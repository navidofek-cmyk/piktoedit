"""Nuz: spoj typu Y, kde druhy tah zacina na prvnim."""

from spolecne import *  # noqa: F403

app, window, view = start()

MAIN_A = (200, 760)
MAIN_B = (820, 200)
JOINT = (510, 480)

for nodes, label in ((1, "dva uzly"), (6, "sedm uzlu"), (30, "jemny tah")):
    for offset, popis in ((0, "zacina presne na tahu"),
                          (-10, "zacina 10 px pred tahem"),
                          (14, "prekroci tah o 14 px")):
        case(f"Y spoj, {label}, druhy tah {popis}")
        pencil(straight(MAIN_A, MAIN_B, max(nodes, 1)), "hlavni")
        # Druhy tah vede od spoje dolu doprava; posun ho podel hlavniho tahu.
        shift = offset / 1.414
        pencil(straight((JOINT[0] - shift, JOINT[1] + shift), (900, 880),
                        max(nodes, 1)), "vetev")

        spot = QPointF(700, 320)   # horni cast hlavniho tahu
        knife(spot)
        pieces = named("hlavni")
        note(f"hlaska: {last_message()}")
        check("hlavni zustal jeden kus", len(pieces) == 1, f"{len(pieces)}")
        check("horni cast je pryc", pieces and nearest_gap(pieces, spot) > 40,
              f"{nearest_gap(pieces, spot):.0f} px" if pieces else "nic nezbylo")
        check("vetev se nezmenila", len(named("vetev")) == 1, f"{len(named('vetev'))}")

raise SystemExit(summary())
