"""Zaklad: SVG tam a zpet, sablony, okno, popisek, panely, ulozeni."""

from pathlib import Path

from spolecne import *  # noqa: F403
from piktoedit.nodes import bspline, catmull_rom, join_subpaths, Node, SubPath
from piktoedit.panels import PART_MIME, ROLE_FILE, ROLE_INDEX
from piktoedit.preview import part_preview, template_parts, template_preview
from piktoedit.shapes import to_path_shape  # noqa: F401
from piktoedit.tools import FillTool, NodeTool

app, window, view = start(1500, 950)

STYL = Style(fill=QColor("#e74c3c"), stroke=QColor("#000000"), stroke_width=8.0)

# ---------------------------------------------------------------------------
case("SVG tam a zpet")
shapes = [
    RectShape(QRectF(10, 20, 100, 60), STYL, 12.0, "obdelnik"),
    EllipseShape(QRectF(200, 40, 120, 90), STYL, "elipsa"),
    LineShape(QLineF(0, 0, 150, 90), STYL, "cara"),
    PathShape.from_points([QPointF(0, 0), QPointF(40, 80), QPointF(90, 10)],
                          STYL, True, "cesta"),
    TextShape("MAMA", Style(fill=QColor("#000000"), stroke=None),
              QFont("Arial", 72), "popisek"),
]
shapes[2].setPos(300, 300)
shapes[3].setPos(120, 400)
shapes[3].setRotation(30.0)
shapes[4].setPos(200, 800)

document = svgio.Document(width=1024, height=1024, grid_size=16)
text = svgio.to_string(document, shapes)
document2, shapes2 = svgio.from_string(text)
check("typy tvaru sedi", [s.kind for s in shapes2] == [s.kind for s in shapes],
      str([s.kind for s in shapes2]))
check("rozmer dokumentu", (document2.width, document2.height) == (1024.0, 1024.0))
check("pozadi rozpoznano", document2.background is not None
      and document2.background.name() == "#ffffff")
check("mrizka", document2.grid_size == 16.0)
check("rotace prezila", abs(shapes2[3].rotation() - 30.0) < 0.01,
      str(shapes2[3].rotation()))
check("pozice cary", abs(shapes2[2].pos().x() - 300) < 0.01
      and abs(shapes2[2].pos().y() - 300) < 0.01)
check("text zachovan", shapes2[4].text() == "MAMA", shapes2[4].text())
check("zaobleni rohu", abs(shapes2[0].radius - 12.0) < 0.01)
check("barva vyplne", shapes2[0].style.fill.name() == "#e74c3c")
check("druhy zapis je stejny", svgio.to_string(document2, shapes2) == text)

case("parser cest")
from piktoedit.pathdata import parse_path_data
for data in ["M 0 0 L 10 10 Z",
             "m0,0 c10,0 20,10 20,20 s10,20 20,20 z",
             "M 100 100 A 50 50 0 1 1 150 150",
             "M0 0H50V50H0Z",
             "M 10 10 q 20 0 40 40 t 40 40"]:
    path, _ = parse_path_data(data)
    check(f"cesta {data[:24]}", path.elementCount() > 1, f"{path.elementCount()} prvku")

case("hladke krivky a napojeni")
points = [QPointF(0, 0), QPointF(100, 120), QPointF(220, 20), QPointF(320, 160)]
check("catmull prochazi body", all(
    any(abs(node.point.x() - p.x()) < 0.01 for node in catmull_rom(points, False).nodes)
    for p in points))
check("bspline vraci uzly", len(bspline(points, False).nodes) >= 2)
loop = join_subpaths([SubPath([Node(QPointF(0, 0)), Node(QPointF(100, 0))]),
                      SubPath([Node(QPointF(100, 0)), Node(QPointF(100, 100))]),
                      SubPath([Node(QPointF(100, 100)), Node(QPointF(0, 0))])], 5.0)
check("napojeni uzavrelo smycku", len(loop) == 1 and loop[0].closed)

# ---------------------------------------------------------------------------
case("sablony")
templates = sorted((PROJECT / "sablony").rglob("*.svg"))
check("sablony se nasly", len(templates) >= 16, f"{len(templates)} souboru")
for template in templates:
    _, loaded = svgio.load(template)
    check(f"{template.parent.name}/{template.name}", len(loaded) > 0,
          f"{len(loaded)} tvaru")

oblicej = PROJECT / "sablony" / "oblicej" / "oblicej_dily.svg"
dily = template_parts(oblicej)
check("sablona se rozbali na dily", len(dily) >= 15, f"{len(dily)} dilu")
check("dily maji nazvy", all(name.strip() for _, name in dily),
      ", ".join(name for _, name in dily[:3]))
check("dil ma nahled", part_preview(oblicej, dily[0][0]) is not None)
check("sablona ma nahled", template_preview(oblicej) is not None)

case("vlozeni dilu a cele sablony")
window.insert_part(str(oblicej), dily[0][0], QPointF(300, 400))
placed = window.scene.shapes()
check("vlozil se jen jeden dil", len(placed) == 1, f"{len(placed)} tvaru")
if placed:
    center = placed[0].mapToScene(placed[0].local_rect()).boundingRect().center()
    check("dil pristal na zadanem miste",
          abs(center.x() - 300) < 1 and abs(center.y() - 400) < 1,
          f"{center.x():.0f}; {center.y():.0f}")

window.templates.open_template(oblicej)
check("panel ukazuje dily", window.templates.list.count() == len(dily))
item = window.templates.list.item(0)
check("polozka nese soubor i index",
      item.data(ROLE_FILE) == str(oblicej) and item.data(ROLE_INDEX) == dily[0][0])
