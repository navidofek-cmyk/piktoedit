"""Nuz: rezani kusu, ktery sam vznikl predchozim rezem.

Takovy kus ma krizeni jen na svych koncich, takze cely lezi mezi reznymi
hranami a ma se odebrat jako celek.
"""

from spolecne import *  # noqa: F403

app, window, view = start()

# ---------------------------------------------------------------------------
case("dva rezy za sebou na stejnem tahu")
pencil(straight((150, 500), (900, 500)))      # hlavni vodorovny tah
pencil(straight((400, 250), (400, 750)))      # prvni rezna hrana
pencil(straight((650, 250), (650, 750)))      # druha rezna hrana

knife(QPointF(520, 500))                      # prostredek pryc
note(f"1. rez: {last_message()}")
check("prostredek zmizel", not covered(QPointF(520, 500), 14))

knife(QPointF(780, 500))                      # pravy zbytek pryc
note(f"2. rez: {last_message()}")
check("pravy zbytek zmizel", not covered(QPointF(780, 500), 14))
check("levy zbytek zustal", covered(QPointF(250, 500), 14))
check("rezne hrany zustaly",
      covered(QPointF(400, 300), 14) and covered(QPointF(650, 300), 14))

# ---------------------------------------------------------------------------
case("kus mezi dvema hranami, ktery uz je samostatny")
pencil(straight((150, 500), (900, 500)))
pencil(straight((400, 250), (400, 750)))
pencil(straight((650, 250), (650, 750)))
knife(QPointF(250, 500))     # odrizneme levy konec
knife(QPointF(800, 500))     # odrizneme pravy konec
check("zbyl jen prostredni kus",
      covered(QPointF(520, 500), 14)
      and not covered(QPointF(250, 500), 14)
      and not covered(QPointF(800, 500), 14))
knife(QPointF(520, 500))     # a ted i prostredek
note(f"3. rez: {last_message()}")
check("i prostredni kus slo odebrat", not covered(QPointF(520, 500), 14))

# ---------------------------------------------------------------------------
case("Y spoj vznikly z rezu")
pencil(straight((200, 760), (820, 200)))      # diagonala
pencil(straight((510, 480), (900, 880)))      # vetev od spoje dolu
knife(QPointF(300, 660))                      # dolni cast diagonaly pryc
note(f"1. rez: {last_message()}")
check("dolni cast pryc", not covered(QPointF(300, 660), 14))
knife(QPointF(700, 320))                      # a ted horni zbytek
note(f"2. rez: {last_message()}")
check("horni zbytek slo odebrat", not covered(QPointF(700, 320), 14))
check("vetev zustala", covered(QPointF(750, 700), 14))

raise SystemExit(summary())
