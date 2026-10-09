"""Nuz: zakladni pripady rezani pres udalosti mysi."""

from spolecne import *  # noqa: F403

app, window, view = start()


def three_lines():
    """Vodorovna cara pretnuta dvema svislymi."""
    main = add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
    add(LineShape(QLineF(400, 300, 400, 700), TAH, "rez1"), 1)
    add(LineShape(QLineF(600, 300, 600, 700), TAH, "rez2"), 2)
    return main


# ---------------------------------------------------------------------------
case("rovna cara, klik na prostredni kus")
three_lines()
knife(QPointF(500, 500))
pieces = named("hlavni")
check("zbyly dva kusy", len(pieces) == 2, f"{len(pieces)}")
if len(pieces) == 2:
    got = spans(pieces)
    check("levy kus 100..400", close(got[0][0], 100) and close(got[0][1], 400), str(got[0]))
    check("pravy kus 600..900", close(got[1][0], 600) and close(got[1][1], 900), str(got[1]))
check("klik je daleko od zbytku", nearest_gap(pieces, QPointF(500, 500)) > 40,
      f"{nearest_gap(pieces, QPointF(500, 500)):.0f} px")

case("rovna cara, klik na levy kus")
three_lines()
knife(QPointF(200, 500))
pieces = named("hlavni")
check("zbyly dva kusy", len(pieces) == 2, f"{len(pieces)}")
if len(pieces) == 2:
    got = spans(pieces)
    check("zbytek 400..600 a 600..900",
          close(got[0][0], 400) and close(got[1][1], 900), str(got))

case("rovna cara, klik na pravy kus")
three_lines()
knife(QPointF(800, 500))
pieces = named("hlavni")
if check("zbyly dva kusy", len(pieces) == 2, f"{len(pieces)}"):
    got = spans(pieces)
    check("zbytek 100..400 a 400..600",
          close(got[0][0], 100) and close(got[1][1], 600), str(got))

# ---------------------------------------------------------------------------
case("jediny prusecik, klik vlevo")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
add(LineShape(QLineF(500, 300, 500, 700), TAH, "rez"), 1)
knife(QPointF(250, 500))
pieces = named("hlavni")
if check("zbyl jeden kus", len(pieces) == 1, f"{len(pieces)}"):
    got = spans(pieces)[0]
    check("zbytek 500..900", close(got[0], 500) and close(got[1], 900), str(got))

case("sikma rezna hrana")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
add(LineShape(QLineF(300, 300, 700, 700), TAH, "rez"), 1)
knife(QPointF(200, 500))
pieces = named("hlavni")
if check("zbyl jeden kus", len(pieces) == 1, f"{len(pieces)}"):
    got = spans(pieces)[0]
    check("zbytek 500..900", close(got[0], 500) and close(got[1], 900), str(got))

# ---------------------------------------------------------------------------
case("vlnovka tuzkou pres vodorovnou caru")
import math  # noqa: E402

# Faze je posunuta, aby tah nezacinal presne na rezne care.
points = [QPointF(150 + i * 15, 500 + 170 * math.sin((i + 2) / 5.5)) for i in range(50)]
wave = pencil(points, "vlnovka")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "rez"), 5)
polygon = list(wave.scene_path().toSubpathPolygons()[0])
expected = sum(1 for a, b in zip(polygon, polygon[1:]) if (a.y() - 500) * (b.y() - 500) < 0)
note(f"vlnovka protina caru {expected}x")
top = min(points, key=lambda p: p.y())
knife(top)
pieces = named("vlnovka")
check("zbyl spravny pocet kusu", len(pieces) == expected,
      f"{len(pieces)} kusu, cekano {expected}")
check("odrezany vrchol uz nikde neni", nearest_gap(pieces, top) > 30,
      f"{nearest_gap(pieces, top):.0f} px")
check("konce vlnovky zustaly",
      nearest_gap(pieces, points[0]) < 5 and nearest_gap(pieces, points[-1]) < 5)

# ---------------------------------------------------------------------------
case("kolecko pretnute svisle, klik vlevo")
add(EllipseShape(QRectF(200, 200, 600, 600), TAH, "kolecko"), 0)
add(LineShape(QLineF(500, 100, 500, 900), TAH, "rez"), 1)
knife(QPointF(205, 500))
pieces = named("kolecko")
if check("zbyl jeden oblouk", len(pieces) == 1, f"{len(pieces)}"):
    box = pieces[0].scene_path().boundingRect()
    check("zbyla prava pulka", close(box.x(), 500) and close(box.right(), 800),
          f"x {box.x():.0f}..{box.right():.0f}")

case("kolecko pretnute svisle, klik vpravo")
add(EllipseShape(QRectF(200, 200, 600, 600), TAH, "kolecko"), 0)
add(LineShape(QLineF(500, 100, 500, 900), TAH, "rez"), 1)
knife(QPointF(795, 500))
pieces = named("kolecko")
if pieces:
    box = pieces[0].scene_path().boundingRect()
    check("zbyla leva pulka", close(box.x(), 200) and close(box.right(), 500),
          f"x {box.x():.0f}..{box.right():.0f}")
else:
    check("zbyl jeden oblouk", False, "nic nezbylo")

