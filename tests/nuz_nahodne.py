"""Nuz: nahodne kresby.

Pro kazdou kresbu se overi, ze se odebral prave kus pod kurzorem, ze se
nezmenil zadny jiny tah a ze po rezu nezustal nepatrny drobek.

Pouziti:  python nuz_nahodne.py [zarodek] [pocet kol]
"""

import random
import sys

from spolecne import *  # noqa: F403

app, window, view = start(1100, 900)

random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 20261005)
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 220

failures: list[str] = []
stats = {"orez": 0, "rozdeleno": 0, "nic": 0}

for round_index in range(ROUNDS):
    window.undo.stack.setClean()
    window.new_document()
    view.zoom_fit()
    messages.clear()

    width = random.uniform(4.0, 18.0)
    style = Style(fill=None, stroke=QColor("#000000"), stroke_width=width)

    main_points = wobbly((random.uniform(80, 200), random.uniform(350, 650)),
                         (random.uniform(820, 960), random.uniform(350, 650)),
                         random.randint(4, 40), random.uniform(0, 14))
    main = add(PathShape(PathShape.from_points(main_points, style, False).path(),
                         style, False, "hlavni"), 0)

    cutters = random.randint(1, 3)
    for index in range(cutters):
        x = random.uniform(250, 800)
        cut_style = Style(fill=None, stroke=QColor("#000000"),
                          stroke_width=random.uniform(4.0, 18.0))
        points = wobbly((x, random.uniform(150, 300)),
                        (x + random.uniform(-80, 80), random.uniform(620, 760)),
                        random.randint(2, 20), random.uniform(0, 8))
        add(PathShape(PathShape.from_points(points, cut_style, False).path(),
                      cut_style, False, f"rez{index}"), index + 1)

    subpath = path_to_subpaths(main.path())[0]
    from piktoedit.nodes import point_at
    param = random.uniform(0.1, len(subpath.nodes) - 1.1)
    spot = main.mapToScene(point_at(subpath, param))
    # Aplikace dostane bod zaokrouhleny na pixel obrazovky.
    spot = view.mapToScene(to_view(spot).toPoint())

    window.select_tool("nuz")
    tool = view.tool
    # Nuz si cil vybira sam; kontroluje se ten, ktery opravdu zvolil.
    target = tool._nearest_curve(spot) or view.shape_at(view.mapFromScene(spot))
    target_name = target.name if target else "(nic)"
    crossings = tool._crossings(target) if target else []
    plan = tool._plan_cut(target, spot, crossings) if target else None
    expected_crossings = plan[3] if plan else 0
    to_crossing = min((gap_to(main, point) * 0 + ((spot.x() - point.x()) ** 2
                       + (spot.y() - point.y()) ** 2) ** 0.5 for point in crossings),
                      default=float("inf"))

    others_before = {shape.name: path_length(shape) for shape in window.scene.shapes()
                     if shape.name != target_name}
    main_box = target.scene_path().boundingRect() if target else None
    main_length = path_length(target) if target else 0.0

    knife(spot)
    pieces = named(target_name)

    def fail(reason: str) -> None:
        failures.append(f"kolo {round_index}: {reason} | sirka {width:.1f},"
                        f" krizeni {expected_crossings}, kusu {len(pieces)},"
                        f" klik {to_crossing:.1f} px od krizeni, cil '{target_name}'")

    if expected_crossings > 0:
        stats["orez"] += 1
        if not pieces:
            if plan and len(plan[1]) > 1:
                fail("po orezu nezbylo nic")
        else:
            limit = 10.0 if to_crossing > 12.0 else 0.0
            if limit and nearest_gap(pieces, spot) < limit:
                fail("kliknute misto zustalo nedotcene")
            if sum(path_length(piece) for piece in pieces) > main_length - 1.0:
                fail("nic se neodebralo")
            for piece in pieces:
                box = piece.scene_path().boundingRect()
                if not main_box.adjusted(-6, -6, 6, 6).contains(box):
                    fail("kus vybehl mimo puvodni tah")
                    break
            for piece in pieces:
                if path_length(piece) < width * 0.9:
                    fail(f"zbyl drobek dlouhy {path_length(piece):.1f} px")
                    break
    elif plan is not None:
        stats["rozdeleno"] += 1
        if len(pieces) < 2:
            fail("bez krizeni se tah nerozdelil")
    else:
        stats["nic"] += 1

    others_after = {shape.name: path_length(shape) for shape in window.scene.shapes()
                    if shape.name != target_name}
    if set(others_before) != set(others_after):
        fail("zmizela nebo pribyla rezna hrana")
    else:
        for name, length in others_before.items():
            if abs(others_after[name] - length) > 1.0:
                fail(f"rezna hrana {name} se zmenila")
                break

print(f"kol: {ROUNDS}, z toho orez {stats['orez']}, pouhe rozdeleni "
      f"{stats['rozdeleno']}, bez efektu {stats['nic']}")
print()
print(f"HOTOVO, problemu: {len(failures)}")
for item in failures[:25]:
    print("  -", item)
raise SystemExit(1 if failures else 0)
