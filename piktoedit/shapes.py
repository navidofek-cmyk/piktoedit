"""Graficke objekty na platne.

Kazdy tvar je QGraphicsItem, ktery umi sam sebe popsat jako SVG element.
Diky tomu je ulozeny soubor primo pracovnim formatem editoru.
"""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainterPath,
    QPixmap,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QStyle,
    QStyleOptionGraphicsItem,
)

from .pathdata import fmt, parse_path_data, path_to_data
from .style import Style, color_to_svg, parse_color

#: Jmenny prostor pro data, ktera do SVG patri jen kvuli editoru.
PIKTO_NS = "https://github.com/aac/piktoedit"

_MIN_SIZE = 0.5


class ShapeMixin:
    """Spolecne chovani vsech tvaru."""

    kind = "shape"
    default_name = "Tvar"

    def setup(self, style: Style, name: str | None = None, role: str = "") -> None:
        self.style = style.copy()
        self.name = name or self.default_name
        #: Volitelna role, napr. ``caption`` pro popisek pod piktogramem.
        self.role = role
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.apply_style()

    # -- styl -------------------------------------------------------------
    def apply_style(self) -> None:
        if hasattr(self, "setPen"):
            self.setPen(self.style.pen())
        if hasattr(self, "setBrush"):
            self.setBrush(self.style.brush())
        self.setOpacity(self.style.opacity)
        self.update()

    def set_style(self, style: Style) -> None:
        self.style = style.copy()
        self.apply_style()

    # -- geometrie --------------------------------------------------------
    def local_rect(self) -> QRectF:
        raise NotImplementedError

    def set_local_rect(self, rect: QRectF) -> None:
        raise NotImplementedError

    def outline_path(self) -> QPainterPath:
        """Tvar jako krivka v souradnicich objektu."""
        raise NotImplementedError

    def scene_path(self) -> QPainterPath:
        """Tvar jako krivka v souradnicich sceny."""
        return self.sceneTransform().map(self.outline_path())

    def scene_center(self) -> QPointF:
        return self.mapToScene(self.local_rect().center())

    def rotation_origin(self) -> QPointF:
        return self.local_rect().center()

    def sync_origin(self) -> None:
        """Stred otaceni drzime uprostred tvaru, aby rotace byla intuitivni."""
        if self.rotation():
            # Pri zmene geometrie by posun stredu tvar odsunul; dopocitame pos.
            before = self.mapToScene(self.transformOriginPoint())
            self.setTransformOriginPoint(self.rotation_origin())
            after = self.mapToScene(self.transformOriginPoint())
            self.setPos(self.pos() + before - after)
        else:
            self.setTransformOriginPoint(self.rotation_origin())

    # -- vykresleni -------------------------------------------------------
    def paint(self, painter, option, widget=None):  # type: ignore[override]
        # Vlastni znaceni vyberu kresli platno, vestavene prerusovane
        # obdelniky by se s nim bily.
        adjusted = QStyleOptionGraphicsItem(option)
        adjusted.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, adjusted, widget)

    # -- SVG --------------------------------------------------------------
    def transform_attr(self) -> str | None:
        parts: list[str] = []
        pos = self.pos()
        if pos.x() or pos.y():
            parts.append(f"translate({fmt(pos.x())} {fmt(pos.y())})")
        angle = self.rotation()
        if angle:
            origin = self.transformOriginPoint()
            parts.append(f"rotate({fmt(angle)} {fmt(origin.x())} {fmt(origin.y())})")
        return " ".join(parts) if parts else None

    def svg_element(self) -> tuple[str, dict[str, str]]:
        raise NotImplementedError

    def to_svg(self) -> tuple[str, dict[str, str]]:
        tag, attrs = self.svg_element()
        attrs.update(self.style.to_attrs())
        transform = self.transform_attr()
        if transform:
            attrs["transform"] = transform
        attrs[f"{{{PIKTO_NS}}}name"] = self.name
        attrs[f"{{{PIKTO_NS}}}kind"] = self.kind
        if self.role:
            attrs[f"{{{PIKTO_NS}}}role"] = self.role
        return tag, attrs

    def clone(self) -> "ShapeMixin":
        raise NotImplementedError

    def _copy_common(self, other: "ShapeMixin") -> "ShapeMixin":
        other.role = self.role
        other.setPos(self.pos())
        other.setRotation(self.rotation())
        other.setTransformOriginPoint(self.transformOriginPoint())
        other.setZValue(self.zValue())
        other.name = self.name
        return other


