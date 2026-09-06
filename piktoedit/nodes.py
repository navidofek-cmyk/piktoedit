"""Geometrie krivek: uzly, hladke krivky, napojeni, orezani a guma.

Cesta se pro editaci prevadi na seznam uzlu. Kazdy uzel ma svuj bod a
volitelne dve ridici ramena, stejne jako v bezne vektorove grafice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtCore import QLineF, QPointF
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QPolygonF

EPS = 0.01


@dataclass
class Node:
    """Jeden uzel krivky."""

    point: QPointF
    handle_in: QPointF | None = None
    handle_out: QPointF | None = None

    def copy(self) -> "Node":
        return Node(
            QPointF(self.point),
            QPointF(self.handle_in) if self.handle_in is not None else None,
            QPointF(self.handle_out) if self.handle_out is not None else None,
        )

    def move_to(self, target: QPointF) -> None:
        delta = target - self.point
        self.point = QPointF(target)
        if self.handle_in is not None:
            self.handle_in = self.handle_in + delta
        if self.handle_out is not None:
            self.handle_out = self.handle_out + delta

    def is_smooth(self) -> bool:
        if self.handle_in is None or self.handle_out is None:
            return False
        first = self.point - self.handle_in
        second = self.handle_out - self.point
        cross = first.x() * second.y() - first.y() * second.x()
        return abs(cross) < 1.0

    def make_smooth(self) -> None:
        """Srovna ramena do jedne primky."""
        if self.handle_in is None and self.handle_out is None:
            return
        if self.handle_in is None:
            self.handle_in = self.point - (self.handle_out - self.point)
            return
        if self.handle_out is None:
            self.handle_out = self.point - (self.handle_in - self.point)
            return
        direction = self.handle_out - self.handle_in
        length = math.hypot(direction.x(), direction.y())
        if length < EPS:
            return
        unit = QPointF(direction.x() / length, direction.y() / length)
        len_in = math.hypot((self.point - self.handle_in).x(),
                            (self.point - self.handle_in).y())
        len_out = math.hypot((self.handle_out - self.point).x(),
                             (self.handle_out - self.point).y())
        self.handle_in = self.point - unit * len_in
        self.handle_out = self.point + unit * len_out

    def make_corner(self) -> None:
        self.handle_in = None
        self.handle_out = None


@dataclass
class SubPath:
    nodes: list[Node] = field(default_factory=list)
    closed: bool = False

    def copy(self) -> "SubPath":
        return SubPath([node.copy() for node in self.nodes], self.closed)

    def reversed(self) -> "SubPath":
        nodes = []
        for node in reversed(self.nodes):
            flipped = node.copy()
            flipped.handle_in, flipped.handle_out = node.handle_out, node.handle_in
            nodes.append(flipped)
        return SubPath(nodes, self.closed)

    def start(self) -> QPointF:
        return self.nodes[0].point

    def end(self) -> QPointF:
        return self.nodes[-1].point


# ---------------------------------------------------------------------------
# Prevod cesta <-> uzly
# ---------------------------------------------------------------------------

def path_to_subpaths(path: QPainterPath) -> list[SubPath]:
    subpaths: list[SubPath] = []
    current: SubPath | None = None
    index = 0
    count = path.elementCount()

    while index < count:
        element = path.elementAt(index)
        if element.type == QPainterPath.ElementType.MoveToElement:
            current = SubPath([Node(QPointF(element.x, element.y))])
            subpaths.append(current)
            index += 1
        elif element.type == QPainterPath.ElementType.LineToElement:
            if current is None:
                current = SubPath([Node(QPointF(element.x, element.y))])
                subpaths.append(current)
            else:
                current.nodes.append(Node(QPointF(element.x, element.y)))
            index += 1
        elif element.type == QPainterPath.ElementType.CurveToElement and index + 2 < count:
            control1 = element
            control2 = path.elementAt(index + 1)
            end = path.elementAt(index + 2)
            if current is None:
                current = SubPath([Node(QPointF(control1.x, control1.y))])
                subpaths.append(current)
            current.nodes[-1].handle_out = QPointF(control1.x, control1.y)
            current.nodes.append(
                Node(QPointF(end.x, end.y), handle_in=QPointF(control2.x, control2.y)))
            index += 3
        else:
            index += 1

    for subpath in subpaths:
        if len(subpath.nodes) > 2 and _same(subpath.nodes[0].point, subpath.nodes[-1].point):
            last = subpath.nodes.pop()
            subpath.nodes[0].handle_in = last.handle_in
            subpath.closed = True
    return [subpath for subpath in subpaths if subpath.nodes]


def subpaths_to_path(subpaths: list[SubPath]) -> QPainterPath:
    path = QPainterPath()
    for subpath in subpaths:
        nodes = subpath.nodes
        if not nodes:
            continue
        path.moveTo(nodes[0].point)
        pairs = list(zip(nodes, nodes[1:]))
        if subpath.closed and len(nodes) > 1:
            pairs.append((nodes[-1], nodes[0]))
        for start, end in pairs:
            if start.handle_out is not None or end.handle_in is not None:
                path.cubicTo(start.handle_out or start.point,
                             end.handle_in or end.point,
                             end.point)
            else:
                path.lineTo(end.point)
        if subpath.closed:
            path.closeSubpath()
    return path


def _same(a: QPointF, b: QPointF, tolerance: float = 0.05) -> bool:
    return abs(a.x() - b.x()) <= tolerance and abs(a.y() - b.y()) <= tolerance


def distance(a: QPointF, b: QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())


# ---------------------------------------------------------------------------
# Hladke krivky
# ---------------------------------------------------------------------------

def catmull_rom(points: list[QPointF], closed: bool = False,
                tension: float = 1.0) -> SubPath:
    """Krivka, ktera prochazi zadanymi body."""
    if len(points) < 2:
        return SubPath([Node(QPointF(p)) for p in points], closed)

    count = len(points)
    nodes = [Node(QPointF(point)) for point in points]

    def at(index: int) -> QPointF:
        if closed:
            return points[index % count]
        return points[max(0, min(count - 1, index))]

    last = count if closed else count - 1
    for i in range(last):
        p0, p1, p2, p3 = at(i - 1), at(i), at(i + 1), at(i + 2)
        control1 = p1 + (p2 - p0) * (tension / 6.0)
        control2 = p2 - (p3 - p1) * (tension / 6.0)
        nodes[i].handle_out = control1
        nodes[(i + 1) % count].handle_in = control2
    if not closed:
        nodes[0].handle_in = None
        nodes[-1].handle_out = None
    return SubPath(nodes, closed)


def bspline(points: list[QPointF], closed: bool = False) -> SubPath:
    """Uniformni kubicky B-spline: body jsou ridici, krivka jimi neprochazi.

    Prevod na bezierove segmenty je presny, jde o jinou parametrizaci teze
    krivky.
    """
    if len(points) < 3:
        return SubPath([Node(QPointF(point)) for point in points], closed)

    count = len(points)

    def at(index: int) -> QPointF:
        if closed:
            return points[index % count]
        return points[max(0, min(count - 1, index))]

    spans = count if closed else count - 3
    if spans <= 0:
        return catmull_rom(points, closed)

    nodes: list[Node] = []
    for i in range(spans):
        p0, p1, p2, p3 = at(i), at(i + 1), at(i + 2), at(i + 3)
        start = (p0 + p1 * 4.0 + p2) / 6.0
        control1 = (p1 * 2.0 + p2) / 3.0
        control2 = (p1 + p2 * 2.0) / 3.0
        end = (p1 + p2 * 4.0 + p3) / 6.0
        if not nodes:
            nodes.append(Node(QPointF(start)))
        nodes[-1].handle_out = control1
        nodes.append(Node(QPointF(end), handle_in=control2))

    if closed and len(nodes) > 1 and _same(nodes[0].point, nodes[-1].point):
        last = nodes.pop()
        nodes[0].handle_in = last.handle_in
        return SubPath(nodes, True)
    return SubPath(nodes, closed)


def split_cubic(p0: QPointF, c1: QPointF, c2: QPointF, p3: QPointF, t: float):
    """De Casteljau: rozdeli kubiku na dve v parametru t."""
    a = p0 + (c1 - p0) * t
    b = c1 + (c2 - c1) * t
    c = c2 + (p3 - c2) * t
    d = a + (b - a) * t
    e = b + (c - b) * t
    point = d + (e - d) * t
    return (a, d, point), (e, c, point)


def nearest_on_segment(start: Node, end: Node, target: QPointF,
                       samples: int = 40) -> tuple[float, float]:
    """Vrati parametr t a vzdalenost nejblizsiho bodu segmentu."""
    has_curve = start.handle_out is not None or end.handle_in is not None
    best_t, best_distance = 0.0, float("inf")
    for index in range(samples + 1):
        t = index / samples
        if has_curve:
            point = _cubic_at(start.point, start.handle_out or start.point,
                              end.handle_in or end.point, end.point, t)
        else:
            point = start.point + (end.point - start.point) * t
        current = distance(point, target)
        if current < best_distance:
            best_distance = current
            best_t = t
    return best_t, best_distance


def _cubic_at(p0: QPointF, c1: QPointF, c2: QPointF, p3: QPointF, t: float) -> QPointF:
    u = 1.0 - t
    return (p0 * (u * u * u) + c1 * (3 * u * u * t)
            + c2 * (3 * u * t * t) + p3 * (t * t * t))


def insert_node(subpath: SubPath, index: int, t: float) -> int:
    """Vlozi uzel do segmentu mezi ``index`` a nasledujicim uzlem."""
    nodes = subpath.nodes
    start = nodes[index]
    end = nodes[(index + 1) % len(nodes)]

    if start.handle_out is None and end.handle_in is None:
        point = start.point + (end.point - start.point) * t
        nodes.insert(index + 1, Node(point))
        return index + 1

    left, right = split_cubic(start.point, start.handle_out or start.point,
                              end.handle_in or end.point, end.point, t)
    start.handle_out = left[0]
    end.handle_in = right[1]
    middle = Node(left[2], handle_in=left[1], handle_out=right[0])
    nodes.insert(index + 1, middle)
    return index + 1


# ---------------------------------------------------------------------------
# Napojeni
# ---------------------------------------------------------------------------

def join_subpaths(subpaths: list[SubPath], tolerance: float) -> list[SubPath]:
    """Spoji otevrene casti, jejichz konce lezi blizko sebe."""
    open_parts = [part for part in subpaths if not part.closed and len(part.nodes) > 1]
    result = [part for part in subpaths if part.closed or len(part.nodes) <= 1]
    if not open_parts:
        return result

    chains = [open_parts.pop(0)]
    while open_parts:
        chain = chains[-1]
        best = None
        for index, candidate in enumerate(open_parts):
            options = (
                (distance(chain.end(), candidate.start()), index, False, True),
                (distance(chain.end(), candidate.end()), index, True, True),
                (distance(chain.start(), candidate.end()), index, False, False),
                (distance(chain.start(), candidate.start()), index, True, False),
            )
            for gap, idx, flip, append in options:
                if gap <= tolerance and (best is None or gap < best[0]):
                    best = (gap, idx, flip, append)
        if best is None:
            chains.append(open_parts.pop(0))
            continue

        _, index, flip, append = best
        part = open_parts.pop(index)
        if flip:
            part = part.reversed()
        if append:
            merged = _concat(chain, part)
        else:
            merged = _concat(part, chain)
        chains[-1] = merged

    for chain in chains:
        if len(chain.nodes) > 2 and distance(chain.start(), chain.end()) <= tolerance:
            last = chain.nodes.pop()
            chain.nodes[0].handle_in = last.handle_in
            chain.closed = True
        result.append(chain)
    return result


def _concat(first: SubPath, second: SubPath) -> SubPath:
    nodes = [node.copy() for node in first.nodes]
    tail = [node.copy() for node in second.nodes]
    # Konce, ktere lezi na sobe, slucujeme do jednoho uzlu.
    if nodes and tail and distance(nodes[-1].point, tail[0].point) < 1.0:
        nodes[-1].handle_out = tail[0].handle_out
        tail = tail[1:]
    nodes.extend(tail)
    return SubPath(nodes, False)


# ---------------------------------------------------------------------------
# Orezani a guma
# ---------------------------------------------------------------------------

def stroke_area(path: QPainterPath, width: float) -> QPainterPath:
    """Plocha, kterou by cara zabrala pri dane sirce."""
    from PySide6.QtCore import Qt

    stroker = QPainterPathStroker()
    stroker.setWidth(max(0.1, width))
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return stroker.createStroke(path)


def erase_from_outline(path: QPainterPath, area: QPainterPath) -> QPainterPath:
    """Vymaze plochu z vyplneneho tvaru."""
    return path.subtracted(area).simplified()


def erase_from_stroke(path: QPainterPath, area: QPainterPath) -> QPainterPath:
    """Rozdeli caru tam, kde ji guma prejela."""
    result = QPainterPath()
    for polygon in path.toSubpathPolygons():
        run: list[QPointF] = []
        for point in polygon:
            if area.contains(point):
                if len(run) > 1:
                    _append_polyline(result, run)
                run = []
            else:
                run.append(QPointF(point))
        if len(run) > 1:
            _append_polyline(result, run)
    return result


def _append_polyline(path: QPainterPath, points: list[QPointF]) -> None:
    path.moveTo(points[0])
    for point in points[1:]:
        path.lineTo(point)


# ---------------------------------------------------------------------------
# Rezani krivek
# ---------------------------------------------------------------------------

def flatten_segments(path: QPainterPath, epsilon: float = 0.4) -> list[QLineF]:
    """Krivku rozlozi na kratke usecky, na kterych se hledaji pruseciky."""
    segments: list[QLineF] = []
    for polygon in path.toSubpathPolygons():
        points = simplify_points([QPointF(point) for point in polygon], epsilon)
        for start, end in zip(points, points[1:]):
            if distance(start, end) > 1e-6:
                segments.append(QLineF(start, end))
    return segments


def path_intersections(first: QPainterPath, second: QPainterPath) -> list[QPointF]:
    """Body, ve kterych se dve krivky protinaji."""
    if not first.boundingRect().intersects(second.boundingRect()):
        return []

    others = flatten_segments(second)
    points: list[QPointF] = []
    for line in flatten_segments(first):
        x1, x2 = sorted((line.x1(), line.x2()))
        y1, y2 = sorted((line.y1(), line.y2()))
        for other in others:
            if (max(other.x1(), other.x2()) < x1 - 0.5
                    or min(other.x1(), other.x2()) > x2 + 0.5
                    or max(other.y1(), other.y2()) < y1 - 0.5
                    or min(other.y1(), other.y2()) > y2 + 0.5):
                continue
            kind, point = line.intersects(other)
            if kind == QLineF.IntersectionType.BoundedIntersection:
                if all(distance(point, found) > 0.7 for found in points):
                    points.append(QPointF(point))
    return points


def locate_point(subpaths: list[SubPath], target: QPointF) -> tuple[int, float, float] | None:
    """Najde nejblizsi misto na krivce: cast, parametr a vzdalenost.

    Parametr je "globalni": cele cislo je poradi segmentu, desetinna cast
    poloha uvnitr nej.
    """
    best: tuple[int, float, float] | None = None
    for index, subpath in enumerate(subpaths):
        nodes = subpath.nodes
        count = len(nodes)
        if count < 2:
            continue
        last = count if subpath.closed else count - 1
        for segment in range(last):
            end = nodes[(segment + 1) % count]
            t, gap = nearest_on_segment(nodes[segment], end, target)
            if best is None or gap < best[2]:
                best = (index, segment + t, gap)
    return best


def split_subpath(subpath: SubPath, cuts: list[float]) -> list[SubPath]:
    """Rozdeli cast krivky v zadanych globalnich parametrech."""
    values = sorted({round(value, 6) for value in cuts})
    if not values:
        return [subpath.copy()]

    work = subpath.copy()
    if work.closed:
        work = _open_at(work, values[0])
        # Po rozstrihnuti smycky se ostatni rezy posunuly o prvni rez.
        shift = values[0]
        total = len(subpath.nodes)
        values = [(value - shift) % total for value in values[1:]]
        values = sorted(value for value in values if value > 1e-6)
        if not values:
            return [work]

    pieces: list[SubPath] = []
    for value in reversed(values):
        head, tail = _split_once(work, value)
        if tail is not None and len(tail.nodes) > 1:
            pieces.insert(0, tail)
        work = head
    if len(work.nodes) > 1:
        pieces.insert(0, work)
    return pieces or [subpath.copy()]


def _split_once(subpath: SubPath, value: float) -> tuple[SubPath, SubPath | None]:
    nodes = subpath.nodes
    index = int(value)
    t = value - index
    if index >= len(nodes) - 1 and t <= 1e-6:
        return subpath, None
    if index < 0:
        return subpath, None

    if t <= 1e-6:
        cut = index
    elif t >= 1.0 - 1e-6:
        cut = index + 1
    else:
        cut = insert_node(subpath, index, t)

    if cut <= 0 or cut >= len(nodes) - 1:
        return subpath, None
    head = SubPath([node.copy() for node in nodes[:cut + 1]], False)
    tail = SubPath([node.copy() for node in nodes[cut:]], False)
    head.nodes[-1].handle_out = None
    tail.nodes[0].handle_in = None
    return head, tail


def _open_at(subpath: SubPath, value: float) -> SubPath:
    """Ze smycky udela otevrenou krivku zacinajici v miste rezu."""
    index = int(value)
    t = value - index
    work = subpath.copy()
    if t > 1e-6:
        index = insert_node(work, index, t)
    nodes = work.nodes
    rotated = [node.copy() for node in nodes[index:]] + [node.copy() for node in nodes[:index]]
    closing = nodes[index].copy()
    closing.handle_out = None
    rotated.append(closing)
    rotated[0].handle_in = None
    return SubPath(rotated, False)


def simplify_points(points: list[QPointF], epsilon: float) -> list[QPointF]:
    """Ramer-Douglas-Peucker: zredukuje body a nechá tvar cary."""
    if len(points) < 3:
        return list(points)

    start, end = points[0], points[-1]
    length = distance(start, end)
    index = 0
    farthest = 0.0

    for i in range(1, len(points) - 1):
        point = points[i]
        if length == 0:
            current = distance(start, point)
        else:
            current = abs((end.x() - start.x()) * (start.y() - point.y())
                          - (start.x() - point.x()) * (end.y() - start.y())) / length
        if current > farthest:
            farthest = current
            index = i

    if farthest <= epsilon:
        return [start, end]
    left = simplify_points(points[:index + 1], epsilon)
    right = simplify_points(points[index:], epsilon)
    return left[:-1] + right


def polygon_to_path(polygon: QPolygonF) -> QPainterPath:
    path = QPainterPath()
    if polygon.isEmpty():
        return path
    path.addPolygon(polygon)
    return path
