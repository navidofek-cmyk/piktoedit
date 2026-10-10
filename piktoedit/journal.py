"""Viditelna historie operaci.

Kazda uprava kresby zapise jeden radek, ktery rika, co se stalo a s cim.
Radky jsou zamerne psane jako prikazy - stejny zapis pozdeji posaji
prikazova radka a generovani, takze historie nebude jen popis, ale i
navod, jak kresbu zopakovat.

    13:42:05  obdelnik 256 256 448 336 --vypln #ffffff --obrys #000000
    13:42:11  nuz "Krivka" --v 512,480 --krizeni 2 --zbylo 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .pathdata import path_to_data


def number(value: float) -> str:
    """Cislo do zapisu: bez zbytecnych desetinnych mist."""
    text = f"{float(value):.1f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-") else "0"


def point(x: float, y: float) -> str:
    return f"{number(x)},{number(y)}"


def color(value) -> str:
    return value.name() if value is not None else "zadna"


def quoted(text: str) -> str:
    cleaned = str(text).replace('"', "'")
    return f'"{cleaned}"'


def style_args(style) -> str:
    """Spolecny zapis vyplne, obrysu a tloustky."""
    parts = [f"--vypln {color(style.fill)}", f"--obrys {color(style.stroke)}"]
    if style.stroke is not None:
        parts.append(f"--tloustka {number(style.stroke_width)}")
    if style.opacity < 1.0:
        parts.append(f"--kryti {number(style.opacity * 100)}")
    return " ".join(parts)


#: Nazvy tvaru v zapisu. Historie i budouci prikazova radka mluvi cesky.
KIND_NAMES = {
    "rect": "obdelnik",
    "ellipse": "elipsa",
    "line": "cara",
    "path": "krivka",
    "text": "text",
}


def kind_name(shape) -> str:
    return KIND_NAMES.get(getattr(shape, "kind", ""), getattr(shape, "kind", "tvar"))


def shape_line(shape) -> str:
    """Cely radek pro nove vznikly tvar.

    Radek je zamerne takovy, aby tvar dokazal znovu vyrobit - rozmery jsou
    v souradnicich kresby a pripadne otoceni je zvlast v ``--uhel``, takze
    zapis neni jen popis, ale i prikaz.
    """
    return f"{kind_name(shape)} {shape_args(shape)}"


def shape_args(shape) -> str:
    """Popis tvaru tak, jak by sel zadat."""
    kind = getattr(shape, "kind", "")
    if kind == "line":
        parts = [_line_args(shape)]
    elif kind == "path":
        parts = [_path_args(shape)]
    elif kind == "text":
        parts = [_text_args(shape)]
    else:
        parts = [_box_args(shape)]
        if getattr(shape, "radius", 0.0):
            parts.append(f"--radius {number(shape.radius)}")
    if shape.rotation():
        parts.append(f"--uhel {number(shape.rotation())}")
    parts.append(style_args(shape.style))
    if shape.name and shape.name != getattr(shape, "default_name", ""):
        parts.append(f"--nazev {quoted(shape.name)}")
    return " ".join(part for part in parts if part)


def _box_args(shape) -> str:
    """Obdelnik tvaru v souradnicich kresby, bez otoceni."""
    rect = shape.local_rect().translated(shape.pos())
    return (f"{number(rect.x())} {number(rect.y())} "
            f"{number(rect.width())} {number(rect.height())}")


def _line_args(shape) -> str:
    line = shape.line().translated(shape.pos())
    return f"{point(line.x1(), line.y1())} {point(line.x2(), line.y2())}"


def _path_args(shape) -> str:
    # Zapis krivky je dlouhy, ale je to presne ona - jinak by se z historie
    # nedala zopakovat.
    closed = bool(getattr(shape, "closed", False))
    data = path_to_data(shape.path().translated(shape.pos()), closed)
    parts = [f"--d {quoted(data)}"]
    if closed:
        parts.append("--uzavrena")
    return " ".join(parts)


def _text_args(shape) -> str:
    font = shape.font()
    parts = [quoted(shape.text()),
             point(shape.pos().x(), shape.pos().y()),
             f"--velikost {number(font.pointSizeF())}",
             f"--pismo {quoted(font.family())}"]
    if not font.bold():
        parts.append("--obycejne")
    return " ".join(parts)


def shape_ids(shapes, all_shapes) -> str:
    """Zapis ``--tvary 2,3``: poradi tvaru v kresbe odspodu, od jednicky.

    Diky nemu je radek samonosny - pri prehravani historie neni potreba
    hadat, co bylo v te chvili vybrane.
    """
    order = {id(shape): index + 1 for index, shape in enumerate(all_shapes)}
    numbers = sorted(order[id(shape)] for shape in shapes if id(shape) in order)
    return f"--tvary {','.join(str(value) for value in numbers)}" if numbers else ""


def box_args(shape) -> str:
    """Kde tvar lezi a jak je velky - pro radky o posunu a zmene velikosti."""
    parts = [f"--na {_box_corner(shape)}", f"--rozmer {_box_size(shape)}"]
    if shape.rotation():
        parts.append(f"--uhel {number(shape.rotation())}")
    return " ".join(parts)


def _box_corner(shape) -> str:
    rect = shape.local_rect().translated(shape.pos())
    return point(rect.x(), rect.y())


def _box_size(shape) -> str:
    rect = shape.local_rect()
    return f"{number(rect.width())}x{number(rect.height())}"


@dataclass
class Entry:
    """Jeden radek historie."""

    time: datetime
    text: str

    def line(self) -> str:
        return f"{self.time:%H:%M:%S}  {self.text}"


@dataclass
class Journal:
    """Historie jedne kresby."""

    entries: list[Entry] = field(default_factory=list)
    #: Kolik radku se drzi; starsi se zahazuji, aby pamet nerostla donekonecna.
    limit: int = 2000

    def record(self, text: str) -> Entry:
        entry = Entry(datetime.now(), text.strip())
        self.entries.append(entry)
        if len(self.entries) > self.limit:
            del self.entries[:len(self.entries) - self.limit]
        return entry

    def clear(self, reason: str = "") -> None:
        self.entries.clear()
        if reason:
            self.record(reason)

    def lines(self) -> list[str]:
        return [entry.line() for entry in self.entries]

    def to_text(self, title: str = "") -> str:
        head = []
        if title:
            head.append(f"# {title}")
            head.append(f"# zapsano {datetime.now():%d.%m.%Y %H:%M}")
            head.append("")
        return "\n".join(head + self.lines()) + "\n"

    def save(self, path: str | Path, title: str = "") -> Path:
        target = Path(path)
        target.write_text(self.to_text(title), encoding="utf-8")
        return target

    def __len__(self) -> int:
        return len(self.entries)
