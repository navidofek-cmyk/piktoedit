"""Kresleni tuzkou a rez pres skutecne udalosti mysi, vcetne cuknuti ruky."""

from spolecne import *  # noqa: F403

app, window, view = start()

# ---------------------------------------------------------------------------
case("tri tahy tuzkou a rez prostredniho kusu")
pencil([QPointF(100 + i * 25, 500 + (i % 3)) for i in range(33)], "vodorovny")
pencil([QPointF(400 + (i % 2), 250 + i * 12) for i in range(33)], "svisly1")
pencil([QPointF(650 + (i % 2), 250 + i * 12) for i in range(33)], "svisly2")
check("tri tahy tuzkou", len(window.scene.shapes()) == 3,
      f"{len(window.scene.shapes())} tvaru")

horizontal = named("vodorovny")[0]
box = horizontal.scene_path().boundingRect()
note(f"vodorovny tah: x {box.x():.0f}..{box.right():.0f}")

knife(QPointF(520, 500))
pieces = named("vodorovny")
note(f"po rezu {len(window.scene.shapes())} tvaru; {last_message()}")
check("z vodorovneho tahu zbyly dva kusy", len(pieces) == 2, f"{len(pieces)} kusu")
if len(pieces) == 2:
    got = spans(pieces)
    check("prostredni kus zmizel", got[0][1] < 450 and got[1][0] > 600, str(got))
check("svisle tahy zustaly cele",
      len(named("svisly1")) == 1 and len(named("svisly2")) == 1)

# ---------------------------------------------------------------------------
case("vetsi tah nozem uz je rez carou")
pencil([QPointF(100 + i * 25, 500 + (i % 3)) for i in range(33)], "vodorovny")
knife_drag(QPointF(300, 300), QPointF(300, 700))
check("tazeni nozem rozdeli", len(window.scene.shapes()) == 2,
      f"{len(window.scene.shapes())} tvaru; {last_message()}")

# ---------------------------------------------------------------------------
case("cuknuti rukou pri kliku neni tazeni")
pencil([QPointF(100 + i * 25, 500) for i in range(33)], "vodorovny")
pencil([QPointF(400, 250 + i * 12) for i in range(33)], "svisly")
knife(QPointF(600, 500), jitter=4.0)
check("i s cuknutim se orezalo", len(named("vodorovny")) == 1,
      f"{len(named('vodorovny'))} kusu; {last_message()}")

raise SystemExit(summary())
