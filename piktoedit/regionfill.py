"""Vyplneni uzavrene oblasti ohranicene vice tvary.

Vektorove se hranice takove oblasti spocitat neda, protoze ji muze tvorit
nekolik samostatnych car. Kresba se proto vykresli do pomocneho rastru bez
vyhlazovani, tam se najde souvisla plocha kolem kliknuti a jeji obrys se
prevede zpet na krivku.
"""

from __future__ import annotations

from array import array

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPolygonF, QTransform

#: Delsi strana pomocneho rastru. Bezna kresba 1024 px se vykresli 1:1, aby
#: se neztratily tenke cary, ktere plochu deli.
MAX_RASTER = 1400

#: O kolik pixelu rastru se vypln zasune pod obrys, aby nevznikla svetla spara.
DEFAULT_GROW = 2


class FillResult:
    """Vysledek hledani oblasti."""

    def __init__(self, path: QPainterPath | None = None, leaked: bool = False,
                 empty: bool = False):
        self.path = path
        self.leaked = leaked
        self.empty = empty

    @property
    def ok(self) -> bool:
        return self.path is not None and not self.leaked and not self.empty


def raster_scale(width: float, height: float) -> float:
    longest = max(width, height, 1.0)
    return min(1.0, MAX_RASTER / longest)


def render_plain(scene, document, scale: float) -> QImage:
    """Vykresli kresbu bez mrizky, predlohy a vyhlazovani."""
    width = max(1, int(round(document.width * scale)))
    height = max(1, int(round(document.height * scale)))
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#ffffff"))

    reference = getattr(scene, "reference", None)
    reference_visible = reference is not None and reference.isVisible()
    if reference_visible:
        reference.setVisible(False)
    scene.plain_render = True
    try:
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        scene.render(painter, QRectF(image.rect()), document.rect(),
                     Qt.AspectRatioMode.IgnoreAspectRatio)
        painter.end()
    finally:
        scene.plain_render = False
        if reference_visible:
            reference.setVisible(True)
    return image


def find_region(image: QImage, seed: QPoint, grow: int = DEFAULT_GROW,
                simplify_epsilon: float = 0.8) -> FillResult:
    """Najde souvislou plochu stejne barvy kolem bodu ``seed``."""
    width, height = image.width(), image.height()
    if not (0 <= seed.x() < width and 0 <= seed.y() < height):
        return FillResult(empty=True)

    pixels = array("I")
    pixels.frombytes(bytes(image.constBits()))
    if len(pixels) < width * height:
        return FillResult(empty=True)

    target = pixels[seed.y() * width + seed.x()]
    filled = bytearray(width * height)
    runs: dict[int, list[tuple[int, int]]] = {}
    stack = [(seed.x(), seed.y())]
    leaked = False

    while stack:
        x, y = stack.pop()
        row = y * width
        if filled[row + x] or pixels[row + x] != target:
            continue

        left = x
        while left > 0 and not filled[row + left - 1] and pixels[row + left - 1] == target:
            left -= 1
        right = x
        while (right < width - 1 and not filled[row + right + 1]
               and pixels[row + right + 1] == target):
            right += 1
        for index in range(left, right + 1):
            filled[row + index] = 1
        runs.setdefault(y, []).append((left, right))

        if left == 0 or right == width - 1 or y == 0 or y == height - 1:
            # Plocha se dotkla okraje, hranice tedy nekde netesni.
            leaked = True
            break

        for next_y in (y - 1, y + 1):
            if not (0 <= next_y < height):
                continue
            next_row = next_y * width
            index = left
            while index <= right:
                if not filled[next_row + index] and pixels[next_row + index] == target:
                    stack.append((index, next_y))
                    while index <= right and pixels[next_row + index] == target:
                        index += 1
                index += 1

    if leaked:
        return FillResult(leaked=True)
    if not runs:
        return FillResult(empty=True)

    grown = _grow(runs, grow, width, height)
    path = _runs_to_path(grown)
    if path.isEmpty():
        return FillResult(empty=True)
    path = _smooth_steps(path, simplify_epsilon)
    return FillResult(path=path)


def _grow(runs: dict[int, list[tuple[int, int]]], grow: int,
          width: int, height: int) -> dict[int, list[tuple[int, int]]]:
    """Rozsiri plochu do stran i nahoru a dolu o ``grow`` pixelu."""
    if grow <= 0:
        return {y: _merge(intervals) for y, intervals in runs.items()}

    result: dict[int, list[tuple[int, int]]] = {}
    for y, intervals in runs.items():
        for offset in range(-grow, grow + 1):
            target_y = y + offset
            if not (0 <= target_y < height):
                continue
            row = result.setdefault(target_y, [])
            for left, right in intervals:
                row.append((max(0, left - grow), min(width - 1, right + grow)))
    return {y: _merge(intervals) for y, intervals in result.items()}


def _merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    return merged


def _runs_to_path(runs: dict[int, list[tuple[int, int]]]) -> QPainterPath:
    path = QPainterPath()
    for y, intervals in runs.items():
        for left, right in intervals:
            path.addRect(QRectF(left, y, right - left + 1, 1))
    return path.simplified()


def _smooth_steps(path: QPainterPath, epsilon: float) -> QPainterPath:
    """Ze schodovitych obrysu udela primky s rozumnym poctem bodu."""
    if epsilon <= 0:
        return path
    result = QPainterPath()
    for polygon in path.toSubpathPolygons():
        points = [QPointF(point) for point in polygon]
        reduced = simplify_polygon(points, epsilon)
        if len(reduced) >= 3:
            result.addPolygon(QPolygonF(reduced))
    return result if not result.isEmpty() else path


def simplify_polygon(points: list[QPointF], epsilon: float) -> list[QPointF]:
    from .nodes import simplify_points

    if len(points) < 3:
        return points
    closed = abs(points[0].x() - points[-1].x()) < 0.01 and \
        abs(points[0].y() - points[-1].y()) < 0.01
    body = points[:-1] if closed else points
    if len(body) < 3:
        return points
    # Uzavreny obrys rozdelime na dve poloviny, aby zjednoduseni neposunulo
    # zacatek a konec do jednoho bodu.
    half = len(body) // 2
    first = simplify_points(body[:half + 1], epsilon)
    second = simplify_points(body[half:] + [body[0]], epsilon)
    reduced = first[:-1] + second[:-1]
    return reduced + [reduced[0]] if closed else reduced


def image_to_document(path: QPainterPath, scale: float) -> QPainterPath:
    if scale == 1.0:
        return path
    return QTransform.fromScale(1.0 / scale, 1.0 / scale).map(path)
