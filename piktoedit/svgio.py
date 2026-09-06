"""Cteni a zapis SVG.

SVG je zaroven nativnim formatem editoru. Pri ukladani se pridavaji jen
nepovinne atributy ve jmennem prostoru ``pikto`` (nazvy objektu, mrizka,
predloha), ktere ostatni prohlizece ignoruji.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainterPath, QTransform

from .pathdata import fmt
from .shapes import (
    PIKTO_NS,
    EllipseShape,
    LineShape,
    PathShape,
    RectShape,
    ShapeMixin,
    TextShape,
    shape_from_svg,
    text_shape_from_svg,
)
from .style import Style, color_to_svg, parse_color

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", SVG_NS)
ET.register_namespace("pikto", PIKTO_NS)
ET.register_namespace("xlink", XLINK_NS)

_UNITS = {"px": 1.0, "pt": 96.0 / 72.0, "pc": 16.0, "mm": 96.0 / 25.4,
          "cm": 96.0 / 2.54, "in": 96.0, "": 1.0}

_TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


@dataclass
class Document:
    """Vlastnosti kresby, ktere nepatri zadnemu jednotlivemu tvaru."""

    width: float = 1024.0
    height: float = 1024.0
    background: QColor | None = field(default_factory=lambda: QColor("#ffffff"))
    grid_size: float = 16.0
    reference_path: str = ""
    reference_opacity: float = 0.45
    title: str = ""

    def rect(self) -> QRectF:
        return QRectF(0.0, 0.0, self.width, self.height)


def parse_length(text: str | None, default: float = 0.0) -> float:
    if text is None:
        return default
    value = str(text).strip()
    match = re.fullmatch(r"([-+０-９\d.eE+-]+)\s*([a-z%]*)", value)
    if not match:
        return default
    try:
        number = float(match.group(1))
    except ValueError:
        return default
    unit = match.group(2).lower()
    if unit == "%":
        return default
    return number * _UNITS.get(unit, 1.0)


def parse_transform(text: str | None) -> QTransform:
    transform = QTransform()
    if not text:
        return transform
    for name, raw in _TRANSFORM_RE.findall(text):
        numbers: list[float] = []
        for piece in re.split(r"[\s,]+", raw.strip()):
            if not piece:
                continue
            try:
                numbers.append(float(piece))
            except ValueError:
                pass
        step = QTransform()
        if name == "matrix" and len(numbers) >= 6:
            step = QTransform(numbers[0], numbers[1], numbers[2],
                              numbers[3], numbers[4], numbers[5])
        elif name == "translate" and numbers:
            step = QTransform.fromTranslate(numbers[0], numbers[1] if len(numbers) > 1 else 0.0)
        elif name == "scale" and numbers:
            step = QTransform.fromScale(numbers[0], numbers[1] if len(numbers) > 1 else numbers[0])
        elif name == "rotate" and numbers:
            step = QTransform()
            if len(numbers) >= 3:
                step.translate(numbers[1], numbers[2])
                step.rotate(numbers[0])
                step.translate(-numbers[1], -numbers[2])
            else:
                step.rotate(numbers[0])
        elif name == "skewX" and numbers:
            step.shear(math.tan(math.radians(numbers[0])), 0.0)
        elif name == "skewY" and numbers:
            step.shear(0.0, math.tan(math.radians(numbers[0])))
        transform = step * transform
    return transform


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


# ---------------------------------------------------------------------------
# Zapis
# ---------------------------------------------------------------------------

def build_svg(document: Document, shapes: list[ShapeMixin]) -> ET.Element:
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": fmt(document.width),
        "height": fmt(document.height),
        "viewBox": f"0 0 {fmt(document.width)} {fmt(document.height)}",
        "version": "1.1",
    })
    root.set(f"{{{PIKTO_NS}}}grid", fmt(document.grid_size))
    if document.reference_path:
        root.set(f"{{{PIKTO_NS}}}reference", document.reference_path)
        root.set(f"{{{PIKTO_NS}}}reference-opacity", fmt(document.reference_opacity))
    if document.title:
        title = ET.SubElement(root, f"{{{SVG_NS}}}title")
        title.text = document.title

    if document.background is not None:
        ET.SubElement(root, f"{{{SVG_NS}}}rect", {
            "x": "0", "y": "0",
            "width": fmt(document.width),
            "height": fmt(document.height),
            "fill": color_to_svg(document.background),
            f"{{{PIKTO_NS}}}role": "background",
        })

    for shape in shapes:
        tag, attrs = shape.to_svg()
        element = ET.SubElement(root, f"{{{SVG_NS}}}{tag}", attrs)
        if isinstance(shape, TextShape):
            _write_text_content(element, shape)
    return root


def _write_text_content(element: ET.Element, shape: TextShape) -> None:
    lines = shape.text_lines()
    spacing = shape.line_spacing()
    if len(lines) == 1:
        element.text = lines[0]
        return
    for index, line in enumerate(lines):
        tspan = ET.SubElement(element, f"{{{SVG_NS}}}tspan", {
            "x": "0",
            "dy": "0" if index == 0 else fmt(spacing),
        })
        tspan.text = line


def to_string(document: Document, shapes: list[ShapeMixin]) -> str:
    root = build_svg(document, shapes)
    _indent(root)
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def save(path: str | Path, document: Document, shapes: list[ShapeMixin]) -> None:
    Path(path).write_text(to_string(document, shapes), encoding="utf-8")


def _indent(element: ET.Element, level: int = 0) -> None:
    pad = "\n" + "  " * level
    if len(element):
        if not (element.text or "").strip():
            element.text = pad + "  "
        for child in element:
            _indent(child, level + 1)
            if not (child.tail or "").strip():
                child.tail = pad + "  "
        if not (element[-1].tail or "").strip():
            element[-1].tail = pad
    elif level and not (element.tail or "").strip():
        element.tail = pad


# ---------------------------------------------------------------------------
# Cteni
# ---------------------------------------------------------------------------

_INHERITED = ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
              "stroke-dasharray", "fill-opacity", "stroke-opacity", "style",
              "font-family", "font-size", "font-weight", "font-style")


def from_string(text: str) -> tuple[Document, list[ShapeMixin]]:
    root = ET.fromstring(text)
    document = Document()
    document.width = parse_length(root.get("width"), 1024.0) or 1024.0
    document.height = parse_length(root.get("height"), 1024.0) or 1024.0

    root_transform = QTransform()
    view_box = root.get("viewBox")
    if view_box:
        numbers = [float(piece) for piece in re.split(r"[\s,]+", view_box.strip())
                   if _is_number(piece)]
        if len(numbers) == 4 and numbers[2] > 0 and numbers[3] > 0:
            if not root.get("width"):
                document.width = numbers[2]
            if not root.get("height"):
                document.height = numbers[3]
            scale_x = document.width / numbers[2]
            scale_y = document.height / numbers[3]
            root_transform = QTransform.fromTranslate(-numbers[0], -numbers[1])
            root_transform *= QTransform.fromScale(scale_x, scale_y)

    grid = root.get(f"{{{PIKTO_NS}}}grid")
    if grid:
        document.grid_size = parse_length(grid, 16.0) or 16.0
    reference = root.get(f"{{{PIKTO_NS}}}reference")
    if reference:
        document.reference_path = reference
        document.reference_opacity = parse_length(
            root.get(f"{{{PIKTO_NS}}}reference-opacity"), 0.45) or 0.45

    title = root.find(f"{{{SVG_NS}}}title")
    if title is not None and title.text:
        document.title = title.text.strip()

    document.background = None
    shapes: list[ShapeMixin] = []
    _walk(root, {}, root_transform, document, shapes)
    return document, shapes


def load(path: str | Path) -> tuple[Document, list[ShapeMixin]]:
    return from_string(Path(path).read_text(encoding="utf-8"))


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _walk(parent: ET.Element, inherited: dict[str, str], transform: QTransform,
          document: Document, shapes: list[ShapeMixin]) -> None:
    for element in parent:
        tag = _local(element.tag)
        attrs = {key: value for key, value in element.attrib.items()}
        merged = dict(inherited)
        for key in _INHERITED:
            if key in attrs:
                merged[key] = attrs[key]
        combined = parse_transform(attrs.get("transform")) * transform

        if tag in ("g", "svg", "a"):
            _walk(element, merged, combined, document, shapes)
            continue
        if tag in ("title", "desc", "defs", "metadata", "style"):
            continue

        if attrs.get(f"{{{PIKTO_NS}}}role") == "background" or _looks_like_background(
                tag, attrs, document):
            document.background = parse_color(attrs.get("fill", "#ffffff"))
            continue

        full = dict(merged)
        full.update(attrs)

        if tag == "text":
            text_shape = text_shape_from_svg(full, _text_lines(element))
            shapes.append(_place_text(text_shape, full, combined))
            continue

        shape = shape_from_svg(tag, full)
        if shape is None:
            continue
        shapes.append(_apply_transform(shape, combined))


def _looks_like_background(tag: str, attrs: dict[str, str], document: Document) -> bool:
    """Cely bily obdelnik pres celou plochu bereme jako pozadi, ne jako tvar."""
    if tag != "rect" or document.background is not None:
        return False
    if attrs.get("transform"):
        return False
    x = parse_length(attrs.get("x", "0"))
    y = parse_length(attrs.get("y", "0"))
    width = parse_length(attrs.get("width", "0"))
    height = parse_length(attrs.get("height", "0"))
    return (abs(x) < 0.5 and abs(y) < 0.5
            and abs(width - document.width) < 0.5
            and abs(height - document.height) < 0.5)


def _text_lines(element: ET.Element) -> list[str]:
    tspans = [child for child in element if _local(child.tag) == "tspan"]
    if tspans:
        return [(child.text or "") for child in tspans]
    return [(element.text or "").strip()]


def _place_text(shape: TextShape, attrs: dict[str, str],
                transform: QTransform) -> ShapeMixin:
    from PySide6.QtGui import QFontMetricsF

    x = parse_length(attrs.get("x", "0"))
    y = parse_length(attrs.get("y", "0"))
    ascent = QFontMetricsF(shape.font()).ascent()
    anchor = attrs.get("text-anchor", "start")
    width = shape.boundingRect().width()
    offset_x = 0.0
    if anchor == "middle":
        offset_x = -width / 2.0
    elif anchor == "end":
        offset_x = -width
    base = QTransform.fromTranslate(x + offset_x, y - ascent) * transform
    return _apply_transform(shape, base)


def _apply_transform(shape: ShapeMixin, transform: QTransform) -> ShapeMixin:
    """Rigidni transformaci ulozi jako pozici a rotaci, jinak ji zapece do tvaru.

    Vraci vysledny tvar; pri zkoseni nebo nerovnomernem zvetseni muze byt
    obdelnik nebo elipsa nahrazena krivkou.
    """
    if transform.isIdentity():
        shape.sync_origin()
        return shape

    m11, m12 = transform.m11(), transform.m12()
    m21, m22 = transform.m21(), transform.m22()
    scale_x = math.hypot(m11, m12)
    scale_y = math.hypot(m21, m22)
    orthogonal = abs(m11 * m21 + m12 * m22) < 1e-6
    rigid = orthogonal and abs(scale_x - 1.0) < 1e-6 and abs(scale_y - 1.0) < 1e-6

    if rigid:
        angle = math.degrees(math.atan2(m12, m11))
        shape.setRotation(0.0)
        shape.setTransformOriginPoint(shape.rotation_origin())
        if abs(angle) < 1e-9:
            shape.setPos(transform.dx(), transform.dy())
            return shape

        # SVG sklada translate * rotate(uhel, stred), Qt otaci kolem sveho
        # stredu az po posunu. Posun proto musime o rotaci stredu opravit.
        shape.setRotation(angle)
        origin = shape.transformOriginPoint()
        rotation = QTransform()
        rotation.rotate(angle)
        rotated = rotation.map(origin)
        shape.setPos(transform.dx() - origin.x() + rotated.x(),
                     transform.dy() - origin.y() + rotated.y())
        return shape

    return _bake(shape, transform)


def _bake(shape: ShapeMixin, transform: QTransform) -> ShapeMixin:
    scale = _average_scale(transform)

    if isinstance(shape, LineShape):
        line = shape.line()
        p1 = transform.map(line.p1())
        p2 = transform.map(line.p2())
        shape.setLine(p1.x(), p1.y(), p2.x(), p2.y())
        shape.style.stroke_width *= scale
        shape.apply_style()
        shape.sync_origin()
        return shape

    if isinstance(shape, TextShape):
        font = shape.font()
        font.setPointSizeF(max(4.0, font.pointSizeF() * scale))
        shape.setFont(font)
        shape.setPos(transform.dx(), transform.dy())
        shape.sync_origin()
        return shape

    path = QPainterPath()
    closed = True
    if isinstance(shape, RectShape):
        if shape.radius > 0:
            path.addRoundedRect(shape.rect(), shape.radius, shape.radius)
        else:
            path.addRect(shape.rect())
    elif isinstance(shape, EllipseShape):
        path.addEllipse(shape.rect())
    elif isinstance(shape, PathShape):
        path = shape.path()
        closed = shape.closed
    else:
        return shape

    mapped = transform.map(path)
    style = shape.style.copy()
    style.stroke_width *= scale

    if isinstance(shape, PathShape):
        shape.setPath(mapped)
        shape.set_style(style)
        shape.sync_origin()
        return shape

    # Obdelnik nebo elipsa po zkoseni uz obdelnikem neni; nahradime krivkou.
    return PathShape(mapped, style, closed, shape.name)


def _average_scale(transform: QTransform) -> float:
    return math.sqrt(abs(transform.determinant())) or 1.0


def shapes_to_clipboard_text(shapes: list[ShapeMixin]) -> str:
    document = Document(width=0, height=0, background=None)
    root = build_svg(document, shapes)
    return ET.tostring(root, encoding="unicode")


def shapes_from_clipboard_text(text: str) -> list[ShapeMixin]:
    try:
        _, shapes = from_string(text)
    except ET.ParseError:
        return []
    return shapes


__all__ = ["Document", "save", "load", "to_string", "from_string",
           "shapes_to_clipboard_text", "shapes_from_clipboard_text",
           "parse_length", "parse_transform"]
