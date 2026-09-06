"""Platno: scena s mrizkou a pohled s uchyty, prichytavanim a zoomem."""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from .nodes import erase_from_outline, erase_from_stroke
from .regionfill import find_region, image_to_document, raster_scale, render_plain
from .shapes import PathShape, ReferenceImage, ShapeMixin, TextShape
from .style import Style
from .svgio import Document

#: Nazvy uchytu kolem vyberu.
HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
ROTATE_HANDLE = "rot"

HANDLE_PIXELS = 9.0
ROTATE_OFFSET_PIXELS = 26.0
SNAP_PIXELS = 12.0

PAGE_MARGIN = 240.0

COLOR_DESK = QColor("#2f333b")
COLOR_GRID = QColor(120, 132, 150, 70)
COLOR_GRID_MAJOR = QColor(120, 132, 150, 130)
COLOR_PAGE_EDGE = QColor("#0f1115")
COLOR_HANDLE = QColor("#ffffff")
COLOR_HANDLE_EDGE = QColor("#1668c1")
COLOR_SELECTION = QColor("#1668c1")
COLOR_SNAP = QColor("#ff8c1a")


class CanvasScene(QGraphicsScene):
    """Scena, ktera zna rozmer stranky a kresli mrizku."""

    def __init__(self, document: Document, parent=None):
        super().__init__(parent)
        self.document = document
        self.show_grid = True
        self.reference: ReferenceImage | None = None
        #: Pri hledani oblasti k vyplneni se kresli jen tvary na bilem podkladu.
        self.plain_render = False
        self.update_page()

    def update_page(self) -> None:
        rect = self.document.rect()
        self.setSceneRect(rect.adjusted(-PAGE_MARGIN, -PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN))
        self.update()

    def shapes(self) -> list[ShapeMixin]:
        items = [item for item in self.items() if isinstance(item, ShapeMixin)]
        items.sort(key=lambda item: item.zValue())
        return items

    def selected_shapes(self) -> list[ShapeMixin]:
        items = [item for item in self.selectedItems() if isinstance(item, ShapeMixin)]
        items.sort(key=lambda item: item.zValue())
        return items

    def next_z(self) -> float:
        shapes = self.shapes()
        return (shapes[-1].zValue() + 1.0) if shapes else 0.0

    # -- pozadi -----------------------------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        if self.plain_render:
            painter.fillRect(rect, QColor("#ffffff"))
            return

        painter.fillRect(rect, COLOR_DESK)
        page = self.document.rect()

        if self.document.background is not None:
            painter.fillRect(page, self.document.background)
        else:
            self._draw_checker(painter, page.intersected(rect))

        if self.show_grid:
            self._draw_grid(painter, rect.intersected(page))

        pen = QPen(COLOR_PAGE_EDGE)
        pen.setCosmetic(True)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(page)

    def _draw_checker(self, painter: QPainter, rect: QRectF) -> None:
        if rect.isEmpty():
            return
        size = 16.0
        painter.fillRect(rect, QColor("#ffffff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e6e8ec"))
        start_x = math.floor(rect.left() / size) * size
        start_y = math.floor(rect.top() / size) * size
        y = start_y
        while y < rect.bottom():
            x = start_x
            while x < rect.right():
                if int((x / size) + (y / size)) % 2 == 0:
                    painter.drawRect(QRectF(x, y, size, size).intersected(rect))
                x += size
            y += size

    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        step = float(self.document.grid_size)
        if step <= 0 or rect.isEmpty():
            return
        scale = painter.transform().m11() or 1.0
        while step * scale < 6.0:
            step *= 2.0

        minor = QPen(COLOR_GRID)
        minor.setCosmetic(True)
        major = QPen(COLOR_GRID_MAJOR)
        major.setCosmetic(True)

        left = math.floor(rect.left() / step) * step
        top = math.floor(rect.top() / step) * step

        x = left
        while x <= rect.right():
            index = round(x / step)
            painter.setPen(major if index % 5 == 0 else minor)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += step
        y = top
        while y <= rect.bottom():
            index = round(y / step)
            painter.setPen(major if index % 5 == 0 else minor)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += step


