"""Prevod tvaru na krivku a navazna uprava uzlu, cele pres mys."""

from spolecne import *  # noqa: F403
from piktoedit.tools import NodeTool

app, window, view = start()

# ---------------------------------------------------------------------------
case("obdelnik nakresleny mysi, prevedeny a upraveny po uzlech")
window.select_tool("obdelnik")
drag(QPointF(250, 250), QPointF(700, 600))
shapes = window.scene.shapes()
check("obdelnik se nakreslil", len(shapes) == 1 and shapes[0].kind == "rect",
      str([s.kind for s in shapes]))
check("a je rovnou vybrany", shapes[0].isSelected())

window.action_to_path.trigger()
shapes = window.scene.shapes()
check("prevedl se na krivku", len(shapes) == 1 and shapes[0].kind == "path",
      str([s.kind for s in shapes]))
note(f"hlaska: {window.statusBar().currentMessage()}")
curve = shapes[0]
check("ma ctyri uzly", len(path_to_subpaths(curve.path())[0].nodes) == 4)
check("zustal vybrany", curve.isSelected())

window.select_tool("uzly")
tool = view.tool
check("nastroj Uzly je aktivni", isinstance(tool, NodeTool))
check("uzly se nactou hned po prepnuti", tool.shape is curve)

# Obdelnik se pri kresleni prichytil na mrizku, takze hranu si zjistime.
box = curve.scene_path().boundingRect()
note(f"obdelnik je na {box.x():.0f};{box.y():.0f} {box.width():.0f}x{box.height():.0f}")
click(QPointF(box.x() + 4, box.center().y()))
check("klik na hranu nacetl krivku", tool.shape is curve)
check("v nastroji jsou ctyri uzly",
      bool(tool.subpaths) and len(tool.subpaths[0].nodes) == 4)

drag(QPointF(box.x(), box.y()), QPointF(box.x() - 110, box.y() - 110))
new_box = window.scene.shapes()[0].scene_path().boundingRect()
check("tazeni za uzel zmenilo tvar",
      new_box.x() < box.x() - 50 and new_box.y() < box.y() - 50,
      f"roh z {box.x():.0f};{box.y():.0f} na {new_box.x():.0f};{new_box.y():.0f}")

double_click(QPointF(box.right(), box.center().y()))
check("dvojklik pridal uzel",
      len(path_to_subpaths(window.scene.shapes()[0].path())[0].nodes) == 5,
      f"{len(path_to_subpaths(window.scene.shapes()[0].path())[0].nodes)} uzlu")

# ---------------------------------------------------------------------------
case("prevod zachova vzhled")
for popis, vypln in (("s vyplni", QColor("#3498db")), ("bez vyplne", None)):
    style = Style(fill=vypln, stroke=QColor("#000000"), stroke_width=8.0)
    ellipse = add(EllipseShape(QRectF(200, 200, 400, 300), style, "elipsa"), 0)
    before = ellipse.scene_path().boundingRect()
    ellipse.setSelected(True)
    window.convert_to_path()
    shape = window.scene.shapes()[0]
    after = shape.scene_path().boundingRect()
    check(f"elipsa {popis}: vypln se nezmenila",
          (shape.style.fill is None) == (vypln is None))
    check(f"elipsa {popis}: rozmery sedi",
          close(after.width(), before.width(), 1) and close(after.height(),
                                                            before.height(), 1))
    window.scene.removeItem(shape)

case("prevod bez vyberu")
add(RectShape(QRectF(200, 200, 400, 300), VYPLNENY, 0.0, "obdelnik"), 0)
window.scene.clearSelection()
window.action_to_path.trigger()
check("tvar zustal obdelnikem", window.scene.shapes()[0].kind == "rect")
check("editor rekl, ze chybi vyber",
      "vyber" in window.statusBar().currentMessage().lower(),
      window.statusBar().currentMessage())

case("prevod uz prevedeneho")
rect = add(RectShape(QRectF(200, 200, 400, 300), VYPLNENY, 0.0, "obdelnik"), 0)
rect.setSelected(True)
window.action_to_path.trigger()
window.action_to_path.trigger()
check("podruhe to jen oznami", "uz krivka" in window.statusBar().currentMessage(),
      window.statusBar().currentMessage())

raise SystemExit(summary())
