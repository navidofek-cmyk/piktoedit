"""Guma pres udalosti mysi."""

from spolecne import *  # noqa: F403

app, window, view = start()

# ---------------------------------------------------------------------------
case("guma pres caru ji rozdeli")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "cara"))
erase([QPointF(500, 400), QPointF(500, 600)], size=60)
shapes = window.scene.shapes()
check("tvar zustal jeden", len(shapes) == 1, f"{len(shapes)}")
if shapes:
    check("cara je na dve casti", parts(shapes[0]) == 2, f"{parts(shapes[0])}")
check("v miste gumy uz nic neni", not covered(QPointF(500, 500), 6))
check("kraje zustaly",
      covered(QPointF(150, 500), 6) and covered(QPointF(850, 500), 6))

case("guma ubere kus z vyplneneho tvaru")
add(RectShape(QRectF(200, 200, 600, 600), VYPLNENY, 0.0, "ctverec"))
erase([QPointF(500, 150), QPointF(500, 850)], size=80)
shapes = window.scene.shapes()
check("tvar zustal", len(shapes) == 1, f"{len(shapes)}")
if shapes:
    check("ctverec je rozdeleny na dve casti", parts(shapes[0]) == 2, f"{parts(shapes[0])}")
    check("vypln zustala", shapes[0].style.fill is not None)
check("prostredek je vymazany", not covered(QPointF(500, 500), 6))
check("boky zustaly",
      covered(QPointF(250, 500), 6) and covered(QPointF(750, 500), 6))

case("Shift maze cely objekt")
add(RectShape(QRectF(200, 200, 300, 300), VYPLNENY, 0.0, "a"), 0)
add(RectShape(QRectF(600, 600, 200, 200), VYPLNENY, 0.0, "b"), 1)
erase([QPointF(300, 300), QPointF(320, 320)], size=30,
      modifiers=Qt.KeyboardModifier.ShiftModifier)
names = sorted(shape.name for shape in window.scene.shapes())
check("prvni tvar je pryc, druhy zustal", names == ["b"], str(names))

case("guma mimo tvary nic neudela")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "cara"))
erase([QPointF(200, 150), QPointF(800, 150)], size=40)
check("kresba beze zmeny", len(window.scene.shapes()) == 1)
check("cara je cela", parts(window.scene.shapes()[0]) == 1)

case("guma smaze maly tvar uplne")
add(EllipseShape(QRectF(480, 480, 40, 40), VYPLNENY, "tecka"))
erase([QPointF(470, 500), QPointF(530, 500)], size=90)
check("tecka zmizela", len(window.scene.shapes()) == 0, f"{len(window.scene.shapes())}")

case("guma na tahu tuzkou")
pencil([QPointF(120 + i * 20, 500) for i in range(40)], "tah")
erase([QPointF(500, 420), QPointF(500, 580)], size=70)
shapes = window.scene.shapes()
check("tah zustal jeden tvar", len(shapes) == 1, f"{len(shapes)}")
if shapes:
    check("tah je na dve casti", parts(shapes[0]) == 2, f"{parts(shapes[0])}")
check("stred je vymazany", not covered(QPointF(500, 500), 6))

# ---------------------------------------------------------------------------
for size, expected in ((20.0, 20), (120.0, 120)):
    case(f"guma o prumeru {size:.0f} px")
    add(LineShape(QLineF(100, 500, 900, 500), TAH, "cara"))
    erase([QPointF(500, 480), QPointF(500, 520)], size=size)
    shapes = window.scene.shapes()
    pieces = path_to_subpaths(shapes[0].scene_path()) if shapes else []
    if len(pieces) == 2:
        hole = abs(max(p.start().x() for p in pieces)
                   - min(p.end().x() for p in pieces))
        check(f"dira je kolem {expected} px", abs(hole - expected) < expected * 0.6,
              f"dira {hole:.0f} px")
    else:
        check("cara se rozdelila", False, f"{len(pieces)} casti")

case("guma pri jinem priblizeni")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "cara"))
view.zoom_reset()
view.scale(2.2, 2.2)
view.centerOn(QPointF(500, 500))
app.processEvents()
erase([QPointF(500, 470), QPointF(500, 530)], size=60)
shapes = window.scene.shapes()
check("rozdelila i pri priblizeni", shapes and parts(shapes[0]) == 2,
      f"{parts(shapes[0]) if shapes else 0}")

case("guma na otocenem tvaru")
rotated = add(RectShape(QRectF(300, 420, 400, 160), VYPLNENY, 0.0, "otoceny"))
rotated.setRotation(25.0)
rotated.sync_origin()
erase([QPointF(500, 300), QPointF(500, 700)], size=70)
shapes = window.scene.shapes()
check("tvar se rozdelil", shapes and parts(shapes[0]) >= 2,
      f"{parts(shapes[0]) if shapes else 0}")
check("stred je vymazany", not covered(QPointF(500, 500), 6))

case("text guma nechava byt, se Shiftem ho smaze")
text = add(TextShape("AHOJ", Style(fill=QColor("#000000"), stroke=None),
                     QFont("Arial", 120), "popis"))
text.setPos(300, 450)
erase([QPointF(300, 500), QPointF(700, 500)], size=60)
check("text prezil bezne gumovani", len(window.scene.shapes()) == 1,
      f"{len(window.scene.shapes())}")
erase([QPointF(300, 500), QPointF(700, 500)], size=60,
      modifiers=Qt.KeyboardModifier.ShiftModifier)
check("se Shiftem text zmizel", len(window.scene.shapes()) == 0,
      f"{len(window.scene.shapes())}")

case("zpet vrati vygumovane")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "cara"))
window.snapshot("priprava")
before = parts(window.scene.shapes()[0])
erase([QPointF(500, 400), QPointF(500, 600)], size=60)
after = parts(window.scene.shapes()[0])
window.undo.stack.undo()
check("guma rozdelila", before == 1 and after == 2, f"{before} -> {after}")
check("zpet vratilo celou caru", parts(window.scene.shapes()[0]) == 1,
      f"{parts(window.scene.shapes()[0])}")

raise SystemExit(summary())
