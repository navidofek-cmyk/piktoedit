"""Nuz: uhel krizeni, blizkost konce tahu a nedojeta rezna hrana."""

import math

from spolecne import *  # noqa: F403

app, window, view = start()


def report(name: str, point: QPointF):
    pieces = named(name)
    note(f"kusu: {len(pieces)}, nejblizsi zbytek "
         f"{nearest_gap(pieces, point):.0f} px, hlaska: {last_message()}")
    return pieces, nearest_gap(pieces, point)


# ---------------------------------------------------------------------------
for angle in (10, 20, 30, 45):
    case(f"krizeni pod uhlem {angle} stupnu")
    pencil(straight((150, 500), (850, 500), 30), "hlavni")
    radians = math.radians(angle)
    half = 350
    pencil(straight((500 - half * math.cos(radians), 500 - half * math.sin(radians)),
                    (500 + half * math.cos(radians), 500 + half * math.sin(radians)), 30),
           "rez")
    spot = QPointF(250, 500)
    knife(spot)
    pieces, gap = report("hlavni", spot)
    check(f"uhel {angle} stupnu: orezalo", len(pieces) == 1 and gap > 40,
          f"{len(pieces)} kusu")

# ---------------------------------------------------------------------------
for offset in (15, 40, 100):
    case(f"krizeni {offset} px od konce tahu")
    pencil(straight((150, 500), (850, 500), 30), "hlavni")
    x = 850 - offset
    pencil(straight((x, 350), (x, 650), 30), "rez")
    spot = QPointF(850 - offset / 2, 500)
    knife(spot)
    pieces, gap = report("hlavni", spot)
    check(f"{offset} px od konce: kratky kus se odreze",
          len(pieces) == 1 and gap > offset / 3, f"{len(pieces)} kusu, {gap:.0f} px")

# ---------------------------------------------------------------------------
for overshoot in (-8, -3, 0, 5, 20):
    case(f"rezna hrana konci {overshoot} px za carou")
    pencil(straight((150, 500), (850, 500), 30), "hlavni")
    pencil(straight((500, 250), (500, 500 + overshoot), 30), "rez")
    spot = QPointF(250, 500)
    knife(spot)
    pieces, gap = report("hlavni", spot)
    check(f"presah {overshoot} px: orezalo", len(pieces) == 1 and gap > 40,
          f"{len(pieces)} kusu, {gap:.0f} px")

raise SystemExit(summary())
