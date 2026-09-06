"""Kreslici a editacni nastroje."""

from __future__ import annotations

import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem

from .nodes import (
    Node,
    SubPath,
    bspline,
    catmull_rom,
    distance,
    insert_node,
    locate_point,
    nearest_on_segment,
    path_intersections,
    path_to_subpaths,
    simplify_points,
    split_subpath,
    stroke_area,
    subpaths_to_path,
)
from .shapes import (
    EllipseShape,
    LineShape,
    PathShape,
    RectShape,
    ShapeMixin,
    TextShape,
    to_path_shape,
)

MIN_DRAG = 2.0


class Tool:
    """Spolecne rozhrani nastroju."""

    name = "nastroj"
    cursor = Qt.CursorShape.ArrowCursor
    #: Po dokresleni se editor vraci na sipku.
    one_shot = False
    #: Uchyty pro zmenu velikosti kresli jen sipka, jinde by matly.
    shows_handles = False

    def __init__(self, view):
        self.view = view

    @property
    def scene(self):
        return self.view.canvas_scene

    @property
    def style(self):
        return self.view.default_style

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        self.cancel()

    def cancel(self) -> None:
        pass

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        return False

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        return False

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        return False

    def double_click(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        return False

    def key_press(self, event) -> bool:
        return False

    def draw_overlay(self, painter: QPainter, scale: float) -> None:
        pass

    # -- pomocne ----------------------------------------------------------
    def snap(self, scene_pos: QPointF, exclude=None) -> QPointF:
        return self.view.snap_point(scene_pos, exclude)

    def add_shape(self, shape: ShapeMixin, label: str) -> None:
        shape.setZValue(self.scene.next_z())
        self.scene.addItem(shape)
        self.scene.clearSelection()
        shape.setSelected(True)
        self.view.snapshot(label)
        if self.one_shot:
            self.view.tool_done.emit()

    def finish(self) -> None:
        if self.one_shot:
            self.view.tool_done.emit()


class SelectTool(Tool):
    """Vyber, posun, zmena velikosti a otaceni."""

    name = "vyber"
    cursor = Qt.CursorShape.ArrowCursor
    shows_handles = True

    def __init__(self, view):
        super().__init__(view)
        self.mode = "idle"
        self.handle: str | None = None
        self.start_scene = QPointF()
        self.start_rect = QRectF()
        self.start_positions: dict[ShapeMixin, QPointF] = {}
        self.start_angle = 0.0
        self.start_rotation = 0.0
        self.active_shape: ShapeMixin | None = None
        self.editing: TextShape | None = None
        self.moved = False

    def deactivate(self) -> None:
        self.stop_editing()
        super().deactivate()

    def cancel(self) -> None:
        self.mode = "idle"
        self.view.rubber_band = None
        self.view.snap_marker = None

    # -- editace textu ----------------------------------------------------
    def start_editing(self, item: TextShape) -> None:
        self.stop_editing()
        self.editing = item
        self._text_before = item.toPlainText()
        item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        item.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = item.textCursor()
        cursor.select(cursor.SelectionType.Document)
        item.setTextCursor(cursor)

    def stop_editing(self) -> None:
        item = self.editing
        if item is None:
            return
        self.editing = None
        item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item.clearFocus()
        item.sync_origin()
        if item.toPlainText() != getattr(self, "_text_before", None):
            if not item.toPlainText().strip():
                self.scene.removeItem(item)
                self.view.snapshot("Smazani textu")
            else:
                item.name = item.toPlainText().strip()[:24]
                self.view.snapshot("Zmena textu")

    # -- mys --------------------------------------------------------------
    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        if self.editing is not None:
            if self.view.shape_at(view_pos) is self.editing:
                return False  # klik uvnitr textu resi Qt
            self.stop_editing()

        self.moved = False
        handle = self.view.handle_at(view_pos)
        shape = self.view.shape_at(view_pos)

        if handle is not None:
            self.active_shape = self.view.selection_shape()
            if self.active_shape is not None:
                self.handle = handle
                self.start_scene = scene_pos
                self.start_rect = QRectF(self.active_shape.local_rect())
                self.start_rotation = self.active_shape.rotation()
                center = self.active_shape.scene_center()
                self.start_angle = math.degrees(
                    math.atan2(scene_pos.y() - center.y(), scene_pos.x() - center.x()))
                self.mode = "rotate" if handle == "rot" else "resize"
                return True

        modifiers = event.modifiers()
        additive = bool(modifiers & (Qt.KeyboardModifier.ShiftModifier
                                     | Qt.KeyboardModifier.ControlModifier))

        if shape is not None:
            if additive:
                shape.setSelected(not shape.isSelected())
            elif not shape.isSelected():
                self.scene.clearSelection()
                shape.setSelected(True)
            self.mode = "move"
            self.start_scene = scene_pos
            self.start_positions = {item: QPointF(item.pos())
                                    for item in self.scene.selected_shapes()}
            self.active_shape = shape
            return True

        if not additive:
            self.scene.clearSelection()
        self.mode = "band"
        self.start_scene = scene_pos
        self.view.rubber_band = QRectF(scene_pos, scene_pos)
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.mode == "idle":
            handle = self.view.handle_at(view_pos)
            if handle == "rot":
                self.view.setCursor(Qt.CursorShape.CrossCursor)
            elif handle in ("nw", "se"):
                self.view.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif handle in ("ne", "sw"):
                self.view.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif handle in ("n", "s"):
                self.view.setCursor(Qt.CursorShape.SizeVerCursor)
            elif handle in ("e", "w"):
                self.view.setCursor(Qt.CursorShape.SizeHorCursor)
            elif self.view.shape_at(view_pos) is not None:
                self.view.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.view.setCursor(self.cursor)
            return False

        self.moved = True

        if self.mode == "band":
            band = QRectF(self.start_scene, scene_pos).normalized()
            self.view.rubber_band = band
            for shape in self.scene.shapes():
                touched = band.intersects(shape.mapToScene(shape.local_rect()).boundingRect())
                shape.setSelected(touched)
            return True

        if self.mode == "move":
            shapes = list(self.start_positions)
            target = self.snap(scene_pos, exclude=shapes)
            delta = target - self.start_scene
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if abs(delta.x()) > abs(delta.y()):
                    delta.setY(0.0)
                else:
                    delta.setX(0.0)
            for item, origin in self.start_positions.items():
                item.setPos(origin + delta)
            return True

        if self.mode == "resize" and self.active_shape is not None:
            self._resize(event, scene_pos)
            return True

        if self.mode == "rotate" and self.active_shape is not None:
            center = self.active_shape.scene_center()
            angle = math.degrees(math.atan2(scene_pos.y() - center.y(),
                                            scene_pos.x() - center.x()))
            rotation = self.start_rotation + (angle - self.start_angle)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                rotation = round(rotation / 15.0) * 15.0
            self.active_shape.setRotation(rotation)
            return True
        return False

    def _resize(self, event, scene_pos: QPointF) -> None:
        shape = self.active_shape
        assert shape is not None
        snapped = self.snap(scene_pos, exclude=[shape])
        local = shape.mapFromScene(snapped)
        rect = QRectF(self.start_rect)

        left, top = rect.left(), rect.top()
        right, bottom = rect.right(), rect.bottom()
        if "w" in self.handle:
            left = min(local.x(), right - 1.0)
        if "e" in self.handle:
            right = max(local.x(), left + 1.0)
        if "n" in self.handle:
            top = min(local.y(), bottom - 1.0)
        if "s" in self.handle:
            bottom = max(local.y(), top + 1.0)

        new_rect = QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()

        keep_ratio = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if keep_ratio and self.handle in ("nw", "ne", "se", "sw") and self.start_rect.height():
            ratio = self.start_rect.width() / self.start_rect.height()
            height = new_rect.height()
            width = height * ratio
            if "w" in self.handle:
                new_rect.setLeft(new_rect.right() - width)
            else:
                new_rect.setRight(new_rect.left() + width)

        shape.set_local_rect(new_rect)

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.mode == "idle":
            return False
        mode = self.mode
        self.mode = "idle"
        self.view.rubber_band = None
        self.view.snap_marker = None
        self.handle = None
        self.start_positions = {}

        if self.moved:
            if mode == "move":
                self.view.snapshot("Posun")
            elif mode == "resize":
                self.view.snapshot("Zmena velikosti")
            elif mode == "rotate":
                self.view.snapshot("Otoceni")
        self.moved = False
        return True

    def double_click(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        shape = self.view.shape_at(view_pos)
        if isinstance(shape, TextShape):
            self.start_editing(shape)
            return True
        return False

    def key_press(self, event) -> bool:
        if self.editing is not None:
            if event.key() == Qt.Key.Key_Escape:
                self.stop_editing()
                return True
            return False

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.scene.clearSelection()
            return True

        step = float(self.scene.document.grid_size) or 1.0
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = 1.0
        deltas = {
            Qt.Key.Key_Left: QPointF(-step, 0.0),
            Qt.Key.Key_Right: QPointF(step, 0.0),
            Qt.Key.Key_Up: QPointF(0.0, -step),
            Qt.Key.Key_Down: QPointF(0.0, step),
        }
        if key in deltas:
            shapes = self.scene.selected_shapes()
            if not shapes:
                return False
            for shape in shapes:
                shape.setPos(shape.pos() + deltas[key])
            self.view.snapshot("Posun")
            return True
        return False


class DragShapeTool(Tool):
    """Zaklad pro nastroje kreslene tazenim mysi."""

    label = "Kresleni"

    def __init__(self, view):
        super().__init__(view)
        self.origin: QPointF | None = None
        self.preview: ShapeMixin | None = None

    def cancel(self) -> None:
        if self.preview is not None and self.preview.scene() is not None:
            self.scene.removeItem(self.preview)
        self.preview = None
        self.origin = None
        self.view.snap_marker = None

    def create(self, origin: QPointF) -> ShapeMixin:
        raise NotImplementedError

    def update_preview(self, origin: QPointF, point: QPointF) -> None:
        raise NotImplementedError

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self.origin = self.snap(scene_pos)
        self.preview = self.create(self.origin)
        self.preview.setZValue(self.scene.next_z())
        self.scene.addItem(self.preview)
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.origin is None or self.preview is None:
            return False
        point = self.snap(scene_pos, exclude=[self.preview])
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            point = self.constrain_point(self.origin, point)
        self.update_preview(self.origin, point)
        return True

    def constrain_point(self, origin: QPointF, point: QPointF) -> QPointF:
        size = max(abs(point.x() - origin.x()), abs(point.y() - origin.y()))
        return QPointF(origin.x() + math.copysign(size, point.x() - origin.x()),
                       origin.y() + math.copysign(size, point.y() - origin.y()))

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.origin is None or self.preview is None:
            return False
        shape = self.preview
        rect = shape.local_rect()
        self.preview = None
        self.origin = None
        self.view.snap_marker = None
        if rect.width() < MIN_DRAG and rect.height() < MIN_DRAG:
            self.scene.removeItem(shape)
            return True
        shape.sync_origin()
        self.scene.clearSelection()
        shape.setSelected(True)
        self.view.snapshot(self.label)
        self.finish()
        return True

    def key_press(self, event) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        return False


class RectTool(DragShapeTool):
    name = "obdelnik"
    label = "Obdelnik"
    cursor = Qt.CursorShape.CrossCursor

    def create(self, origin: QPointF) -> ShapeMixin:
        shape = RectShape(QRectF(origin, origin), self.style, self.view.corner_radius)
        return shape

    def update_preview(self, origin: QPointF, point: QPointF) -> None:
        self.preview.set_local_rect(QRectF(origin, point).normalized())


class EllipseTool(DragShapeTool):
    name = "elipsa"
    label = "Elipsa"
    cursor = Qt.CursorShape.CrossCursor

    def create(self, origin: QPointF) -> ShapeMixin:
        return EllipseShape(QRectF(origin, origin), self.style)

    def update_preview(self, origin: QPointF, point: QPointF) -> None:
        self.preview.set_local_rect(QRectF(origin, point).normalized())


class LineTool(DragShapeTool):
    name = "cara"
    label = "Cara"
    cursor = Qt.CursorShape.CrossCursor

    def create(self, origin: QPointF) -> ShapeMixin:
        style = self.style.copy()
        style.fill = None
        return LineShape(QLineF(origin, origin), style)

    def constrain_point(self, origin: QPointF, point: QPointF) -> QPointF:
        return self.view.constrain(origin, point)

    def update_preview(self, origin: QPointF, point: QPointF) -> None:
        self.preview.setLine(QLineF(origin, point))

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.preview is not None:
            line = self.preview.line()
            if line.length() < MIN_DRAG:
                self.scene.removeItem(self.preview)
                self.preview = None
                self.origin = None
                return True
        return super().mouse_release(event, scene_pos, view_pos)


class PolylineTool(Tool):
    """Lomena cara nebo mnohouhelnik: klikani bod po bodu."""

    name = "lomena"
    cursor = Qt.CursorShape.CrossCursor
    closed = False
    label = "Lomena cara"

    def __init__(self, view):
        super().__init__(view)
        self.points: list[QPointF] = []
        self.cursor_point: QPointF | None = None

    def cancel(self) -> None:
        self.points = []
        self.cursor_point = None
        self.view.snap_marker = None
        self.view.viewport().update()

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.RightButton:
            self.commit()
            return True
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        point = self.snap(scene_pos)
        if self.points and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            point = self.view.constrain(self.points[-1], point)
        if self.points and QLineF(self.points[0], point).length() < 8.0 / self.view.scale_factor():
            self.commit(force_closed=True)
            return True
        self.points.append(point)
        self.cursor_point = point
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if not self.points:
            return False
        point = self.snap(scene_pos)
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            point = self.view.constrain(self.points[-1], point)
        self.cursor_point = point
        return True

    def double_click(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        self.commit()
        return True

    def key_press(self, event) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.commit()
            return True
        if key == Qt.Key.Key_Backspace and self.points:
            self.points.pop()
            return True
        return False

    def commit(self, force_closed: bool = False) -> None:
        points = list(self.points)
        self.cancel()
        if len(points) < 2:
            return
        style = self.style.copy()
        closed = self.closed or force_closed
        if not closed:
            style.fill = None
        shape = PathShape.from_points(points, style, closed=closed)
        self.add_shape(shape, self.label)

    def draw_overlay(self, painter: QPainter, scale: float) -> None:
        if not self.points:
            return
        pen = QPen(QColor("#1668c1"))
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(self.points[0])
        for point in self.points[1:]:
            path.lineTo(point)
        if self.cursor_point is not None:
            path.lineTo(self.cursor_point)
        painter.drawPath(path)

        size = 4.0 / scale
        painter.setBrush(QColor("#ffffff"))
        for point in self.points:
            painter.drawRect(QRectF(point.x() - size, point.y() - size, size * 2, size * 2))


class PolygonTool(PolylineTool):
    name = "mnohouhelnik"
    closed = True
    label = "Mnohouhelnik"


class PencilTool(Tool):
    """Kresleni od ruky s naslednym zjednodusenim bodu."""

    name = "tuzka"
    cursor = Qt.CursorShape.CrossCursor
    label = "Kresba od ruky"

    def __init__(self, view):
        super().__init__(view)
        self.points: list[QPointF] = []
        self.preview: PathShape | None = None

    def cancel(self) -> None:
        if self.preview is not None and self.preview.scene() is not None:
            self.scene.removeItem(self.preview)
        self.preview = None
        self.points = []

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        style = self.style.copy()
        style.fill = None
        self.points = [scene_pos]
        self.preview = PathShape.from_points([scene_pos, scene_pos], style)
        self.preview.setZValue(self.scene.next_z())
        self.scene.addItem(self.preview)
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.preview is None:
            return False
        if QLineF(self.points[-1], scene_pos).length() < 1.5 / self.view.scale_factor():
            return True
        self.points.append(scene_pos)
        path = QPainterPath(self.points[0])
        for point in self.points[1:]:
            path.lineTo(point)
        self.preview.setPath(path)
        return True

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.preview is None:
            return False
        points = simplify_points(self.points, 1.2 / self.view.scale_factor())
        self.scene.removeItem(self.preview)
        self.preview = None
        self.points = []
        if len(points) < 2:
            return True
        style = self.style.copy()
        style.fill = None
        shape = PathShape.from_points(points, style)
        self.add_shape(shape, self.label)
        return True

    def key_press(self, event) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        return False


class TextTool(Tool):
    """Klik vlozi text a rovnou ho da do editace."""

    name = "text"
    cursor = Qt.CursorShape.IBeamCursor
    one_shot = True

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        style = self.style.copy()
        style.fill = QColor(style.stroke or QColor("#000000"))
        style.stroke = None
        font = QFont(self.view.text_font)
        shape = TextShape("TEXT", style, font)
        shape.setPos(self.snap(scene_pos))
        shape.sync_origin()
        self.add_shape(shape, "Vlozeni textu")
        self.view.pending_text_edit = shape
        return True


class CurveTool(Tool):
    """Pero: klik prida roh, tazeni pri kliku vytvori hladky uzel."""

    name = "krivka"
    cursor = Qt.CursorShape.CrossCursor
    label = "Krivka"

    def __init__(self, view):
        super().__init__(view)
        self.nodes: list[Node] = []
        self.cursor_point: QPointF | None = None
        self.dragging = False

    def cancel(self) -> None:
        self.nodes = []
        self.cursor_point = None
        self.dragging = False
        self.view.snap_marker = None
        self.view.viewport().update()

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.RightButton:
            self.commit(False)
            return True
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        point = self.snap(scene_pos)
        if self.nodes and distance(point, self.nodes[0].point) < 10.0 / self.view.scale_factor():
            self.commit(True)
            return True
        self.nodes.append(Node(point))
        self.cursor_point = point
        self.dragging = True
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if not self.nodes:
            return False
        self.cursor_point = scene_pos
        if self.dragging:
            node = self.nodes[-1]
            handle = scene_pos
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                handle = self.view.constrain(node.point, handle)
            node.handle_out = QPointF(handle)
            node.handle_in = node.point - (handle - node.point)
        return True

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if not self.dragging:
            return False
        self.dragging = False
        return True

    def double_click(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        self.commit(False)
        return True

    def key_press(self, event) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.commit(False)
            return True
        if key == Qt.Key.Key_Backspace and self.nodes:
            self.nodes.pop()
            return True
        return False

    def commit(self, closed: bool) -> None:
        nodes = [node.copy() for node in self.nodes]
        self.cancel()
        if len(nodes) < 2:
            return
        style = self.style.copy()
        if not closed:
            style.fill = None
        path = subpaths_to_path([SubPath(nodes, closed)])
        self.add_shape(PathShape(path, style, closed), self.label)

    def draw_overlay(self, painter: QPainter, scale: float) -> None:
        if not self.nodes:
            return
        preview = [node.copy() for node in self.nodes]
        if self.cursor_point is not None and not self.dragging:
            preview.append(Node(QPointF(self.cursor_point)))
        path = subpaths_to_path([SubPath(preview, False)])

        pen = QPen(QColor("#1668c1"))
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        _draw_nodes(painter, scale, self.nodes, None)


class SplineTool(PolylineTool):
    """Hladka krivka. Rezim se prepina v horni liste."""

    name = "spline"
    label = "Hladka krivka"

    def commit(self, force_closed: bool = False) -> None:
        points = list(self.points)
        self.cancel()
        if len(points) < 2:
            return
        closed = force_closed
        style = self.style.copy()
        if not closed:
            style.fill = None
        if self.view.spline_mode == "ridici":
            subpath = bspline(points, closed)
        else:
            subpath = catmull_rom(points, closed)
        path = subpaths_to_path([subpath])
        self.add_shape(PathShape(path, style, closed), self.label)

    def draw_overlay(self, painter: QPainter, scale: float) -> None:
        super().draw_overlay(painter, scale)
        if len(self.points) < 2:
            return
        points = list(self.points)
        if self.cursor_point is not None:
            points.append(self.cursor_point)
        if self.view.spline_mode == "ridici":
            subpath = bspline(points, False)
        else:
            subpath = catmull_rom(points, False)
        pen = QPen(QColor("#e67e22"))
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(subpaths_to_path([subpath]))


class NodeTool(Tool):
    """Editace krivky po uzlech vcetne ridicich ramen."""

    name = "uzly"
    cursor = Qt.CursorShape.ArrowCursor

    def __init__(self, view):
        super().__init__(view)
        self.shape: PathShape | None = None
        self.subpaths: list[SubPath] = []
        self.selected: tuple[int, int] | None = None
        self.drag: tuple[str, int, int] | None = None
        self.changed = False

    def activate(self) -> None:
        selected = self.scene.selected_shapes()
        if selected and isinstance(selected[0], PathShape):
            self.load(selected[0])

    def cancel(self) -> None:
        self.shape = None
        self.subpaths = []
        self.selected = None
        self.drag = None

    def load(self, shape: PathShape) -> None:
        self.shape = shape
        self.subpaths = path_to_subpaths(shape.path())
        self.selected = None
        self.scene.clearSelection()
        shape.setSelected(True)

    def rebuild(self) -> None:
        if self.shape is None:
            return
        self.shape.setPath(subpaths_to_path(self.subpaths))
        self.shape.closed = any(part.closed for part in self.subpaths)
        self.shape.sync_origin()

    # -- hledani uchopeneho prvku ----------------------------------------
    def _hit(self, scene_pos: QPointF) -> tuple[str, int, int] | None:
        if self.shape is None:
            return None
        threshold = 9.0 / self.view.scale_factor()
        local = self.shape.mapFromScene(scene_pos)

        if self.selected is not None:
            si, ni = self.selected
            node = self.subpaths[si].nodes[ni]
            for kind, handle in (("handle_in", node.handle_in),
                                 ("handle_out", node.handle_out)):
                if handle is not None and distance(handle, local) <= threshold:
                    return (kind, si, ni)

        for si, subpath in enumerate(self.subpaths):
            for ni, node in enumerate(subpath.nodes):
                if distance(node.point, local) <= threshold:
                    return ("node", si, ni)
        return None

    def _segment_at(self, scene_pos: QPointF) -> tuple[int, int, float] | None:
        if self.shape is None:
            return None
        threshold = 8.0 / self.view.scale_factor()
        local = self.shape.mapFromScene(scene_pos)
        best = None
        for si, subpath in enumerate(self.subpaths):
            nodes = subpath.nodes
            pairs = list(range(len(nodes) - 1))
            if subpath.closed and len(nodes) > 1:
                pairs.append(len(nodes) - 1)
            for ni in pairs:
                end = nodes[(ni + 1) % len(nodes)]
                t, gap = nearest_on_segment(nodes[ni], end, local)
                if gap <= threshold and (best is None or gap < best[3]):
                    best = (si, ni, t, gap)
        return best[:3] if best else None

    # -- mys --------------------------------------------------------------
    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        hit = self._hit(scene_pos)
        if hit is not None:
            kind, si, ni = hit
            if kind == "node":
                self.selected = (si, ni)
            self.drag = hit
            self.changed = False
            return True

        shape = self.view.shape_at(view_pos)
        if isinstance(shape, PathShape):
            if shape is not self.shape:
                self.load(shape)
            else:
                self.selected = None
            return True
        if shape is not None:
            self.view.convert_request.emit(shape)
            return True

        self.cancel()
        self.scene.clearSelection()
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.drag is None or self.shape is None:
            return False
        kind, si, ni = self.drag
        node = self.subpaths[si].nodes[ni]
        target = self.shape.mapFromScene(self.snap(scene_pos, exclude=[self.shape]))

        if kind == "node":
            node.move_to(target)
        elif kind == "handle_in":
            node.handle_in = target
            if node.is_smooth() or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                node.handle_out = node.point - (target - node.point)
        else:
            node.handle_out = target
            if node.is_smooth() or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                node.handle_in = node.point - (target - node.point)

        self.changed = True
        self.rebuild()
        return True

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.drag is None:
            return False
        self.drag = None
        self.view.snap_marker = None
        if self.changed:
            self.view.snapshot("Uprava uzlu")
        self.changed = False
        return True

    def double_click(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        found = self._segment_at(scene_pos)
        if found is None or self.shape is None:
            return False
        si, ni, t = found
        index = insert_node(self.subpaths[si], ni, t)
        self.selected = (si, index)
        self.rebuild()
        self.view.snapshot("Pridani uzlu")
        return True

    def key_press(self, event) -> bool:
        if self.shape is None or self.selected is None:
            return False
        si, ni = self.selected
        subpath = self.subpaths[si]
        key = event.key()

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if len(subpath.nodes) <= 2:
                return False
            subpath.nodes.pop(ni)
            self.selected = None
            self.rebuild()
            self.view.snapshot("Smazani uzlu")
            return True
        if key == Qt.Key.Key_S:
            node = subpath.nodes[ni]
            if node.handle_in is None and node.handle_out is None:
                previous = subpath.nodes[(ni - 1) % len(subpath.nodes)]
                following = subpath.nodes[(ni + 1) % len(subpath.nodes)]
                direction = (following.point - previous.point) / 4.0
                node.handle_in = node.point - direction
                node.handle_out = node.point + direction
            else:
                node.make_smooth()
            self.rebuild()
            self.view.snapshot("Hladky uzel")
            return True
        if key == Qt.Key.Key_C:
            subpath.nodes[ni].make_corner()
            self.rebuild()
            self.view.snapshot("Rohovy uzel")
            return True
        if key == Qt.Key.Key_Escape:
            self.selected = None
            return True

        step = float(self.scene.document.grid_size) or 1.0
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = 1.0
        deltas = {
            Qt.Key.Key_Left: QPointF(-step, 0.0),
            Qt.Key.Key_Right: QPointF(step, 0.0),
            Qt.Key.Key_Up: QPointF(0.0, -step),
            Qt.Key.Key_Down: QPointF(0.0, step),
        }
        if key in deltas:
            node = subpath.nodes[ni]
            node.move_to(node.point + deltas[key])
            self.rebuild()
            self.view.snapshot("Posun uzlu")
            return True
        return False

    def draw_overlay(self, painter: QPainter, scale: float) -> None:
        if self.shape is None:
            return
        painter.save()
        painter.setTransform(self.shape.sceneTransform(), True)
        for si, subpath in enumerate(self.subpaths):
            selected = self.selected[1] if (self.selected and self.selected[0] == si) else None
            _draw_nodes(painter, scale, subpath.nodes, selected)
        painter.restore()


class FillTool(Tool):
    """Kyblik.

    Nejdriv zkusi prebarvit tvar pod kurzorem, protoze to da ciste vektorovy
    vysledek. Az kdyz tam zadny tvar neni, hleda plochu ohranicenou vice
    carami a vyrobi pro ni novou vypln.
    """

    name = "vypln"
    cursor = Qt.CursorShape.PointingHandCursor

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        modifiers = event.modifiers()
        shape = self.view.shape_at(view_pos)

        if modifiers & Qt.KeyboardModifier.AltModifier:
            if shape is None:
                return True
            # Kapatko: prevezme barvu z tvaru.
            picked = shape.style.copy()
            self.view.default_style.fill = picked.fill
            self.view.default_style.stroke = picked.stroke
            self.view.default_style.stroke_width = picked.stroke_width
            self.view.style_picked.emit()
            return True

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            if shape is None:
                return True
            style = shape.style.copy()
            style.stroke = (QColor(self.view.default_style.stroke)
                            if self.view.default_style.stroke else None)
            shape.set_style(style)
            self.view.snapshot("Prebarveni obrysu")
            return True

        force_region = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        # Uzavreny tvar bez vyplne se kliknutim dovnitr netrefi, nema co
        # zasahnout; najdeme ho podle obrysu.
        candidate = shape if shape is not None else self._hollow_shape_at(scene_pos)
        self.view.fill_region(scene_pos, candidate=candidate, force_region=force_region)
        return True

    def _hollow_shape_at(self, scene_pos: QPointF) -> ShapeMixin | None:
        candidates = []
        for shape in self.scene.shapes():
            if shape.style.fill is not None:
                continue
            if isinstance(shape, (LineShape, TextShape)):
                continue
            if isinstance(shape, PathShape) and not shape.closed:
                continue
            if shape.scene_path().contains(scene_pos):
                candidates.append(shape)
        return max(candidates, key=lambda item: item.zValue()) if candidates else None


class CutTool(Tool):
    """Nuz: reze krivky v mistech, kde se krizi s jinymi.

    Klik odebere kousek pod kurzorem, Shift+klik krivku jen rozdeli a tazeni
    rozreze vsechno, co cara protne.
    """

    name = "nuz"
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.origin: QPointF | None = None
        self.cursor_point: QPointF | None = None

    def cancel(self) -> None:
        self.origin = None
        self.view.viewport().update()

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self.origin = scene_pos
        self.cursor_point = scene_pos
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        self.cursor_point = scene_pos
        return self.origin is not None

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if self.origin is None:
            return False
        origin = self.origin
        self.origin = None

        if distance(origin, scene_pos) > 4.0 / self.view.scale_factor():
            self._knife(origin, scene_pos)
            return True

        shape = self.view.shape_at(view_pos) or self._nearest_curve(scene_pos)
        if shape is None:
            self.view.message.emit("Nuz potrebuje krivku nebo caru pod kurzorem.")
            return True
        keep_all = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._cut_at_click(shape, scene_pos, keep_all)
        return True

    # -- vlastni rezani ---------------------------------------------------
    def _nearest_curve(self, scene_pos: QPointF) -> ShapeMixin | None:
        threshold = 10.0 / self.view.scale_factor()
        best = None
        for shape in self.scene.shapes():
            if isinstance(shape, TextShape):
                continue
            found = locate_point(path_to_subpaths(shape.scene_path()), scene_pos)
            if found is not None and found[2] <= threshold:
                if best is None or found[2] < best[1]:
                    best = (shape, found[2])
        return best[0] if best else None

    def _crossings(self, shape: ShapeMixin) -> list[QPointF]:
        own = shape.scene_path()
        points: list[QPointF] = []
        for other in self.scene.shapes():
            if other is shape or isinstance(other, TextShape):
                continue
            points.extend(path_intersections(own, other.scene_path()))
        return points

    def _cut_at_click(self, shape: ShapeMixin, scene_pos: QPointF, keep_all: bool) -> None:
        target = shape if isinstance(shape, PathShape) else to_path_shape(shape)
        subpaths = path_to_subpaths(target.path())
        local_click = target.mapFromScene(scene_pos)

        found = locate_point(subpaths, local_click)
        if found is None:
            self.view.message.emit("Na krivce se nenaslo misto k rezu.")
            return
        index, click_param, _ = found

        cuts: list[float] = []
        for point in self._crossings(shape):
            located = locate_point([subpaths[index]], target.mapFromScene(point))
            if located is not None and located[2] <= 1.5:
                cuts.append(located[1])

        if not cuts:
            # Zadne krizeni: krivku aspon rozdelime v miste kliknuti.
            cuts = [click_param]
            keep_all = True

        pieces = split_subpath(subpaths[index], cuts)
        if len(pieces) < 2:
            self.view.message.emit("Tady rez nic nerozdeli.")
            return

        if not keep_all:
            distances = []
            for piece in pieces:
                located = locate_point([piece], local_click)
                distances.append(located[2] if located else float("inf"))

            pieces.pop(distances.index(min(distances)))

        rest = [subpaths[i] for i in range(len(subpaths)) if i != index]
        self._replace(shape, target, pieces + rest)

    def _knife(self, start: QPointF, end: QPointF) -> None:
        blade = QPainterPath(start)
        blade.lineTo(end)
        touched = 0

        for shape in list(self.scene.shapes()):
            if isinstance(shape, TextShape):
                continue
            crossings = path_intersections(shape.scene_path(), blade)
            if not crossings:
                continue

            target = shape if isinstance(shape, PathShape) else to_path_shape(shape)
            subpaths = path_to_subpaths(target.path())
            result: list[SubPath] = []
            for subpath in subpaths:
                cuts = []
                for point in crossings:
                    located = locate_point([subpath], target.mapFromScene(point))
                    if located is not None and located[2] <= 1.5:
                        cuts.append(located[1])
                result.extend(split_subpath(subpath, cuts) if cuts else [subpath])
            if len(result) > len(subpaths):
                self._replace(shape, target, result, record=False)
                touched += 1

        if touched:
            self.view.snapshot("Rez nozem")
        else:
            self.view.message.emit("Cara nozem nic neprotala.")

    def _replace(self, original: ShapeMixin, target: PathShape, pieces: list[SubPath],
                 record: bool = True) -> None:
        style = target.style.copy()
        if any(not piece.closed for piece in pieces):
            # Z rozrezaneho tvaru zbyvaji otevrene kusy, vypln by z nich
            # delala nesmyslne plochy.
            style.fill = None

        z = original.zValue()
        self.scene.removeItem(original)
        created = []
        for order, piece in enumerate(pieces):
            if len(piece.nodes) < 2:
                continue
            path = subpaths_to_path([piece])
            item = PathShape(path, style, piece.closed, target.name)
            item.setPos(target.pos())
            item.setTransformOriginPoint(target.transformOriginPoint())
            item.setRotation(target.rotation())
            item.setZValue(z + order * 0.001)
            self.scene.addItem(item)
            created.append(item)

        self.scene.clearSelection()
        for item in created:
            item.setSelected(True)
        if record:
            self.view.snapshot("Rezani krivky")

    def draw_overlay(self, painter: QPainter, scale: float) -> None:
        if self.origin is None or self.cursor_point is None:
            return
        pen = QPen(QColor("#e74c3c"))
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(self.origin, self.cursor_point)


class EraserTool(Tool):
    """Guma. Tahem odmaze cast tvaru, se Shiftem maze cele objekty."""

    name = "guma"
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.points: list[QPointF] = []
        self.cursor_point: QPointF | None = None
        self.whole = False

    def cancel(self) -> None:
        self.points = []

    def mouse_press(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self.whole = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.points = [scene_pos]
        self.cursor_point = scene_pos
        return True

    def mouse_move(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        self.cursor_point = scene_pos
        if not self.points:
            return True
        if distance(self.points[-1], scene_pos) >= 1.0 / self.view.scale_factor():
            self.points.append(scene_pos)
        return True

    def mouse_release(self, event, scene_pos: QPointF, view_pos: QPointF) -> bool:
        if not self.points:
            return False
        points = list(self.points)
        self.points = []
        if len(points) == 1:
            points.append(points[0] + QPointF(0.01, 0.01))

        trail = QPainterPath(points[0])
        for point in points[1:]:
            trail.lineTo(point)
        area = stroke_area(trail, self.view.eraser_size)

        if self.view.erase_area(area, whole_objects=self.whole):
            self.view.snapshot("Guma")
        return True

    def key_press(self, event) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        return False

    def draw_overlay(self, painter: QPainter, scale: float) -> None:
        pen = QPen(QColor("#e74c3c"))
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        radius = self.view.eraser_size / 2.0
        if self.cursor_point is not None:
            painter.drawEllipse(self.cursor_point, radius, radius)
        if len(self.points) > 1:
            trail = QPainterPath(self.points[0])
            for point in self.points[1:]:
                trail.lineTo(point)
            painter.drawPath(stroke_area(trail, self.view.eraser_size))


def _draw_nodes(painter: QPainter, scale: float, nodes: list[Node],
                selected: int | None) -> None:
    size = 5.0 / scale
    handle_pen = QPen(QColor("#7a7f87"))
    handle_pen.setCosmetic(True)
    node_pen = QPen(QColor("#1668c1"))
    node_pen.setCosmetic(True)

    for index, node in enumerate(nodes):
        if index == selected:
            for handle in (node.handle_in, node.handle_out):
                if handle is None:
                    continue
                painter.setPen(handle_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(node.point, handle)
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(handle, size * 0.8, size * 0.8)

        painter.setPen(node_pen)
        painter.setBrush(QColor("#ff8c1a") if index == selected else QColor("#ffffff"))
        painter.drawRect(QRectF(node.point.x() - size, node.point.y() - size,
                                size * 2, size * 2))


TOOL_CLASSES = {
    "vyber": SelectTool,
    "obdelnik": RectTool,
    "elipsa": EllipseTool,
    "cara": LineTool,
    "lomena": PolylineTool,
    "mnohouhelnik": PolygonTool,
    "tuzka": PencilTool,
    "text": TextTool,
    "krivka": CurveTool,
    "spline": SplineTool,
    "uzly": NodeTool,
    "vypln": FillTool,
    "nuz": CutTool,
    "guma": EraserTool,
}