class CanvasView(QGraphicsView):
    """Pohled na scenu. Vsechny mysi udalosti predava aktivnimu nastroji."""

    mouse_moved = Signal(QPointF)
    zoom_changed = Signal(float)
    tool_done = Signal()
    document_changed = Signal(str)
    #: Nastroj narazil na tvar, ktery je potreba prevest na krivku.
    convert_request = Signal(object)
    #: Kapatko prevzalo barvu, panely se maji obnovit.
    style_picked = Signal()
    #: Hlaska pro stavovy radek.
    message = Signal(str)

    def __init__(self, scene: CanvasScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.canvas_scene = scene
        self.tool = None
        self.default_style = Style()
        self.corner_radius = 0.0
        self.text_font = QFont("Arial", 96, QFont.Weight.Bold)
        self.pending_text_edit = None
        self.eraser_size = 24.0
        #: "prochazi" = krivka jde body, "ridici" = body ji jen ridi (B-spline)
        self.spline_mode = "prochazi"
        self.join_tolerance = 12.0
        self.snap_to_grid = True
        self.snap_to_objects = True
        self.ortho = False
        self.snap_marker: QPointF | None = None
        self.rubber_band: QRectF | None = None
        self.snapshot: Callable[[str], None] = lambda label: None

        self._panning = False
        self._pan_origin = QPointF()
        self._space_down = False

    # -- nastroje ---------------------------------------------------------
    def set_tool(self, tool) -> None:
        if self.tool is not None:
            self.tool.deactivate()
        self.tool = tool
        if tool is not None:
            tool.activate()
            self.setCursor(QCursor(tool.cursor))

    # -- prichytavani -----------------------------------------------------
    def scale_factor(self) -> float:
        return math.sqrt(abs(self.transform().determinant())) or 1.0

    def snap_point(self, point: QPointF, exclude: list | None = None) -> QPointF:
        """Vrati bod prichyceny k objektum nebo mrizce."""
        self.snap_marker = None
        threshold = SNAP_PIXELS / self.scale_factor()

        if self.snap_to_objects:
            best: QPointF | None = None
            best_distance = threshold
            for shape in self.canvas_scene.shapes():
                if exclude and shape in exclude:
                    continue
                for candidate in self._key_points(shape):
                    distance = math.hypot(candidate.x() - point.x(), candidate.y() - point.y())
                    if distance < best_distance:
                        best_distance = distance
                        best = candidate
            if best is not None:
                self.snap_marker = best
                return QPointF(best)

        if self.snap_to_grid:
            step = float(self.canvas_scene.document.grid_size)
            if step > 0:
                return QPointF(round(point.x() / step) * step, round(point.y() / step) * step)
        return QPointF(point)

    def _key_points(self, shape: ShapeMixin) -> list[QPointF]:
        rect = shape.local_rect()
        local = [
            rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight(),
            rect.center(),
            QPointF(rect.center().x(), rect.top()),
            QPointF(rect.center().x(), rect.bottom()),
            QPointF(rect.left(), rect.center().y()),
            QPointF(rect.right(), rect.center().y()),
        ]
        return [shape.mapToScene(point) for point in local]

    def constrain(self, origin: QPointF, point: QPointF) -> QPointF:
        """Ortho rezim: drzi smer po 45 stupnich."""
        dx = point.x() - origin.x()
        dy = point.y() - origin.y()
        if dx == 0 and dy == 0:
            return QPointF(point)
        angle = math.degrees(math.atan2(dy, dx))
        step = round(angle / 45.0) * 45.0
        length = math.hypot(dx, dy)
        radians = math.radians(step)
        return QPointF(origin.x() + math.cos(radians) * length,
                       origin.y() + math.sin(radians) * length)

    # -- uchyty vyberu ----------------------------------------------------
    def selection_shape(self) -> ShapeMixin | None:
        selected = self.canvas_scene.selected_shapes()
        return selected[0] if len(selected) == 1 else None

    def selection_polygon(self) -> QPolygonF | None:
        shape = self.selection_shape()
        if shape is not None:
            return shape.mapToScene(shape.local_rect())
        selected = self.canvas_scene.selected_shapes()
        if not selected:
            return None
        rect = QRectF()
        for item in selected:
            mapped = item.mapToScene(item.local_rect()).boundingRect()
            rect = mapped if rect.isNull() else rect.united(mapped)
        return QPolygonF(rect)

    def handle_positions(self) -> dict[str, QPointF]:
        if self.tool is not None and not self.tool.shows_handles:
            return {}
        shape = self.selection_shape()
        if shape is None:
            return {}
        rect = shape.local_rect()
        local = {
            "nw": rect.topLeft(),
            "n": QPointF(rect.center().x(), rect.top()),
            "ne": rect.topRight(),
            "e": QPointF(rect.right(), rect.center().y()),
            "se": rect.bottomRight(),
            "s": QPointF(rect.center().x(), rect.bottom()),
            "sw": rect.bottomLeft(),
            "w": QPointF(rect.left(), rect.center().y()),
        }
        points = {name: shape.mapToScene(point) for name, point in local.items()}

        offset = ROTATE_OFFSET_PIXELS / self.scale_factor()
        top = QPointF(rect.center().x(), rect.top() - offset)
        points[ROTATE_HANDLE] = shape.mapToScene(top)
        return points

    def handle_at(self, view_pos: QPointF) -> str | None:
        radius = HANDLE_PIXELS
        for name, scene_point in self.handle_positions().items():
            widget_point = self.mapFromScene(scene_point)
            if (abs(widget_point.x() - view_pos.x()) <= radius
                    and abs(widget_point.y() - view_pos.y()) <= radius):
                return name
        return None

    def shape_at(self, view_pos) -> ShapeMixin | None:
        for item in self.items(view_pos.toPoint() if hasattr(view_pos, "toPoint") else view_pos):
            if isinstance(item, ShapeMixin):
                return item
        return None

    # -- guma -------------------------------------------------------------
    def erase_area(self, area: QPainterPath, whole_objects: bool = False) -> bool:
        """Odmaze zadanou plochu z tvaru. Vraci, zda se neco zmenilo."""
        bounds = area.boundingRect()
        changed = False

        for shape in list(self.canvas_scene.shapes()):
            if not shape.sceneBoundingRect().intersects(bounds):
                continue
            scene_path = shape.scene_path()
            if not scene_path.intersects(area):
                continue

            if whole_objects:
                self.canvas_scene.removeItem(shape)
                changed = True
                continue
            if isinstance(shape, TextShape):
                # Text mazeme jen cely, jinak by z nej vznikly nesmyslne kusy.
                continue

            filled = shape.style.fill is not None
            if filled:
                erased = erase_from_outline(scene_path, area)
                closed = True
            else:
                erased = erase_from_stroke(scene_path, area)
                closed = False

            self.canvas_scene.removeItem(shape)
            changed = True
            if erased.elementCount() < 2:
                continue

            replacement = PathShape(erased, shape.style, closed, shape.name)
            replacement.role = shape.role
            replacement.setZValue(shape.zValue())
            self.canvas_scene.addItem(replacement)
        return changed

    # -- vypln oblasti ----------------------------------------------------
    def fill_region(self, scene_pos: QPointF, candidate: ShapeMixin | None = None,
                    force_region: bool = False) -> bool:
        """Vyplni plochu kolem bodu.

        Plocha se hleda vzdy v rastru, aby respektovala i cary, ktere tvar
        deli na casti. Kdyz vyjde presne ta cast, kterou uz nejaky tvar ma,
        prebarvi se rovnou ten tvar - vysledek je pak cistsi nez novy objekt.
        """
        document = self.canvas_scene.document
        color = self.default_style.fill
        if color is None:
            self.message.emit("Aktualni vypln je 'zadna', neni cim vyplnit.")
            return False
        if not document.rect().contains(scene_pos):
            self.message.emit("Kliknuti je mimo kresbu.")
            return False

        scale = raster_scale(document.width, document.height)
        image = render_plain(self.canvas_scene, document, scale)
        seed = QPoint(int(scene_pos.x() * scale), int(scene_pos.y() * scale))
        result = find_region(image, seed)

        if not result.ok:
            if candidate is not None and not force_region:
                self._recolor(candidate, color)
                return True
            if result.leaked:
                self.message.emit(
                    "Oblast neni uzavrena, vypln by pretekla. Zkontroluj mezery "
                    "v obrysu nebo cary spoj pres Objekt / Napojit krivky (Ctrl+J).")
            else:
                self.message.emit("Tady se zadna uzavrena plocha nenasla.")
            return False

        path = image_to_document(result.path, scale)

        if (candidate is not None and not force_region
                and self._region_matches(candidate, path)):
            self._recolor(candidate, color)
            return True

        style = self.default_style.copy()
        style.stroke = None
        shape = PathShape(path, style, True, "Vypln oblasti")
        shape.setZValue(self._fill_depth(scene_pos))
        self.canvas_scene.addItem(shape)
        self.canvas_scene.clearSelection()
        shape.setSelected(True)
        self.snapshot("Vypln oblasti")
        return True

    def _recolor(self, shape: ShapeMixin, color: QColor) -> None:
        style = shape.style.copy()
        style.fill = QColor(color)
        shape.set_style(style)
        self.snapshot("Vypln tvaru")

    def _region_matches(self, shape: ShapeMixin, region: QPainterPath) -> bool:
        """Odpovida nalezena plocha cele vnitrni casti tvaru?"""
        outline = shape.scene_path().boundingRect()
        found = region.boundingRect()
        # Plocha konci uprostred obrysu, proto je o jeho tloustku mensi.
        tolerance = shape.style.stroke_width + 8.0
        return (abs(outline.x() - found.x()) < tolerance
                and abs(outline.y() - found.y()) < tolerance
                and abs(outline.width() - found.width()) < tolerance * 2
                and abs(outline.height() - found.height()) < tolerance * 2)

    def _fill_depth(self, scene_pos: QPointF) -> float:
        """Nova vypln patri nad plochu, do ktere se kreslilo, ale pod obrysy."""
        covering = [shape for shape in self.canvas_scene.shapes()
                    if shape.style.fill is not None
                    and shape.scene_path().contains(scene_pos)]
        if covering:
            return max(shape.zValue() for shape in covering) + 0.5
        lowest = min((shape.zValue() for shape in self.canvas_scene.shapes()), default=0.0)
        return lowest - 1.0

    # -- popredi ----------------------------------------------------------
    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        scale = self.scale_factor()

        if self.rubber_band is not None:
            pen = QPen(COLOR_SELECTION)
            pen.setCosmetic(True)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(22, 104, 193, 40)))
            painter.drawRect(self.rubber_band)

        polygon = self.selection_polygon()
        if polygon is not None:
            pen = QPen(COLOR_SELECTION)
            pen.setCosmetic(True)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(polygon)

        handles = self.handle_positions()
        if handles:
            size = HANDLE_PIXELS / scale
            pen = QPen(COLOR_HANDLE_EDGE)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QBrush(COLOR_HANDLE))
            for name, point in handles.items():
                if name == ROTATE_HANDLE:
                    painter.drawEllipse(point, size / 2.0, size / 2.0)
                else:
                    painter.drawRect(QRectF(point.x() - size / 2.0, point.y() - size / 2.0,
                                            size, size))

        if self.snap_marker is not None:
            pen = QPen(COLOR_SNAP)
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            size = 6.0 / scale
            point = self.snap_marker
            painter.drawRect(QRectF(point.x() - size, point.y() - size, size * 2, size * 2))

        if self.tool is not None:
            self.tool.draw_overlay(painter, scale)

    # -- zoom a posun -----------------------------------------------------
    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if not delta:
            return
        factor = 1.0015 ** delta
        self.zoom_by(factor)

    def zoom_by(self, factor: float) -> None:
        target = self.scale_factor() * factor
        if target < 0.05 or target > 40.0:
            return
        self.scale(factor, factor)
        self.zoom_changed.emit(self.scale_factor())
        self.viewport().update()

    def zoom_reset(self) -> None:
        self.setTransform(QTransform())
        self.zoom_changed.emit(1.0)

    def zoom_fit(self) -> None:
        self.fitInView(self.canvas_scene.document.rect().adjusted(-24, -24, 24, 24),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self.zoom_changed.emit(self.scale_factor())

    # -- udalosti mysi ----------------------------------------------------
    def _positions(self, event) -> tuple[QPointF, QPointF]:
        view_pos = event.position()
        scene_pos = self.mapToScene(view_pos.toPoint())
        return view_pos, scene_pos

    def mousePressEvent(self, event) -> None:
        view_pos, scene_pos = self._positions(event)
        if event.button() == Qt.MouseButton.MiddleButton or self._space_down:
            self._panning = True
            self._pan_origin = view_pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if self.tool is not None and self.tool.mouse_press(event, scene_pos, view_pos):
            self.viewport().update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        view_pos, scene_pos = self._positions(event)
        self.mouse_moved.emit(scene_pos)

        if self._panning:
            delta = view_pos - self._pan_origin
            self._pan_origin = view_pos
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return

        if self.tool is not None and self.tool.mouse_move(event, scene_pos, view_pos):
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        view_pos, scene_pos = self._positions(event)
        if self._panning:
            self._panning = False
            self.setCursor(QCursor(self.tool.cursor if self.tool else Qt.CursorShape.ArrowCursor))
            event.accept()
            return
        if self.tool is not None and self.tool.mouse_release(event, scene_pos, view_pos):
            self.viewport().update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        view_pos, scene_pos = self._positions(event)
        if self.tool is not None and self.tool.double_click(event, scene_pos, view_pos):
            self.viewport().update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if self.tool is not None and self.tool.key_press(event):
            self.viewport().update()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = False
            self.setCursor(QCursor(self.tool.cursor if self.tool else Qt.CursorShape.ArrowCursor))
            event.accept()
            return
        super().keyReleaseEvent(event)