check("polozka jde pretahnout",
      window.templates.list.mimeData([item]).hasFormat(PART_MIME))
window.templates._show_category()
check("zpet na seznam sablon", window.templates.list.count() >= 16
      and window.templates.list.item(0).data(ROLE_INDEX) == -1)

case("drop na platno")
view.part_dropped.emit(str(oblicej), dily[1][0], QPointF(700, 200))
check("drop vlozil dil", len(window.scene.shapes()) == 1)

case("cela sablona")
window.insert_template(str(PROJECT / "sablony" / "postavy" / "postava_dospely.svg"))
check("cela sablona se vlozi", len(window.scene.shapes()) == 12,
      f"{len(window.scene.shapes())} tvaru")

case("duplikace a zpet")
window.insert_template(str(PROJECT / "sablony" / "postavy" / "postava_dospely.svg"))
before = len(window.scene.shapes())
window.select_all()
window.duplicate()
check("duplikace", len(window.scene.shapes()) == before * 2)
window.undo.stack.undo()
check("zpet po duplikaci", len(window.scene.shapes()) == before)
window.undo.stack.redo()
check("znovu", len(window.scene.shapes()) == before * 2)

# ---------------------------------------------------------------------------
case("popisek pod obrazkem")
window.caption_panel.text_edit.setText("máma")
window.apply_caption()
caption = window.caption_shape()
check("popisek vznikl", caption is not None)
check("popisek velkymi", caption is not None and caption.text() == "MÁMA",
      caption.text() if caption else "")
bounds = caption.mapToScene(caption.local_rect()).boundingRect()
check("popisek na stredu", abs(bounds.center().x() - window.document.width / 2) < 1.0)
check("popisek dole", bounds.bottom() <= window.document.height)
window.caption_panel.size_spin.setValue(140.0)
app.processEvents()
check("popisek se neduplikuje",
      sum(1 for s in window.scene.shapes() if getattr(s, "role", "") == "caption") == 1)

out = Path(svgio.__file__).parent.parent / "tests" / "_docasny.svg"
window._write(out)
window.open_path(out)
reloaded = window.caption_shape()
check("popisek prezil ulozeni", reloaded is not None and reloaded.text() == "MÁMA",
      reloaded.text() if reloaded else "chybi")
out.unlink(missing_ok=True)

# ---------------------------------------------------------------------------
case("vypln respektuje delici caru")
ring = add(EllipseShape(QRectF(200, 200, 600, 600),
                        Style(fill=None, stroke=QColor("#000000"), stroke_width=8.0),
                        "kolo"), 0)
add(LineShape(QLineF(500, 150, 500, 850), TAH, "delici cara"), 1)
view.default_style.fill = QColor("#3498db")
tool = FillTool(view)
view.set_tool(tool)
view.fill_region(QPointF(350, 500), candidate=tool._hollow_shape_at(QPointF(350, 500)))
half = named("Vypln oblasti")
check("delici cara se respektuje", len(half) == 1, "; ".join(messages))
check("vyplnila se jen leva pulka",
      bool(half) and half[0].scene_path().boundingRect().width() < 340)
check("kolecko zustalo bez vyplne", ring.style.fill is None)

case("netesna hranice se odchyti")
for index, (x1, y1, x2, y2) in enumerate([(200, 200, 800, 200), (800, 200, 800, 800),
                                          (800, 800, 200, 800), (200, 800, 200, 400)]):
    add(LineShape(QLineF(x1, y1, x2, y2), TAH, f"c{index}"), index)
check("vypln se neprovedla", not view.fill_region(QPointF(500, 500)))
check("hlaska o netesnosti", any("neni uzavrena" in m for m in messages))

# ---------------------------------------------------------------------------
case("prevod na krivku a uzly")
rect = add(RectShape(QRectF(100, 100, 200, 200), STYL, 0.0, "ctverec"), 0)
rect.setSelected(True)
window.convert_to_path()
converted = window.scene.shapes()[0]
check("prevod na krivku", converted.kind == "path", converted.kind)
node_tool = NodeTool(view)
view.set_tool(node_tool)
node_tool.load(converted)
check("uzly nactene", len(node_tool.subpaths[0].nodes) == 4)

case("zive upravy v panelu")
box = add(RectShape(QRectF(100, 100, 200, 100), STYL, 0.0, "box"), 0)
box.setSelected(True)
window.refresh_panels()
steps = window.undo.stack.count()
window.properties.x_spin.setValue(400.0)
check("X se projevi hned",
      abs(box.mapToScene(box.local_rect()).boundingRect().x() - 400.0) < 0.5)
window.properties.w_spin.setValue(300.0)
check("sirka se projevi hned", abs(box.local_rect().width() - 300.0) < 0.5)
window.properties.angle_spin.setValue(45.0)
check("uhel se projevi hned", abs(box.rotation() - 45.0) < 0.01)
check("zive upravy nezaplavi historii", window.undo.stack.count() == steps)
window.properties._record("Zmena geometrie")
check("po dokonceni se zapise krok zpet", window.undo.stack.count() == steps + 1)

# ---------------------------------------------------------------------------
case("start a panely")
check("po startu je kresba cista", window.undo.stack.isClean(), window.windowTitle())
check("po startu se nepta na ulozeni", window._confirm_discard())
view.zoom_fit()
check("po prizpusobeni je videt cela kresba", 0.2 < view.scale_factor() < 3.0,
      f"zoom {view.scale_factor():.2f}")
counts = {key: len(items) for key, items in window.templates._files.items()}
check("sablony jsou v kategoriich", {"oblicej", "zvirata", "doprava"} <= set(counts),
      str(counts))

raise SystemExit(summary())
