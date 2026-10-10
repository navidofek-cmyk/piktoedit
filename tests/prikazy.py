"""Prikazova vrstva: zapis, provedeni a zpetne prehrani historie.

Nejdulezitejsi je tady posledni pripad: kresba se nakresli mysi, pak se z
jeji historie postavi znovu a oba vysledky se porovnaji. Tim se overuje,
ze historie neni jen popis, ale skutecny navod.
"""

from spolecne import *  # noqa: F403

from piktoedit.commands import (  # noqa: E402
    COMMANDS,
    CommandError,
    parse,
    run_line,
    run_script,
)
from piktoedit.journal import shape_line  # noqa: E402

app, window, view = start()


def layout() -> list[tuple]:
    """Co je v kresbe: druh tvaru a kde lezi."""
    out = []
    for shape in window.scene.shapes():
        box = shape.scene_path().boundingRect()
        out.append((shape.kind, round(box.x()), round(box.y()),
                    round(box.width()), round(box.height())))
    return sorted(out)


def same(first: list[tuple], second: list[tuple], tolerance: float = 3.0) -> bool:
    if len(first) != len(second):
        return False
    for left, right in zip(first, second):
        if left[0] != right[0]:
            return False
        if any(abs(a - b) > tolerance for a, b in zip(left[1:], right[1:])):
            return False
    return True


def difference(first: list[tuple], second: list[tuple]) -> str:
    """Prvni rozdil obou kreseb; pri shode prazdny text."""
    for index, (left, right) in enumerate(zip(first, second)):
        if left != right:
            return f"tvar {index}: {left} != {right}"
    if len(first) != len(second):
        return f"pocet tvaru {len(first)} != {len(second)}"
    return f"{len(first)} tvaru shodne"


def rebuild(lines: list[str]):
    """Vyprazdni kresbu a postavi ji znovu z radku historie."""
    window.undo.stack.setClean()
    window.new_document()
    app.processEvents()
    report = run_script(window, chr(10).join(lines))
    app.processEvents()
    return report


# ---------------------------------------------------------------------------
case("rozebrani radku")
name, args = parse('12:31:40  nuz "Krivka tah" --v 520,499.6 --krizeni 2')
check("nazev prikazu", name == "nuz", name)
check("cas se preskoci", args.words == ["Krivka tah"], str(args.words))
check("bod se precte", abs(args.point("v").x() - 520) < 0.01)
check("volba s cislem", args.number("krizeni") == 2)

name, args = parse('smazat --tvary 2,3  # "Krivka" "Cara"')
check("poznamka za mrizkou se zahodi", args.indices("tvary") == [2, 3],
      str(args.indices("tvary")))

name, args = parse('popisek "MAMA" --velikost 96')
check("text v uvozovkach", args.word() == "MAMA", str(args.word()))
check("uvozovane slovo neni volba", not args.has("mama"))

check("kazdy prikaz ma napovedu",
      all(entry.usage and entry.help for entry in COMMANDS.values()))

# ---------------------------------------------------------------------------
case("kresleni prikazem")
run_line(window, "obdelnik 200 200 400 300 --vypln #ffcc00 --obrys #000000 --tloustka 8")
run_line(window, "elipsa 300 600 200 150 --vypln zadna")
run_line(window, "cara 100,100 900,100 --tloustka 12")
run_line(window, 'krivka 200,800 400,900 600,800 --nazev "vlnka"')
run_line(window, 'text "AHOJ" 120,420 --velikost 64')

shapes = window.scene.shapes()
check("vznikly vsechny tvary", len(shapes) == 5, f"{len(shapes)} tvaru")
kinds = [shape.kind for shape in shapes]
check("druhy tvaru", kinds == ["rect", "ellipse", "line", "path", "text"], str(kinds))

rect = shapes[0]
box = rect.scene_path().boundingRect()
check("obdelnik lezi, kde ma", close(box.center().x(), 400, 6) and close(box.center().y(), 350, 6),
      f"stred {box.center().x():.0f},{box.center().y():.0f}")
check("obdelnik ma zadanou vypln", rect.style.fill.name() == "#ffcc00",
      rect.style.fill.name())
check("elipsa je bez vyplne", shapes[1].style.fill is None)
check("krivka si drzi nazev", shapes[3].name == "vlnka", shapes[3].name)
check("text ma zadanou velikost", abs(shapes[4].font().pointSizeF() - 64) < 0.5,
      str(shapes[4].font().pointSizeF()))
check("kazda operace je v historii", len(window.journal) >= 5, str(len(window.journal)))

# ---------------------------------------------------------------------------
case("chyby prikazu se poznaji")
for bad, why in [
    ("obdelnik 10 20", "chybi cisla"),
    ("obdelnik 10 20 30 40 --vypln zelenomodra", "nesmyslna barva"),
    ("neexistuje 1 2", "neznamy prikaz"),
    ("posun --tvary 9", "tvar neexistuje"),
]:
    try:
        run_line(window, bad)
    except CommandError as error:
        check(f"'{bad}' -> chyba", True, str(error))
    else:
        check(f"'{bad}' -> chyba", False, f"proslo, ackoli {why}")

