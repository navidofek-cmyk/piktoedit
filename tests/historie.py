"""Viditelna historie operaci."""

from pathlib import Path

from spolecne import *  # noqa: F403

app, window, view = start()

# ---------------------------------------------------------------------------
case("kazda operace zapise radek")
start_count = len(window.journal)

window.select_tool("obdelnik")
drag(QPointF(250, 250), QPointF(700, 600))
window.select_tool("elipsa")
drag(QPointF(300, 700), QPointF(600, 850))
window.caption_panel.text_edit.setText("mama")
window.apply_caption()

lines = window.journal.lines()
note("zapsane radky:")
for line in lines:
    note(f"  {line}")

check("pribyly tri radky", len(lines) - start_count == 3, f"{len(lines)} radku")
check("obdelnik je zapsany i s rozmerem",
      any("obdelnik" in line and "--vypln" in line for line in lines))
check("elipsa je zapsana", any("elipsa " in line for line in lines))
check("popisek je zapsany i s textem",
      any("popisek" in line and "MAMA" in line.upper() for line in lines))
check("radky zacinaji casem", all(line[2] == ":" for line in lines))

# ---------------------------------------------------------------------------
case("rez a guma se zapisi s podrobnostmi")
pencil(straight((150, 500), (900, 500)), "tah")
pencil(straight((400, 250), (400, 750)), "rez1")
pencil(straight((650, 250), (650, 750)), "rez2")
knife(QPointF(520, 500))
erase([QPointF(800, 450), QPointF(800, 550)], size=50)

lines = window.journal.lines()
note("zapsane radky:")
for line in lines:
    note(f"  {line}")

check("rez zapsal pocet krizeni a zbylych casti",
      any("nuz" in line and "--krizeni" in line and "--zbylo" in line for line in lines))
check("guma zapsala prumer", any("guma" in line and "--prumer" in line for line in lines))
check("kresleni tuzkou je v historii",
      sum(1 for line in lines if "krivka " in line) >= 3,
      str([line for line in lines if "krivka " in line][:1]))

# ---------------------------------------------------------------------------
case("historie se da ulozit")
pencil(straight((200, 300), (800, 300)), "tah")
target = Path(window.journal.save(
    Path(__file__).resolve().parent / "_historie_test.txt", "zkouska"))
content = target.read_text(encoding="utf-8")
check("soubor vznikl", target.exists())
check("ma hlavicku", content.startswith("# zkouska"), content.splitlines()[0])
check("obsahuje operaci", "krivka" in content)
target.unlink(missing_ok=True)

case("ulozeni kresby zapise historii vedle ni")
pencil(straight((200, 300), (800, 300)), "tah")
drawing = Path(__file__).resolve().parent / "_kresba_test.svg"
window._write(drawing)
journal_file = window.journal_path(drawing)
check("vznikl i soubor s historii", journal_file.exists(), journal_file.name)
if journal_file.exists():
    check("historie neni prazdna", len(journal_file.read_text(encoding="utf-8")) > 20)
drawing.unlink(missing_ok=True)
journal_file.unlink(missing_ok=True)

case("panel historie ukazuje tytez radky")
pencil(straight((200, 300), (800, 300)), "tah")
shown = window.history_panel.text.toPlainText().splitlines()
check("panel ma stejny pocet radku", len(shown) == len(window.journal.lines()),
      f"panel {len(shown)}, historie {len(window.journal.lines())}")
check("pocitadlo sedi", "Operaci" in window.history_panel.count_label.text(),
      window.history_panel.count_label.text())

case("operace bez zmeny se nezapisuje")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "cara"))
window.snapshot("priprava")
before = len(window.journal)
window.snapshot("nic se nestalo")
check("prazdny snimek radek nepridal", len(window.journal) == before,
      f"{before} -> {len(window.journal)}")

raise SystemExit(summary())
