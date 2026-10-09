"""Spolecny zaklad zkousek.

Zkousky bezi bez zobrazeni okna a ovladaji editor stejnymi udalostmi mysi
jako clovek. Diky tomu overuji i cestu pres nastroje a prichytavani, ne
jen vypocty uvnitr.

Pouziti ve zkousce:

    from spolecne import *

    app, window, view = start()

    case("neco se zkousi")
    check("tohle ma platit", podminka)

    raise SystemExit(summary())
"""

from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QEvent, QLineF, QPointF, QRectF, Qt  # noqa: E402,F401
from PySide6.QtGui import (  # noqa: E402,F401
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

from piktoedit import svgio  # noqa: E402,F401
from piktoedit.mainwindow import MainWindow  # noqa: E402
from piktoedit.nodes import locate_point, path_to_subpaths  # noqa: E402,F401
from piktoedit.shapes import (  # noqa: E402,F401
    EllipseShape,
    LineShape,
    PathShape,
    RectShape,
    TextShape,
)
from piktoedit.style import Style  # noqa: E402

#: Bezne styly, at je kazda zkouska nemusi vyrabet znovu.
TAH = Style(fill=None, stroke=QColor("#000000"), stroke_width=10.0)
VYPLNENY = Style(fill=QColor("#3498db"), stroke=QColor("#000000"), stroke_width=8.0)

#: Hlasky, ktere editor poslal do stavoveho radku.
messages: list[str] = []

app = None
window = None
view = None

_problems: list[str] = []
_case = ""


# ---------------------------------------------------------------------------
# Start a vysledky
# ---------------------------------------------------------------------------

def start(width: int = 1200, height: int = 900):
    """Spusti editor bez zobrazeni a vrati (app, window, view)."""
    global app, window, view
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.resize(width, height)
    window.show()
    app.processEvents()
    view = window.view
    view.message.connect(messages.append)
    view.zoom_fit()
    app.processEvents()
    return app, window, view


def case(name: str) -> None:
    """Zacne novy pripad s prazdnou kresbou."""
    global _case
    _case = name
    messages.clear()
    window.undo.stack.setClean()
    window.new_document()
    view.zoom_fit()
    app.processEvents()
    print(f"\n--- {name} ---")


def check(label: str, condition, detail: str = "") -> bool:
    ok = bool(condition)
    print(f"   [{'OK ' if ok else 'CHYBA'}] {label} {detail}")
    if not ok:
        _problems.append(f"{_case}: {label}" if _case else label)
    return ok


def note(text: str) -> None:
    print(f"      {text}")


def last_message() -> str:
    return messages[-1] if messages else ""


def problems() -> list[str]:
    return list(_problems)


def summary() -> int:
    """Vypise souhrn a vrati navratovy kod."""
    print()
    print(f"HOTOVO, problemu: {len(_problems)}")
    for item in _problems:
        print("  -", item)
    return 1 if _problems else 0


# ---------------------------------------------------------------------------
# Udalosti mysi
# ---------------------------------------------------------------------------

def to_view(point: QPointF) -> QPointF:
    """Bod sceny na pixel obrazovky."""
    return QPointF(view.mapFromScene(point))


def send(kind, point: QPointF, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    button = Qt.MouseButton.LeftButton
    buttons = button if kind != QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
    event = QMouseEvent(kind, point, view.viewport().mapToGlobal(point.toPoint()),
                        button, buttons, modifiers)
    {QEvent.Type.MouseButtonPress: view.mousePressEvent,
     QEvent.Type.MouseMove: view.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: view.mouseReleaseEvent}[kind](event)


def click(point: QPointF, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    send(QEvent.Type.MouseButtonPress, to_view(point), modifiers)
    send(QEvent.Type.MouseButtonRelease, to_view(point), modifiers)
    app.processEvents()


def drag(start_point: QPointF, end_point: QPointF, steps: int = 6,
         modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    send(QEvent.Type.MouseButtonPress, to_view(start_point), modifiers)
    for index in range(1, steps + 1):
        ratio = index / steps
        send(QEvent.Type.MouseMove,
             to_view(QPointF(
                 start_point.x() + (end_point.x() - start_point.x()) * ratio,
                 start_point.y() + (end_point.y() - start_point.y()) * ratio)),
             modifiers)
    send(QEvent.Type.MouseButtonRelease, to_view(end_point), modifiers)
    app.processEvents()


def double_click(point: QPointF) -> None:
    click(point)
    event = QMouseEvent(QEvent.Type.MouseButtonDblClick, to_view(point),
                        view.viewport().mapToGlobal(to_view(point).toPoint()),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    view.mouseDoubleClickEvent(event)
    app.processEvents()


# ---------------------------------------------------------------------------
# Nastroje
# ---------------------------------------------------------------------------

def pencil(points: list[QPointF], name: str | None = None):
    """Nakresli tah tuzkou pres udalosti mysi."""
    window.select_tool("tuzka")
    send(QEvent.Type.MouseButtonPress, to_view(points[0]))
    for point in points[1:]:
        send(QEvent.Type.MouseMove, to_view(point))
    send(QEvent.Type.MouseButtonRelease, to_view(points[-1]))
    app.processEvents()
    shape = window.scene.shapes()[-1]
    if name:
        shape.name = name
    return shape


def knife(point: QPointF, jitter: float = 3.0,
          modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    """Klik nozem vcetne cuknuti rukou mezi stiskem a pustenim."""
    window.select_tool("nuz")
    start_point = to_view(point)
    end_point = QPointF(start_point.x() + jitter, start_point.y() - jitter)
    send(QEvent.Type.MouseButtonPress, start_point, modifiers)
    send(QEvent.Type.MouseMove, end_point, modifiers)
    send(QEvent.Type.MouseButtonRelease, end_point, modifiers)
    app.processEvents()


def knife_drag(start_point: QPointF, end_point: QPointF) -> None:
    window.select_tool("nuz")
    send(QEvent.Type.MouseButtonPress, to_view(start_point))
    send(QEvent.Type.MouseMove, to_view(end_point))
    send(QEvent.Type.MouseButtonRelease, to_view(end_point))
    app.processEvents()


def erase(points: list[QPointF], size: float = 40.0,
          modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    window.select_tool("guma")
    view.eraser_size = size
    send(QEvent.Type.MouseButtonPress, to_view(points[0]), modifiers)
    for point in points[1:]:
        send(QEvent.Type.MouseMove, to_view(point), modifiers)
    send(QEvent.Type.MouseButtonRelease, to_view(points[-1]), modifiers)
    app.processEvents()


# ---------------------------------------------------------------------------
# Prace s kresbou
# ---------------------------------------------------------------------------

def add(shape, z: float = 0.0):
    shape.setZValue(z)
    window.scene.addItem(shape)
    return shape


def named(name: str) -> list:
    return [shape for shape in window.scene.shapes() if shape.name == name]


def parts(shape) -> int:
    """Na kolik oddelenych casti je tvar rozpadly."""
    return len(path_to_subpaths(shape.scene_path()))


def gap_to(shape, point: QPointF) -> float:
    """Vzdalenost bodu od osy tvaru."""
    found = locate_point(path_to_subpaths(shape.scene_path()), point)
    return found[2] if found else float("inf")


def nearest_gap(shapes, point: QPointF) -> float:
    return min((gap_to(shape, point) for shape in shapes), default=float("inf"))


def covered(point: QPointF, radius: float = 10.0) -> bool:
    """Je v tom miste jeste neco nakresleno?"""
    box = QRectF(point.x() - radius, point.y() - radius, radius * 2, radius * 2)
    return any(shape.scene_path().intersects(box) for shape in window.scene.shapes())


def spans(shapes, axis: str = "x") -> list:
    """Rozsahy tvaru v dane ose, serazene."""
    out = []
    for shape in shapes:
        box = shape.scene_path().boundingRect()
        out.append((box.x(), box.right()) if axis == "x" else (box.y(), box.bottom()))
    return sorted(out)


def path_length(shape) -> float:
    total = 0.0
    for subpath in path_to_subpaths(shape.scene_path()):
        nodes = subpath.nodes
        for first, second in zip(nodes, nodes[1:]):
            total += math.hypot(first.point.x() - second.point.x(),
                                first.point.y() - second.point.y())
    return total


def close(value: float, target: float, tolerance: float = 12.0) -> bool:
    return abs(value - target) <= tolerance


# ---------------------------------------------------------------------------
# Tvary pro zadani
# ---------------------------------------------------------------------------

def straight(start_point, end_point, steps: int = 20) -> list[QPointF]:
    """Rovny tah o danem poctu bodu."""
    return [QPointF(start_point[0] + (end_point[0] - start_point[0]) * i / steps,
                    start_point[1] + (end_point[1] - start_point[1]) * i / steps)
            for i in range(steps + 1)]


def wobbly(start_point, end_point, steps: int, wobble: float) -> list[QPointF]:
    """Tah jako od ruky: mezi dvema body, s mirnym rozhozenim."""
    points = []
    for index in range(steps + 1):
        ratio = index / steps
        points.append(QPointF(
            start_point[0] + (end_point[0] - start_point[0]) * ratio
            + random.uniform(-wobble, wobble),
            start_point[1] + (end_point[1] - start_point[1]) * ratio
            + random.uniform(-wobble, wobble)))
    return points


def render(name: str, size: int = 420) -> Path:
    """Ulozi obrazek kresby, at jde vysledek prohlednout okem."""
    target = Path(os.environ.get("TEMP", ".")) / f"piktoedit_{name}.png"
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    window.scene.render(painter, QRectF(image.rect()), window.document.rect())
    painter.end()
    image.save(str(target))
    return target
