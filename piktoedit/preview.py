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

_CACHE: dict[tuple[str, float, int], QPixmap] = {}


def template_preview(path: str | Path, size: int = 104) -> QPixmap | None:
    """Vykresli sablonu do ctverecneho nahledu. Vysledky se kesuji."""
    file = Path(path)
    try:
        stamp = file.stat().st_mtime
    except OSError:
        return None

    key = (str(file), stamp, size)
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