class RectShape(ShapeMixin, QGraphicsRectItem):
    kind = "rect"
    default_name = "Obdelnik"

    def __init__(self, rect: QRectF, style: Style, radius: float = 0.0, name: str | None = None):
        QGraphicsRectItem.__init__(self, rect)
        self.radius = float(radius)
        self.setup(style, name)
        self.sync_origin()

    def local_rect(self) -> QRectF:
        return self.rect()

    def set_local_rect(self, rect: QRectF) -> None:
        self.setRect(rect.normalized())
        self.sync_origin()

    def set_radius(self, radius: float) -> None:
        self.radius = max(0.0, float(radius))
        self.update()

    def paint(self, painter, option, widget=None):
        adjusted = QStyleOptionGraphicsItem(option)
        adjusted.state &= ~QStyle.StateFlag.State_Selected
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        if self.radius > 0:
            painter.drawRoundedRect(self.rect(), self.radius, self.radius)
        else:
            painter.drawRect(self.rect())

    def outline_path(self) -> QPainterPath:
        path = QPainterPath()
        if self.radius > 0:
            path.addRoundedRect(self.rect(), self.radius, self.radius)
        else:
            path.addRect(self.rect())
        return path

    def svg_element(self) -> tuple[str, dict[str, str]]:
        rect = self.rect().normalized()
        attrs = {
            "x": fmt(rect.x()),
            "y": fmt(rect.y()),
            "width": fmt(rect.width()),
            "height": fmt(rect.height()),
        }
        if self.radius > 0:
            attrs["rx"] = fmt(self.radius)
            attrs["ry"] = fmt(self.radius)
        return "rect", attrs

    def clone(self) -> "RectShape":
        return self._copy_common(RectShape(self.rect(), self.style, self.radius, self.name))