check("nic z toho nic nenakreslilo", not window.scene.shapes())
check("napoveda vypise prikazy", "obdelnik" in run_line(window, "prikazy"))

# ---------------------------------------------------------------------------
case("uprava tvaru prikazem")
run_line(window, "obdelnik 100 100 200 200")
run_line(window, "obdelnik 500 500 200 200")

run_line(window, "posun --tvary 1 --o 50,25")
first = window.scene.shapes()[0].scene_path().boundingRect()
check("posun o kus", close(first.x(), 150, 2) and close(first.y(), 125, 2),
      f"{first.x():.0f},{first.y():.0f}")

run_line(window, "posun --tvary 2 --na 300,300 --rozmer 100x400")
second = window.scene.shapes()[1].local_rect().translated(window.scene.shapes()[1].pos())
check("umisteni i rozmer",
      close(second.x(), 300, 2) and close(second.width(), 100, 2)
      and close(second.height(), 400, 2),
      f"{second.x():.0f},{second.y():.0f} {second.width():.0f}x{second.height():.0f}")

run_line(window, "barva --vypln #00ff00 --tvary 1,2")
check("barva obou tvaru",
      all(shape.style.fill.name() == "#00ff00" for shape in window.scene.shapes()))

run_line(window, "vybrat --tvary 1")
check("vyber funguje", len(window.scene.selected_shapes()) == 1)
run_line(window, "smazat --tvary 1")
check("smazani ubralo tvar", len(window.scene.shapes()) == 1)

run_line(window, "na-krivku --tvary 1")
check("prevod na krivku", window.scene.shapes()[0].kind == "path",
      window.scene.shapes()[0].kind)

# ---------------------------------------------------------------------------
case("nuz, guma a vypln prikazem")
run_line(window, 'krivka 150,500 900,500 --nazev "tah" --tloustka 10')
run_line(window, "cara 400,250 400,750 --tloustka 10")
run_line(window, "cara 650,250 650,750 --tloustka 10")

run_line(window, "nuz --v 520,500")
check("nuz odebral kus mezi carami", not covered(QPointF(520, 500), 8),
      "v miste kliknuti uz nic neni")
check("tah zustal po stranach",
      covered(QPointF(250, 500), 12) and covered(QPointF(800, 500), 12))

run_line(window, "guma --tah 800,450 800,550 --prumer 60")
check("guma vzala kus pravé casti", not covered(QPointF(800, 500), 6))

run_line(window, "obdelnik 100 100 300 200 --vypln zadna --obrys #000000 --tloustka 6")
filled = run_line(window, "vypln --oblast 250,200 --barva #ff8800")
check("vypln oblasti prosla", "Vyplneno" in filled, filled)
check("vznikl tvar s vyplni",
      any(shape.style.fill is not None and shape.style.fill.name() == "#ff8800"
          for shape in window.scene.shapes()))

# ---------------------------------------------------------------------------
case("zapis tvaru umi tvar znovu vyrobit")
window.select_tool("obdelnik")
drag(QPointF(250, 250), QPointF(700, 600))
window.select_tool("elipsa")
drag(QPointF(300, 700), QPointF(600, 850))
pencil(straight((150, 150), (900, 420)), "tah")
window.select_tool("cara")
drag(QPointF(120, 880), QPointF(880, 940))

original = layout()
lines = [shape_line(shape) for shape in window.scene.shapes()]
note("zapsane tvary:")
for line in lines:
    note(f"  {line[:110]}")

report = rebuild(lines)
check("vsechny radky prosly", report.ok, report.summary())
check("tvary vysly stejne", same(original, layout()),
      difference(original, layout()))

# ---------------------------------------------------------------------------
case("historie kresby se da prehrat")
window.select_tool("obdelnik")
drag(QPointF(220, 220), QPointF(720, 560))
pencil(straight((150, 650), (900, 650)), "tah")
pencil(straight((400, 500), (400, 800)), "rez1")
pencil(straight((650, 500), (650, 800)), "rez2")
knife(QPointF(520, 650))
erase([QPointF(820, 620), QPointF(820, 680)], size=50)
window.caption_panel.text_edit.setText("kocka")
window.apply_caption()

original = layout()
lines = window.journal.lines()
note(f"historie ma {len(lines)} radku:")
for line in lines:
    note(f"  {line[:110]}")

report = rebuild(lines)
note(report.summary())
check("vsechny radky historie se povedlo provest", report.ok, report.summary())
check("prehrana kresba vysla stejne", same(original, layout()),
      difference(original, layout()))

# ---------------------------------------------------------------------------
case("prikazove okno v editoru")
ok = window.run_command("obdelnik 300 300 200 200 --vypln #112233")
check("prikaz prosel", ok)
check("tvar vznikl", len(window.scene.shapes()) == 1)
check("vysledek je videt v panelu",
      "obdelnik" in window.history_panel.text.toPlainText())

bad = window.run_command("obdelnik moc malo")
check("chybny prikaz neprosel", not bad)
check("chyba se ukazala u radku",
      "obdelnik moc malo" in window.history_panel.result_label.text(),
      window.history_panel.result_label.text())
check("chybny prikaz nic nenakreslil", len(window.scene.shapes()) == 1)

raise SystemExit(summary())
