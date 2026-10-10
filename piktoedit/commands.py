"""Prikazova vrstva editoru.

Kazda uprava kresby se da vyjadrit jednim radkem prikazu:

    obdelnik 256 256 448 336 --vypln #ffffff --obrys #000000 --tloustka 8
    nuz --v 520,500
    popisek "MAMA" --velikost 96 --odsazeni 60

Historie operaci zapisuje prave tyhle radky, takze historie neni jen popis,
ale navod, jak kresbu zopakovat. Stejnou slovni zasobu pouziva prikazove
okno v editoru a pozdeji ji prevezme prikazova radka i generovani.

Radek je vzdy samonosny: rika i to, na kterych tvarech se operace stala
(``--tvary 2,3``), aby se pri prehravani nemuselo hadat, co bylo vybrane.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QLineF, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainterPath

from .journal import color as color_text
from .journal import number, quoted, shape_line
from .journal import point as point_text
from .nodes import insert_node, locate_point, path_to_subpaths, subpaths_to_path
from .pathdata import parse_path_data
from .paths import TEMPLATE_DIR
from .shapes import (
    EllipseShape,
    LineShape,
    PathShape,
    RectShape,
    ShapeMixin,
    TextShape,
)
from .style import parse_color


class CommandError(Exception):
    """Prikaz se nepovedlo pochopit nebo provest."""


#: Cas na zacatku radku historie; pri prehravani se preskoci.
_TIME = re.compile(r"^\d{1,2}:\d{2}:\d{2}\s+")

_NONE_WORDS = ("zadna", "zadny", "none", "nic", "-")


def tokenize(line: str) -> list[tuple[str, bool]]:
    """Rozlozi radek na slova. Druha hodnota rika, zda bylo v uvozovkach."""
    tokens: list[tuple[str, bool]] = []
    current = ""
    quote = ""
    was_quoted = False
    for char in line:
        if quote:
            if char == quote:
                tokens.append((current, True))
                current = ""
                quote = ""
                was_quoted = False
            else:
                current += char
        elif char in "\"'":
            if current:
                tokens.append((current, was_quoted))
                current = ""
            quote = char
            was_quoted = True
        elif char.isspace():
            if current:
                tokens.append((current, was_quoted))
                current = ""
        else:
            current += char
    if current:
        tokens.append((current, was_quoted))
    return tokens


@dataclass
class Args:
    """Rozebrane argumenty jednoho prikazu."""

    words: list[str] = field(default_factory=list)
    options: dict[str, list[str]] = field(default_factory=dict)

    # -- pritomnost -------------------------------------------------------
    def has(self, *names: str) -> bool:
        return any(name in self.options for name in names)

    def value(self, name: str, default: str | None = None) -> str | None:
        values = self.options.get(name)
        return values[0] if values else default

    def values(self, name: str) -> list[str]:
        return list(self.options.get(name, []))

    def word(self) -> str | None:
        """Prvni nepojmenovany argument, ktery neni cislo."""
        return next((w for w in self.words if not _is_number(w)), None)

    # -- cisla ------------------------------------------------------------
    @staticmethod
    def _numbers(pieces: list[str]) -> list[float]:
        out: list[float] = []
        for piece in pieces:
            cleaned = str(piece).replace(";", ",").replace("x", " ")
            for part in cleaned.split(","):
                for bit in part.split():
                    try:
                        out.append(float(bit))
                    except ValueError as error:
                        raise CommandError(f"'{bit}' neni cislo") from error
        return out

    def numbers(self) -> list[float]:
        """Vsechna cisla z nepojmenovanych argumentu."""
        return self._numbers([w for w in self.words if _is_number(w)])

    def number(self, name: str, default: float | None = None) -> float:
        values = self.options.get(name)
        if not values:
            if default is None:
                raise CommandError(f"chybi --{name}")
            return float(default)
        found = self._numbers(values)
        if not found:
            if default is None:
                raise CommandError(f"--{name} chce cislo")
            return float(default)
        return found[0]

    def need(self, count: int, usage: str) -> list[float]:
        found = self.numbers()
        if len(found) < count:
            raise CommandError(f"chybi cisla, ocekavam: {usage}")
        return found[:count]

    # -- body a rozmery ---------------------------------------------------
    def point(self, name: str, default: QPointF | None = None) -> QPointF:
        values = self.options.get(name)
        if not values:
            if default is None:
                raise CommandError(f"chybi --{name} x,y")
            return QPointF(default)
        found = self._numbers(values)
        if len(found) < 2:
            raise CommandError(f"--{name} chce dve cisla, treba 120,340")
        return QPointF(found[0], found[1])

    def points(self, name: str) -> list[QPointF]:
        found = self._numbers(self.options.get(name, []))
        if len(found) < 2:
            raise CommandError(f"--{name} chce body jako x,y x,y")
        return [QPointF(found[i], found[i + 1])
                for i in range(0, len(found) - 1, 2)]

    def word_points(self) -> list[QPointF]:
        found = self.numbers()
        return [QPointF(found[i], found[i + 1])
                for i in range(0, len(found) - 1, 2)]

    def size(self, name: str = "rozmer") -> tuple[float, float] | None:
        values = self.options.get(name)
        if not values:
            return None
        found = self._numbers(values)
        if len(found) < 2:
            raise CommandError(f"--{name} chce sirku a vysku, treba 120x80")
        return found[0], found[1]

    # -- barvy ------------------------------------------------------------
    def color(self, name: str, default: QColor | None = None) -> QColor | None:
        values = self.options.get(name)
        if not values:
            return default
        text = values[0].strip()
        if text.lower() in _NONE_WORDS:
            return None
        found = parse_color(text)
        if found is None:
            raise CommandError(f"'{text}' neni barva (zkus #ff8800 nebo 'zadna')")
        return found

    # -- tvary ------------------------------------------------------------
    def indices(self, name: str = "tvary") -> list[int]:
        values = self.options.get(name)
        if not values:
            return []
        return [int(round(value)) for value in self._numbers(values)]


def parse(line: str) -> tuple[str, Args]:
    """Rozebere radek na nazev prikazu a argumenty."""
    tokens = tokenize(_TIME.sub("", line.strip()))
    if not tokens:
        return "", Args()

    name = tokens[0][0].lower()
    args = Args()
    option: str | None = None
    for value, was_quoted in tokens[1:]:
        if not was_quoted and value == "#":
            # Poznamka na konci radku, treba vypsane nazvy smazanych tvaru.
            # Samostatna mrizka, aby se nepletla s barvou #ffcc00.
            break
        if not was_quoted and value.startswith("--") and len(value) > 2:
            option = value[2:].lower()
            args.options.setdefault(option, [])
        elif option is not None:
            args.options[option].append(value)
        else:
            args.words.append(value)
    return name, args


@dataclass
class Command:
    """Jeden prikaz: jak se pise, co dela a cim se provede."""

    name: str
    usage: str
    help: str
    run: Callable[["Runner", Args], str]


#: Vsechny prikazy vcetne druhych nazvu; poradi zapisu je poradi v napovede.
COMMANDS: dict[str, Command] = {}


def command(name: str, usage: str, help_text_value: str, *aliases: str):
    def wrap(func: Callable[["Runner", Args], str]):
        entry = Command(name, usage, help_text_value, func)
        COMMANDS[name] = entry
        for alias in aliases:
            COMMANDS[alias] = entry
        return func
    return wrap


def _is_number(text: str) -> bool:
    cleaned = str(text).replace(",", " ").replace("x", " ").split()
    if not cleaned:
        return False
    for bit in cleaned:
        try:
            float(bit)
        except ValueError:
            return False
    return True


def _unique(shapes: list[ShapeMixin]) -> list[ShapeMixin]:
    seen: set[int] = set()
    out: list[ShapeMixin] = []
    for shape in shapes:
        if id(shape) not in seen:
            seen.add(id(shape))
            out.append(shape)
    return out


def _near_path(path: QPainterPath, position: QPointF, tolerance: float) -> bool:
    probe = QPainterPath()
    probe.addEllipse(position, tolerance, tolerance)
    return path.intersects(probe)


class Runner:
    """Provadi prikazy nad otevrenou kresbou."""

    def __init__(self, host):
        self.host = host

    # -- zkratky ----------------------------------------------------------
    @property
    def view(self):
        return self.host.view

    @property
    def scene(self):
        return self.host.scene

    @property
    def document(self):
        return self.host.document

    @property
    def style(self):
        return self.host.view.default_style

    def shapes(self) -> list[ShapeMixin]:
        return self.scene.shapes()

    # -- hledani tvaru ----------------------------------------------------
    def at(self, position: QPointF) -> ShapeMixin | None:
        """Nejvyssi tvar v danem miste."""
        best: ShapeMixin | None = None
        for shape in self.shapes():
            tolerance = max(4.0, shape.style.stroke_width)
            bounds = shape.sceneBoundingRect().adjusted(
                -tolerance, -tolerance, tolerance, tolerance)
            if not bounds.contains(position):
                continue
            path = shape.scene_path()
            if path.contains(position) or _near_path(path, position, tolerance):
                best = shape
        return best

    def by_name(self, name: str) -> list[ShapeMixin]:
        wanted = name.strip().lower()
        return [shape for shape in self.shapes()
                if shape.name.strip().lower() == wanted]

    def resolve(self, args: Args, required: bool = True) -> list[ShapeMixin]:
        """Na kterych tvarech se ma prikaz provest.

        Poradi: cisla v ``--tvary``, pak nazev, pak misto ``--na``, nakonec
        soucasny vyber. Cisla jsou poradi tvaru odspodu, pocitano od jedne.
        """
        shapes = self.shapes()
        chosen: list[ShapeMixin] = []

        for index in args.indices("tvary") + args.indices("tvar"):
            if 1 <= index <= len(shapes):
                chosen.append(shapes[index - 1])
            else:
                raise CommandError(
                    f"tvar {index} neexistuje, kresba ma {len(shapes)} tvaru")

        if not chosen:
            names = args.values("nazev")
            word = args.word()
            if word:
                names.append(word)
            for name in names:
                chosen.extend(self.by_name(name))

        if not chosen and args.has("na"):
            found = self.at(args.point("na"))
            if found is not None:
                chosen.append(found)

        if not chosen:
            chosen = self.scene.selected_shapes()

        if required and not chosen:
            raise CommandError(
                "nevim, na kterem tvaru - pridej --tvary 2 nebo tvar nejdriv vyber")
        return _unique(chosen)

    def ids(self, shapes: list[ShapeMixin]) -> str:
        """Zapis ``--tvary 2,3`` pro radek historie."""
        order = {id(shape): index + 1 for index, shape in enumerate(self.shapes())}
        numbers = sorted(order[id(shape)] for shape in shapes if id(shape) in order)
        return f"--tvary {','.join(str(value) for value in numbers)}" if numbers else ""

    # -- zmeny ------------------------------------------------------------
    def select(self, shapes: list[ShapeMixin]) -> None:
        self.scene.clearSelection()
        for shape in shapes:
            shape.setSelected(True)

    def style_from(self, args: Args, base=None):
        style = (base or self.style).copy()
        if args.has("vypln"):
            style.fill = args.color("vypln")
        if args.has("obrys"):
            style.stroke = args.color("obrys")
        if args.has("tloustka"):
            style.stroke_width = max(0.0, args.number("tloustka"))
        if args.has("kryti"):
            style.opacity = max(0.0, min(1.0, args.number("kryti") / 100.0))
        return style

    def add(self, shape: ShapeMixin, label: str, angle: float = 0.0) -> str:
        shape.setZValue(self.scene.next_z())
        self.scene.addItem(shape)
        shape.sync_origin()
        if angle:
            shape.setRotation(angle)
            shape.sync_origin()
        self.select([shape])
        detail = shape_line(shape)
        self.host.snapshot(label, detail)
        return detail

    def record(self, label: str, detail: str) -> str:
        self.host.snapshot(label, detail)
        return detail


# ---------------------------------------------------------------------------
# Kresleni
# ---------------------------------------------------------------------------

_STYLE_USAGE = "[--vypln barva] [--obrys barva] [--tloustka t] [--kryti %] [--nazev jmeno]"


@command("obdelnik", f"x y sirka vyska [--radius r] [--uhel a] {_STYLE_USAGE}",
         "Nakresli obdelnik.")
def _cmd_rect(run: Runner, args: Args) -> str:
    x, y, width, height = args.need(4, "obdelnik x y sirka vyska")
    shape = RectShape(QRectF(x, y, width, height), run.style_from(args),
                      args.number("radius", 0.0), args.value("nazev"))
    return run.add(shape, "Obdelnik", args.number("uhel", 0.0))


@command("elipsa", f"x y sirka vyska [--uhel a] {_STYLE_USAGE}",
         "Nakresli elipsu vepsanou do zadaneho obdelniku.")
def _cmd_ellipse(run: Runner, args: Args) -> str:
    x, y, width, height = args.need(4, "elipsa x y sirka vyska")
    shape = EllipseShape(QRectF(x, y, width, height), run.style_from(args),
                         args.value("nazev"))
    return run.add(shape, "Elipsa", args.number("uhel", 0.0))


@command("cara", f"x1,y1 x2,y2 [--uhel a] {_STYLE_USAGE}", "Nakresli caru.")
def _cmd_line(run: Runner, args: Args) -> str:
    x1, y1, x2, y2 = args.need(4, "cara x1,y1 x2,y2")
    style = run.style_from(args)
    if not args.has("vypln"):
        style.fill = None
    shape = LineShape(QLineF(x1, y1, x2, y2), style, args.value("nazev"))
    return run.add(shape, "Cara", args.number("uhel", 0.0))


@command("krivka",
         f"--d \"M…\" | x,y x,y x,y [--uzavrena] [--uhel a] {_STYLE_USAGE}",
         "Nakresli krivku ze zapisu SVG nebo z bodu.")
def _cmd_path(run: Runner, args: Args) -> str:
    closed = args.has("uzavrena")
    if args.has("d"):
        path, data_closed = parse_path_data(" ".join(args.values("d")))
        closed = closed or data_closed
    else:
        points = args.word_points()
        if len(points) < 2:
            raise CommandError("krivka chce aspon dva body nebo --d \"M…\"")
        path = QPainterPath(points[0])
        for item in points[1:]:
            path.lineTo(item)
        if closed:
            path.closeSubpath()
    if path.elementCount() < 2:
        raise CommandError("krivka je prazdna")

    style = run.style_from(args)
    if not closed and not args.has("vypln"):
        style.fill = None
    shape = PathShape(path, style, closed, args.value("nazev"))
    return run.add(shape, "Krivka", args.number("uhel", 0.0))


@command("text",
         f"\"obsah\" x,y [--velikost s] [--pismo Arial] [--obycejne] {_STYLE_USAGE}",
         "Napise text na dane misto.")
def _cmd_text(run: Runner, args: Args) -> str:
    content = args.value("obsah") or args.word()
    if not content:
        raise CommandError("text chce obsah v uvozovkach")
    where = args.numbers()
    if len(where) < 2:
        raise CommandError("text chce misto, treba text \"ahoj\" 100,200")

    font = QFont(args.value("pismo", "Arial"))
    font.setPointSizeF(args.number("velikost", 96.0))
    font.setBold(not args.has("obycejne"))

    style = run.style_from(args)
    if not args.has("vypln"):
        style.fill = QColor(style.stroke or QColor("#000000"))
    style.stroke = None
    shape = TextShape(content, style, font, args.value("nazev"))
    shape.setPos(where[0], where[1])
    shape.sync_origin()
    return run.add(shape, "Text", args.number("uhel", 0.0))


# ---------------------------------------------------------------------------
# Kresba jako celek
# ---------------------------------------------------------------------------

@command("strana", "[sirka vyska] [--mrizka g] [--pozadi barva] [--nazev jmeno]",
         "Nastavi rozmer kresby, mrizku a pozadi.")
def _cmd_page(run: Runner, args: Args) -> str:
    document = run.document
    size = args.numbers()
    if len(size) >= 2:
        document.width, document.height = size[0], size[1]
    if args.has("mrizka"):
        document.grid_size = max(0.5, args.number("mrizka"))
    if args.has("pozadi"):
        document.background = args.color("pozadi")
    if args.has("nazev"):
        document.title = args.value("nazev", "")
    run.scene.update_page()
    run.record("Nastaveni kresby",
               f"strana {number(document.width)} {number(document.height)} "
               f"--mrizka {number(document.grid_size)} "
               f"--pozadi {color_text(document.background)}")
    return f"Kresba {number(document.width)}x{number(document.height)}."


@command("popisek", "\"text\" [--velikost s] [--odsazeni m] [--barva c] | --odebrat",
         "Napise nebo zmeni popisek pod piktogramem.")
def _cmd_caption(run: Runner, args: Args) -> str:
    if args.has("odebrat"):
        run.host.remove_caption()
        return "Popisek odebran."

    panel = run.host.caption_panel
    content = args.value("text") or args.word()
    if not content:
        raise CommandError("popisek chce text v uvozovkach")
    panel.text_edit.setText(content)
    if args.has("velikost"):
        panel.size_spin.setValue(args.number("velikost"))
    if args.has("odsazeni"):
        panel.margin_spin.setValue(args.number("odsazeni"))
    if args.has("barva"):
        chosen = args.color("barva")
        if chosen is not None:
            panel.color_button.set_color(chosen)
    run.host.apply_caption()
    return f"Popisek: {content}"


@command("predloha", "\"cesta/k/obrazku.png\" [--kryti %] | --odebrat",
         "Podlozi obrazek k obkresleni.")
def _cmd_reference(run: Runner, args: Args) -> str:
    if args.has("odebrat"):
        run.host.remove_reference()
        return "Predloha odebrana."
    path = args.value("cesta") or args.word() or ""
    if not path:
        raise CommandError("predloha chce cestu k obrazku")
    if not Path(path).exists():
        raise CommandError(f"soubor neexistuje: {path}")
    run.host.set_reference(path)
    if args.has("kryti"):
        run.host.set_reference_opacity(args.number("kryti") / 100.0)
    return f"Predloha: {Path(path).name}"


@command("sablona", "\"zvirata/kocka.svg\" [--dil i] [--na x,y]",
         "Vlozi sablonu nebo jeji dil do kresby.", "vlozit")
def _cmd_insert(run: Runner, args: Args) -> str:
    name = args.value("cesta") or args.word() or ""
    if not name:
        raise CommandError("sablona chce cestu k souboru")
    path = template_path(name)
    if path is None:
        raise CommandError(f"sablonu '{name}' jsem nenasel")
    index = int(args.number("dil", -1))
    where = args.point("na") if args.has("na") else None
    run.host.insert_part(str(path), index, where)
    return f"Vlozeno: {path.name}"


def template_path(name: str) -> Path | None:
    """Najde sablonu podle zapisu v historii - relativne i absolutne."""
    direct = Path(name)
    if direct.exists():
        return direct
    inside = TEMPLATE_DIR / name
    if inside.exists():
        return inside
    # Zapsany byl treba jen nazev souboru; najdeme ho mezi sablonami.
    found = sorted(TEMPLATE_DIR.rglob(direct.name))
    return found[0] if found else None


def template_name(path: str | Path) -> str:
    """Jak se sablona zapise do historie: relativne ke slozce se sablonami."""
    file = Path(path)
    try:
        return file.resolve().relative_to(TEMPLATE_DIR.resolve()).as_posix()
    except (ValueError, OSError):
        return file.as_posix()


# ---------------------------------------------------------------------------
# Vyber a uprava tvaru
# ---------------------------------------------------------------------------

@command("vybrat", "--vse | --nic | --tvary 2,3 | --nazev jmeno | --na x,y",
         "Vybere tvary, se kterymi budou pracovat dalsi prikazy.")
def _cmd_select(run: Runner, args: Args) -> str:
    if args.has("nic"):
        run.scene.clearSelection()
        return "Vyber zrusen."
    shapes = run.shapes() if args.has("vse") else run.resolve(args)
    run.select(shapes)
    if not shapes:
        return "Nic nevybrano."
    return f"Vybrano {len(shapes)}: " + ", ".join(shape.name for shape in shapes[:4])


@command("posun", "--tvary 2 (--o dx,dy | --na x,y [--rozmer sirkaxvyska] [--uhel a])",
         "Posune tvar, zmeni jeho rozmer nebo otoceni.",
         "velikost", "otoceni", "umistit")
def _cmd_place(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    ids = run.ids(shapes)

    if args.has("o"):
        delta = args.point("o")
        for shape in shapes:
            shape.setPos(shape.pos() + delta)
            shape.sync_origin()
        run.select(shapes)
        return run.record("Posun",
                          f"posun {ids} --o {point_text(delta.x(), delta.y())}")

    if not args.has("na", "rozmer", "uhel"):
        raise CommandError("posun chce --o dx,dy nebo --na x,y")
    if len(shapes) > 1:
        raise CommandError("--na umisti jeden tvar; vic tvaru posune --o dx,dy")

    shape = shapes[0]
    box = shape.local_rect().translated(shape.pos())
    target = args.point("na", box.topLeft())
    width, height = args.size("rozmer") or (box.width(), box.height())
    angle = args.number("uhel", shape.rotation())

    shape.setPos(QPointF(0.0, 0.0))
    shape.set_local_rect(QRectF(target.x(), target.y(), width, height))
    shape.setRotation(angle)
    shape.sync_origin()
    run.select([shape])

    detail = (f"posun {ids} --na {point_text(target.x(), target.y())} "
              f"--rozmer {number(width)}x{number(height)}")
    if angle:
        detail += f" --uhel {number(angle)}"
    return run.record("Posun", detail)


@command("barva",
         "[--vypln barva] [--obrys barva] [--tloustka t] [--kryti %] [--tvary 2,3]",
         "Zmeni vzhled vybranych tvaru.", "styl")
def _cmd_color(run: Runner, args: Args) -> str:
    parts = [f"--{name} {args.value(name)}"
             for name in ("vypln", "obrys", "tloustka", "kryti") if args.has(name)]
    if not parts:
        raise CommandError("barva chce treba --vypln #ff8800")

    shapes = run.resolve(args)
    for shape in shapes:
        shape.set_style(run.style_from(args, shape.style))
    run.select(shapes)
    return run.record("Zmena vzhledu",
                      f"barva {' '.join(parts)} {run.ids(shapes)}".strip())


@command("smazat", "[--tvary 2,3]", "Smaze vybrane tvary.")
def _cmd_delete(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    count = len(shapes)
    run.select(shapes)
    run.host.delete_selection()
    return f"Smazano {count} tvaru."


@command("duplikovat", "[--tvary 2]", "Udela kopii vybranych tvaru.")
def _cmd_duplicate(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    run.select(shapes)
    run.host.duplicate()
    return f"Zkopirovano {len(shapes)} tvaru."


@command("poradi", "--nahoru | --dolu [--tvary 2]",
         "Posune tvar nad nebo pod ostatni.")
def _cmd_order(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    run.select(shapes)
    run.host.reorder(-1 if args.has("dolu") else 1)
    return "Poradi zmeneno."


@command("zarovnat", "--vodorovne | --svisle [--tvary 2,3]",
         "Posune vyber na stred strany.")
def _cmd_align(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    run.select(shapes)
    run.host.center_on_page(not args.has("svisle"))
    return "Zarovnano."


@command("na-krivku", "[--tvary 2]",
         "Prevede obdelnik, elipsu nebo caru na krivku.", "prevest")
def _cmd_to_path(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    run.select(shapes)
    run.host.convert_to_path()
    return "Prevedeno na krivku."


@command("napojit", "[--tvary 2,3]", "Spoji konce krivek, aby se daly vyplnit.")
def _cmd_join(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    if len(shapes) < 2:
        raise CommandError("napojit chce aspon dve krivky")
    run.select(shapes)
    run.host.join_selected()
    return "Napojeno."


@command("uzavrit", "[--tvary 2]", "Uzavre krivku, aby mela vypln.")
def _cmd_close(run: Runner, args: Args) -> str:
    shapes = run.resolve(args)
    run.select(shapes)
    run.host.close_selected()
    return "Uzavreno."


#: Nazev prikazu -> operace, kterou umi okno editoru.
_BOOLEAN = {"sjednotit": "unite", "odecist": "subtract",
            "prunik": "intersect", "vyloucit": "exclude"}


@command("sjednotit", "[--tvary 2,3]",
         "Slouci tvary do jednoho (odecist, prunik, vyloucit pracuji stejne).",
         "odecist", "prunik", "vyloucit")
def _cmd_boolean(run: Runner, args: Args) -> str:
    operation = _BOOLEAN.get(args.value("_prikaz", "sjednotit"), "unite")
    shapes = run.resolve(args)
    if len(shapes) < 2:
        raise CommandError("tahle operace chce aspon dva tvary")
    run.select(shapes)
    run.host.boolean_op(operation)
    return "Hotovo."


@command("uzel", "--pridat --na x,y | --smazat --na x,y [--tvary 2]",
         "Prida nebo odebere uzel krivky.")
def _cmd_node(run: Runner, args: Args) -> str:
    position = args.point("na")
    shapes = [shape for shape in run.resolve(args, required=False)
              if isinstance(shape, PathShape)]
    if not shapes:
        found = run.at(position)
        shapes = [found] if isinstance(found, PathShape) else []
    if not shapes:
        raise CommandError("uzly se upravuji na krivce; nejdriv prevest")
    shape = shapes[0]

    subpaths = path_to_subpaths(shape.path())
    local = shape.mapFromScene(position)
    located = locate_point(subpaths, local)
    if located is None:
        raise CommandError("v tom miste zadna krivka neni")
    part, parameter, _ = located

    if args.has("smazat"):
        nodes = subpaths[part].nodes
        if len(nodes) <= 2:
            raise CommandError("krivka by zustala bez uzlu")
        index = min(range(len(nodes)),
                    key=lambda i: (nodes[i].point - local).manhattanLength())
        del nodes[index]
        label, detail = "Smazani uzlu", f"uzel --smazat {quoted(shape.name)}"
    else:
        insert_node(subpaths[part], parameter)
        label, detail = "Pridani uzlu", f"uzel --pridat {quoted(shape.name)}"

    shape.setPath(subpaths_to_path(subpaths))
    shape.sync_origin()
    run.select([shape])
    return run.record(label,
                      f"{detail} --na {point_text(position.x(), position.y())}")


# ---------------------------------------------------------------------------
# Nuz, guma, vypln
# ---------------------------------------------------------------------------

@command("nuz", "--v x,y [--vse] | --tah x,y x,y",
         "Orezava krivky: odebere kousek mezi krizenimi, nebo rozreze carou.")
def _cmd_cut(run: Runner, args: Args) -> str:
    from .tools import CutTool

    tool = CutTool(run.view)
    if args.has("tah"):
        points = args.points("tah")
        if not tool.cut_along(points[0], points[-1]):
            raise CommandError("cara nozem nic neprotala")
        return "Rozrezano."

    if not tool.cut_at(args.point("v"), args.has("vse", "rozdelit")):
        raise CommandError("tam neni co rezat")
    return "Orezano."


@command("rozdelit", "--v x,y", "Rozdeli krivku v danem miste, nic nemaze.")
def _cmd_split(run: Runner, args: Args) -> str:
    from .tools import CutTool

    if not CutTool(run.view).cut_at(args.point("v"), True):
        raise CommandError("tam neni co delit")
    return "Rozdeleno."


@command("guma", "--tah x,y x,y … [--prumer d] [--cele-objekty]",
         "Vygumuje plochu podel tahu.")
def _cmd_erase(run: Runner, args: Args) -> str:
    from .tools import EraserTool

    points = args.points("tah")
    size = args.number("prumer", run.view.eraser_size)
    if not EraserTool(run.view).erase_along(points, size, args.has("cele-objekty")):
        raise CommandError("tah gumy nic nezasahl")
    return "Vygumovano."


@command("vypln", "--oblast x,y --barva barva | \"nazev\" --v x,y --barva barva",
         "Vyplni uzavrenou plochu nebo prebarvi tvar.")
def _cmd_fill(run: Runner, args: Args) -> str:
    chosen = args.color("barva", run.style.fill)
    if chosen is None:
        raise CommandError("vypln chce barvu, treba --barva #ffcc00")

    previous = run.style.fill
    run.style.fill = QColor(chosen)
    try:
        if args.has("oblast"):
            done = run.view.fill_region(args.point("oblast"), None, True)
        else:
            where = args.point("v")
            done = run.view.fill_region(where, run.at(where), False)
    finally:
        run.style.fill = previous
    if not done:
        raise CommandError("tam se nic vyplnit neda")
    return "Vyplneno."


# ---------------------------------------------------------------------------
# Napoveda a prehravani
# ---------------------------------------------------------------------------

@command("prikazy", "[nazev]", "Vypise prehled prikazu.", "napoveda", "?")
def _cmd_help(run: Runner, args: Args) -> str:
    wanted = args.word()
    if wanted:
        entry = COMMANDS.get(wanted.lower())
        if entry is None:
            raise CommandError(f"prikaz '{wanted}' neznam")
        return f"{entry.name} {entry.usage}\n  {entry.help}"
    return help_text()


@command("prehrat", "\"cesta/k/historii.txt\"",
         "Zopakuje operace ze souboru historie.")
def _cmd_replay(run: Runner, args: Args) -> str:
    path = args.value("cesta") or args.word() or ""
    if not path:
        raise CommandError("prehrat chce cestu k souboru")
    file = Path(path)
    if not file.exists():
        raise CommandError(f"soubor neexistuje: {path}")
    return run_script(run.host, file.read_text(encoding="utf-8")).summary()


def help_text() -> str:
    """Prehled prikazu, jeden za druhym."""
    seen: set[int] = set()
    lines: list[str] = []
    for entry in COMMANDS.values():
        if id(entry) in seen:
            continue
        seen.add(id(entry))
        lines.append(f"{entry.name} {entry.usage}")
        lines.append(f"    {entry.help}")
    return "\n".join(lines)


@dataclass
class Report:
    """Vysledek prehrani vice radku."""

    done: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.skipped

    def summary(self) -> str:
        text = f"Provedeno {len(self.done)} prikazu."
        if self.skipped:
            text += f" Nepovedlo se {len(self.skipped)}:"
            for line, reason in self.skipped[:5]:
                text += f"\n  {line}  ->  {reason}"
        return text


def run_line(host, line: str) -> str:
    """Provede jeden prikaz. Vraci hlasku, chybu hlasi :class:`CommandError`."""
    name, args = parse(line)
    if not name or name.startswith("#"):
        return ""
    entry = COMMANDS.get(name)
    if entry is None:
        raise CommandError(f"neznamy prikaz '{name}'; seznam vypise 'prikazy'")
    if name in _BOOLEAN:
        # Booleovske operace maji jedno telo, musi poznat, jak byly zavolane.
        args.options["_prikaz"] = [name]
    return entry.run(Runner(host), args)


def run_script(host, text: str, stop_on_error: bool = False) -> Report:
    """Provede vic radku za sebou; prazdne radky a komentare preskoci."""
    report = Report()
    for raw in text.splitlines():
        line = _TIME.sub("", raw.strip())
        if not line or line.startswith("#"):
            continue
        try:
            run_line(host, line)
        except CommandError as error:
            report.skipped.append((line, str(error)))
        except Exception as error:  # chyba pri provadeni, ne v zapisu
            report.skipped.append((line, f"{type(error).__name__}: {error}"))
        else:
            report.done.append(line)
            continue
        if stop_on_error:
            break
    return report