class EllipseShape(ShapeMixin, QGraphicsEllipseItem):
    kind = "ellipse"
    default_name = "Elipsa"

    def __init__(self, rect: QRectF, style: Style, name: str | None = None):
        QGraphicsEllipseItem.__init__(self, rect)
        self.setup(style, name)
        self.sync_origin()

    def local_rect(self) -> QRectF:
        return self.rect()

    def set_local_rect(self, rect: QRectF) -> None:
        self.setRect(rect.normalized())
        self.sync_origin()

    def outline_path(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(self.rect())
        return path

    def svg_element(self) -> tuple[str, dict[str, str]]:
        rect = self.rect().normalized()
        center = rect.center()
        return "ellipse", {
            "cx": fmt(center.x()),
            "cy": fmt(center.y()),
            "rx": fmt(rect.width() / 2.0),
            "ry": fmt(rect.height() / 2.0),
        }

    def clone(self) -> "EllipseShape":
        return self._copy_common(EllipseShape(self.rect(), self.style, self.name))


class LineShape(ShapeMixin, QGraphicsLineItem):
    kind = "line"
    default_name = "Cara"

    def __init__(self, line: QLineF, style: Style, name: str | None = None):
        QGraphicsLineItem.__init__(self, line)
        self.setup(style, name)
        self.sync_origin()

    def apply_style(self) -> None:
        self.setPen(self.style.pen())
        self.setOpacity(self.style.opacity)
        self.update()

    def local_rect(self) -> QRectF:
        line = self.line()
        return QRectF(line.p1(), line.p2()).normalized()

    def set_local_rect(self, rect: QRectF) -> None:
        old = self.local_rect()
        line = self.line()
        rect = rect.normalized()
        sx = rect.width() / old.width() if old.width() > _MIN_SIZE else 1.0
        sy = rect.height() / old.height() if old.height() > _MIN_SIZE else 1.0

        def remap(point: QPointF) -> QPointF:
            return QPointF(rect.x() + (point.x() - old.x()) * sx,
                           rect.y() + (point.y() - old.y()) * sy)

        self.setLine(QLineF(remap(line.p1()), remap(line.p2())))
        self.sync_origin()

    def outline_path(self) -> QPainterPath:
        path = QPainterPath(self.line().p1())
        path.lineTo(self.line().p2())
        return path

    def svg_element(self) -> tuple[str, dict[str, str]]:
        line = self.line()
        return "line", {
            "x1": fmt(line.x1()), "y1": fmt(line.y1()),
            "x2": fmt(line.x2()), "y2": fmt(line.y2()),
        }

    def clone(self) -> "LineShape":
        return self._copy_common(LineShape(self.line(), self.style, self.name))


class PathShape(ShapeMixin, QGraphicsPathItem):
    kind = "path"
    default_name = "Krivka"

    def __init__(self, path: QPainterPath, style: Style, closed: bool = False,
                 name: str | None = None):
        QGraphicsPathItem.__init__(self, path)
        self.closed = bool(closed)
        self.setup(style, name)
        self.sync_origin()

    @classmethod
    def from_points(cls, points: list[QPointF], style: Style, closed: bool = False,
                    name: str | None = None) -> "PathShape":
        path = QPainterPath()
        if points:
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
            if closed:
                path.closeSubpath()
        return cls(path, style, closed, name)

    def local_rect(self) -> QRectF:
        rect = self.path().boundingRect()
        if rect.width() < _MIN_SIZE:
            rect.setWidth(_MIN_SIZE)
        if rect.height() < _MIN_SIZE:
            rect.setHeight(_MIN_SIZE)
        return rect

    def set_local_rect(self, rect: QRectF) -> None:
        old = self.path().boundingRect()
        rect = rect.normalized()
        sx = rect.width() / old.width() if old.width() > _MIN_SIZE else 1.0
        sy = rect.height() / old.height() if old.height() > _MIN_SIZE else 1.0
        transform = QTransform()
        transform.translate(rect.x(), rect.y())
        transform.scale(sx, sy)
        transform.translate(-old.x(), -old.y())
        self.setPath(transform.map(self.path()))
        self.sync_origin()

    def points(self) -> list[QPointF]:
        path = self.path()
        return [QPointF(path.elementAt(i).x, path.elementAt(i).y)
                for i in range(path.elementCount())]

    def outline_path(self) -> QPainterPath:
        return QPainterPath(self.path())

    def set_closed(self, closed: bool) -> None:
        """Uzavreni krivky; az uzavrena krivka jde smysluplne vyplnit."""
        self.closed = bool(closed)
        if closed:
            path = QPainterPath(self.path())
            path.closeSubpath()
            self.setPath(path)
        self.update()

    def svg_element(self) -> tuple[str, dict[str, str]]:
        return "path", {"d": path_to_data(self.path(), self.closed)}

    def clone(self) -> "PathShape":
        return self._copy_common(
            PathShape(QPainterPath(self.path()), self.style, self.closed, self.name)
        )


class TextShape(ShapeMixin, QGraphicsTextItem):
    kind = "text"
    default_name = "Text"

    def __init__(self, text: str, style: Style, font: QFont | None = None,
                 name: str | None = None):
        QGraphicsTextItem.__init__(self)
        self.document().setDocumentMargin(0.0)
        self.setPlainText(text)
        self.setFont(font or QFont("Arial", 48, QFont.Weight.Bold))
        self.setup(style, name or (text.strip()[:24] or self.default_name))

    def apply_style(self) -> None:
        color = self.style.fill or self.style.stroke or QColor("#000000")
        self.setDefaultTextColor(color)
        self.setOpacity(self.style.opacity)
        self.update()

    def text(self) -> str:
        return self.toPlainText()

    def set_text(self, text: str) -> None:
        self.setPlainText(text)
        self.sync_origin()

    def local_rect(self) -> QRectF:
        return self.boundingRect()

    def set_local_rect(self, rect: QRectF) -> None:
        old = self.boundingRect()
        if old.height() <= _MIN_SIZE:
            return
        ratio = rect.normalized().height() / old.height()
        font = QFont(self.font())
        size = max(4.0, font.pointSizeF() * ratio)
        font.setPointSizeF(size)
        self.setFont(font)
        self.sync_origin()

    def svg_element(self) -> tuple[str, dict[str, str]]:
        font = self.font()
        metrics = QFontMetricsF(font)
        attrs = {
            "x": "0",
            "y": fmt(metrics.ascent()),
            "font-family": font.family(),
            "font-size": fmt(font.pointSizeF()),
            "xml:space": "preserve",
        }
        if font.bold():
            attrs["font-weight"] = "bold"
        if font.italic():
            attrs["font-style"] = "italic"
        return "text", attrs

    def outline_path(self) -> QPainterPath:
        path = QPainterPath()
        metrics = QFontMetricsF(self.font())
        y = metrics.ascent()
        for line in self.text_lines():
            path.addText(0.0, y, self.font(), line)
            y += metrics.lineSpacing()
        return path

    def text_lines(self) -> list[str]:
        return self.toPlainText().split("\n")

    def line_spacing(self) -> float:
        return QFontMetricsF(self.font()).lineSpacing()

    def clone(self) -> "TextShape":
        return self._copy_common(
            TextShape(self.toPlainText(), self.style, QFont(self.font()), self.name)
        )


class ReferenceImage(QGraphicsPixmapItem):
    """Predloha k obkresleni. Do SVG se uklada jen jako poznamka editoru."""

    kind = "reference"

    def __init__(self, pixmap: QPixmap, source: str = ""):
        super().__init__(pixmap)
        self.source = source
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setZValue(-1000)
        self.setOpacity(0.45)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    @classmethod
    def load(cls, path: str | Path) -> "ReferenceImage | None":
        image = QImage(str(path))
        if image.isNull():
            return None
        return cls(QPixmap.fromImage(image), str(path))

    def fit_into(self, width: float, height: float) -> None:
        pixmap = self.pixmap()
        if pixmap.isNull():
            return
        scale = min(width / pixmap.width(), height / pixmap.height())
        self.setScale(scale)
        self.setPos((width - pixmap.width() * scale) / 2.0,
                    (height - pixmap.height() * scale) / 2.0)

    def to_data_uri(self) -> str:
        pixmap = self.pixmap()
        from PySide6.QtCore import QBuffer, QByteArray

        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()
        encoded = base64.b64encode(bytes(data)).decode("ascii")
        return f"data:image/png;base64,{encoded}"


def to_path_shape(shape: ShapeMixin) -> PathShape:
    """Prevede libovolny tvar na krivku, aby sel editovat po uzlech."""
    if isinstance(shape, PathShape):
        return shape
    style = shape.style.copy()
    if isinstance(shape, TextShape):
        style.stroke = style.stroke or None
    path = shape.outline_path()
    closed = not isinstance(shape, LineShape)
    replacement = PathShape(path, style, closed, shape.name)
    replacement.role = shape.role
    replacement.setPos(shape.pos())
    replacement.setTransformOriginPoint(shape.transformOriginPoint())
    replacement.setRotation(shape.rotation())
    replacement.setZValue(shape.zValue())
    return replacement


SHAPE_CLASSES = {
    "rect": RectShape,
    "ellipse": EllipseShape,
    "line": LineShape,
    "path": PathShape,
    "text": TextShape,
}


def shape_from_svg(tag: str, attrs: dict[str, str]) -> ShapeMixin | None:
    """Vytvori tvar z jednoho SVG elementu. Nezname elementy vraci None."""
    shape = _build_shape(tag, attrs)
    if shape is not None:
        shape.role = attrs.get(f"{{{PIKTO_NS}}}role", "")
    return shape


def _build_shape(tag: str, attrs: dict[str, str]) -> ShapeMixin | None:
    style = Style.from_attrs(attrs)
    name = attrs.get(f"{{{PIKTO_NS}}}name")

    def number(key: str, default: float = 0.0) -> float:
        try:
            return float(str(attrs.get(key, default)).strip().rstrip("px"))
        except (TypeError, ValueError):
            return default

    if tag == "rect":
        rect = QRectF(number("x"), number("y"), number("width"), number("height"))
        radius = max(number("rx"), number("ry"))
        return RectShape(rect, style, radius, name)
    if tag == "circle":
        radius = number("r")
        rect = QRectF(number("cx") - radius, number("cy") - radius, radius * 2, radius * 2)
        return EllipseShape(rect, style, name)
    if tag == "ellipse":
        rx, ry = number("rx"), number("ry")
        rect = QRectF(number("cx") - rx, number("cy") - ry, rx * 2, ry * 2)
        return EllipseShape(rect, style, name)
    if tag == "line":
        line = QLineF(number("x1"), number("y1"), number("x2"), number("y2"))
        return LineShape(line, style, name)
    if tag in ("polyline", "polygon"):
        points = _parse_points(attrs.get("points", ""))
        if len(points) < 2:
            return None
        if tag == "polygon" and style.fill is None and "fill" not in attrs:
            style.fill = QColor("#000000")
        return PathShape.from_points(points, style, closed=(tag == "polygon"), name=name)
    if tag == "path":
        path, closed = parse_path_data(attrs.get("d", ""))
        if path.elementCount() == 0:
            return None
        return PathShape(path, style, closed, name)
    return None


def _parse_points(text: str) -> list[QPointF]:
    numbers: list[float] = []
    for piece in text.replace(",", " ").split():
        try:
            numbers.append(float(piece))
        except ValueError:
            continue
    return [QPointF(numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2)]


def text_shape_from_svg(attrs: dict[str, str], lines: list[str]) -> TextShape:
    style = Style.from_attrs(attrs)
    if style.fill is None:
        style.fill = parse_color(attrs.get("fill")) or QColor("#000000")
    family = attrs.get("font-family", "Arial")
    try:
        size = float(str(attrs.get("font-size", 48)).rstrip("px"))
    except ValueError:
        size = 48.0
    font = QFont(family)
    font.setPointSizeF(size)
    font.setBold(attrs.get("font-weight", "") in ("bold", "700", "800", "900"))
    font.setItalic(attrs.get("font-style", "") == "italic")
    shape = TextShape("\n".join(lines), style, font, attrs.get(f"{{{PIKTO_NS}}}name"))
    shape.role = attrs.get(f"{{{PIKTO_NS}}}role", "")
    return shape


__all__ = [
    "PIKTO_NS",
    "ShapeMixin",
    "RectShape",
    "EllipseShape",
    "LineShape",
    "PathShape",
    "TextShape",
    "ReferenceImage",
    "SHAPE_CLASSES",
    "to_path_shape",
    "shape_from_svg",
    "text_shape_from_svg",
    "color_to_svg",
]
