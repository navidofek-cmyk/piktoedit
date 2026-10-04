"""Nahledy sablon.

Sablona je bezne SVG, takze nahled vznikne tak, ze se nacte a vykresli
stejnym kodem jako kresba na platne.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsScene

from . import svgio

_CACHE: dict[tuple[str, float, int, int], QPixmap] = {}


def _stamp(file: Path) -> float | None:
    try:
        return file.stat().st_mtime
    except OSError:
        return None


def template_parts(path: str | Path) -> list[tuple[int, str]]:
    """Pojmenovane objekty v sablone, ktere jde vlozit samostatne."""
    try:
        _, shapes = svgio.load(Path(path))
    except Exception:  # noqa: BLE001 - rozbita sablona nesmi shodit panel
        return []
    return [(index, shape.name)
            for index, shape in enumerate(shapes)
            if getattr(shape, "role", "") != "caption"]


def part_preview(path: str | Path, index: int, size: int = 104) -> QPixmap | None:
    """Nahled jednoho dilu ze sablony."""
    file = Path(path)
    stamp = _stamp(file)
    if stamp is None:
        return None

    key = (str(file), stamp, size, index)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        _, shapes = svgio.load(file)
    except Exception:  # noqa: BLE001
        return None
    if not 0 <= index < len(shapes):
        return None

    shape = shapes[index]
    scene = QGraphicsScene()
    scene.addItem(shape)
    source = shape.sceneBoundingRect().adjusted(-8, -8, 8, 8)
    if source.isEmpty():
        return None

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, QRectF(image.rect()), source,
                 Qt.AspectRatioMode.KeepAspectRatio)
    painter.end()

    pixmap = QPixmap.fromImage(image)
    _CACHE[key] = pixmap
    scene.clear()
    return pixmap


def template_preview(path: str | Path, size: int = 104) -> QPixmap | None:
    """Vykresli sablonu do ctverecneho nahledu. Vysledky se kesuji."""
    file = Path(path)
    stamp = _stamp(file)
    if stamp is None:
        return None

    key = (str(file), stamp, size, -1)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        document, shapes = svgio.load(file)
    except Exception:  # noqa: BLE001 - nahled nesmi shodit panel
        return None

    scene = QGraphicsScene()
    scene.setSceneRect(document.rect())
    for index, shape in enumerate(shapes):
        shape.setZValue(index)
        scene.addItem(shape)

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(document.background or QColor("#ffffff"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(image.rect()), document.rect(),
                 Qt.AspectRatioMode.KeepAspectRatio)
    painter.end()

    pixmap = QPixmap.fromImage(image)
    _CACHE[key] = pixmap
    scene.clear()
    return pixmap
