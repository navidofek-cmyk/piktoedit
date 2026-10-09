"""Nuz: mene obvykle pripady, ktere zakladni sada nepokryva."""

import math

from spolecne import *  # noqa: F403

app, window, view = start()

# ---------------------------------------------------------------------------
case("tah, ktery se krizi sam se sebou")
loop = pencil([QPointF(500 + 220 * math.cos(t / 10.0), 500 + 220 * math.sin(t / 10.0))
               for t in range(0, 68)], "smycka")
spot = QPointF(500, 280)
knife(spot)
pieces = named("smycka")
note(f"po rezu {len(pieces)} kusu: {last_message()}")
check("neco se stalo", len(pieces) >= 1)
check("kliknute misto je pryc", nearest_gap(pieces, spot) > 20,
      f"{nearest_gap(pieces, spot):.0f} px")

# ---------------------------------------------------------------------------
case("klik u pruseciku, kde je nahore jina cara")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
add(LineShape(QLineF(400, 300, 400, 700), TAH, "rez1"), 5)
add(LineShape(QLineF(600, 300, 600, 700), TAH, "rez2"), 6)
knife(QPointF(430, 500))
check("rezala se hlavni cara", len(named("hlavni")) == 2, f"{len(named('hlavni'))}")
check("svisle cary zustaly cele", len(named("rez1")) == 1 and len(named("rez2")) == 1)

case("klik presne na prusecik")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
add(LineShape(QLineF(400, 300, 400, 700), TAH, "rez1"), 1)
add(LineShape(QLineF(600, 300, 600, 700), TAH, "rez2"), 2)
knife(QPointF(400, 500))
note(f"tvaru: {len(window.scene.shapes())}, hlaska: {last_message()}")
check("editor nespadl a neco udelal", len(window.scene.shapes()) >= 3)

case("rezana cara je nahore nad reznymi hranami")
add(LineShape(QLineF(400, 300, 400, 700), TAH, "rez1"), 0)
add(LineShape(QLineF(600, 300, 600, 700), TAH, "rez2"), 1)
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 9)
knife(QPointF(500, 500))
check("hlavni se orezala", len(named("hlavni")) == 2,
      f"{len(named('hlavni'))}; {last_message()}")

case("rezna hrana konci presne na care")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
add(LineShape(QLineF(400, 200, 400, 500), TAH, "rez1"), 1)
add(LineShape(QLineF(600, 200, 600, 500), TAH, "rez2"), 2)
knife(QPointF(500, 500))
check("T spojeni se bere jako prusecik", len(named("hlavni")) == 2,
      f"{len(named('hlavni'))}; {last_message()}")

# ---------------------------------------------------------------------------
case("dva tahy tuzkou, rez tuzkovym tahem")
pencil([QPointF(120 + i * 20, 500 + (i % 2) * 2) for i in range(40)], "hlavni")
pencil([QPointF(400 + (i % 2) * 2, 250 + i * 12) for i in range(40)])
pencil([QPointF(650 + (i % 2) * 2, 250 + i * 12) for i in range(40)])
knife(QPointF(520, 501))
pieces = named("hlavni")
if check("tah se orezal na dva kusy", len(pieces) == 2, f"{len(pieces)}; {last_message()}"):
    got = spans(pieces)
    check("prostredek je pryc", got[0][1] < 430 and got[1][0] > 620, str(got))

case("klik vedle cary, ale v ramci tloustky tahu")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
add(LineShape(QLineF(400, 300, 400, 700), TAH, "rez1"), 1)
add(LineShape(QLineF(600, 300, 600, 700), TAH, "rez2"), 2)
knife(QPointF(500, 496))
check("trefa i mimo osu tahu", len(named("hlavni")) == 2,
      f"{len(named('hlavni'))}; {last_message()}")

case("klik 25 px vedle cary")
add(LineShape(QLineF(100, 500, 900, 500), TAH, "hlavni"), 0)
add(LineShape(QLineF(400, 300, 400, 700), TAH, "rez1"), 1)
add(LineShape(QLineF(600, 300, 600, 700), TAH, "rez2"), 2)
knife(QPointF(500, 525))
note(f"kusu: {len(named('hlavni'))}, hlaska: {last_message()}")
check("bud orezal, nebo to jasne rekl",
      len(named("hlavni")) == 2 or any("potrebuje krivku" in m for m in messages))

raise SystemExit(summary())