case("obdelnik pretnuty vodorovne, klik na horni hranu")
add(RectShape(QRectF(200, 200, 600, 600), TAH, 0.0, "obdelnik"), 0)
add(LineShape(QLineF(100, 500, 900, 500), TAH, "rez"), 1)
knife(QPointF(500, 200))
pieces = named("obdelnik")
if check("zbyl jeden kus", len(pieces) == 1, f"{len(pieces)}"):
    box = pieces[0].scene_path().boundingRect()
    check("horni hrana zmizela", close(box.y(), 500) and close(box.bottom(), 800),
          f"y {box.y():.0f}..{box.bottom():.0f}")

# ---------------------------------------------------------------------------
case("otoceny obdelnik")
rotated = add(RectShape(QRectF(300, 400, 400, 200), TAH, 0.0, "otoceny"), 0)
rotated.setRotation(30.0)
rotated.sync_origin()
add(LineShape(QLineF(500, 100, 500, 900), TAH, "rez"), 1)
before_box = rotated.scene_path().boundingRect()
click_point = QPointF(before_box.x() + 20, before_box.center().y())
knife(click_point)
pieces = named("otoceny")
check("tvar se rozdelil", len(pieces) >= 1, f"{len(pieces)} kusu")
check("klik uz nelezi na zbytku", nearest_gap(pieces, click_point) > 20,
      f"{nearest_gap(pieces, click_point):.0f} px")

# ---------------------------------------------------------------------------
case("Shift+klik jen rozdeli")
three_lines()
knife(QPointF(500, 500), modifiers=Qt.KeyboardModifier.ShiftModifier)
pieces = named("hlavni")
if check("vznikly tri kusy", len(pieces) == 3, f"{len(pieces)}"):
    got = spans(pieces)
    check("kusy navazuji", close(got[0][1], 400) and close(got[1][0], 400)
          and close(got[1][1], 600) and close(got[2][0], 600), str(got))

case("tazeni nozem pres tri cary")
for index, y in enumerate((300, 500, 700)):
    add(LineShape(QLineF(200, y, 800, y), TAH, f"cara{index}"), index)
knife_drag(QPointF(500, 200), QPointF(500, 800))
check("ze tri car je sest kusu", len(window.scene.shapes()) == 6,
      f"{len(window.scene.shapes())}")

case("klik do prazdna")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
knife(QPointF(500, 150))
check("nic se nezmenilo", len(window.scene.shapes()) == 1, f"{len(window.scene.shapes())}")
check("editor to rekl", any("potrebuje krivku" in m for m in messages), str(messages))

case("cara bez krizeni se rozdeli v miste kliku")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
knife(QPointF(400, 500))
pieces = named("hlavni")
if check("vznikly dva kusy", len(pieces) == 2, f"{len(pieces)}"):
    got = spans(pieces)
    check("deli se tam, kam se kliklo", close(got[0][1], 400) and close(got[1][0], 400),
          str(got))

case("vyplneny tvar po rezu vypln ztrati")
add(EllipseShape(QRectF(200, 200, 600, 600), VYPLNENY, "plny"), 0)
add(LineShape(QLineF(500, 100, 500, 900), TAH, "rez"), 1)
knife(QPointF(205, 500))
pieces = named("plny")
check("zbyl oblouk", len(pieces) == 1, f"{len(pieces)}")
check("vypln je pryc", all(p.style.fill is None for p in pieces))
check("obrys zustal", all(p.style.stroke is not None for p in pieces))

case("zpet vrati puvodni caru")
three_lines()
# Tvary pridane primo do sceny musi nejdriv projit do historie.
window.snapshot("priprava")
before = len(window.scene.shapes())
knife(QPointF(500, 500))
after = len(window.scene.shapes())
window.undo.stack.undo()
check("rez pridal krok do historie", after != before, f"{before} -> {after}")
check("zpet vratilo puvodni stav", len(window.scene.shapes()) == before,
      f"{len(window.scene.shapes())}")

for zoom in (0.4, 2.5):
    case(f"stejny rez pri priblizeni {zoom}x")
    three_lines()
    view.zoom_reset()
    view.scale(zoom, zoom)
    view.centerOn(QPointF(500, 500))
    app.processEvents()
    knife(QPointF(500, 500))
    pieces = named("hlavni")
    if check("zbyly dva kusy", len(pieces) == 2, f"{len(pieces)}; {messages}"):
        got = spans(pieces)
        check("kusy sedi", close(got[0][1], 400) and close(got[1][0], 600), str(got))

case("bezierova krivka pretnuta carou")
path = QPainterPath(QPointF(150, 500))
path.cubicTo(350, 200, 650, 800, 880, 500)
add(PathShape(path, TAH, False, "krivka"), 0)
add(LineShape(QLineF(400, 100, 400, 900), TAH, "rez1"), 1)
add(LineShape(QLineF(700, 100, 700, 900), TAH, "rez2"), 2)
knife(QPointF(515, 500))
pieces = named("krivka")
if check("krivka se rozdelila", len(pieces) == 2, f"{len(pieces)}; {messages}"):
    got = spans(pieces)
    check("prostredni cast je pryc", got[0][1] < 460 and got[1][0] > 640, str(got))
check("kusy jsou porad krivky", all(p.kind == "path" for p in pieces))

raise SystemExit(summary())
