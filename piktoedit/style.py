"""Styl tvaru: vypln, obrys, sirka cary, pruhlednost."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

_RGB_RE = re.compile(r"rgba?\(([^)]*)\)", re.IGNORECASE)

CAP_TO_QT = {
    "butt": Qt.PenCapStyle.FlatCap,
    "round": Qt.PenCapStyle.RoundCap,
    "square": Qt.PenCapStyle.SquareCap,
}
QT_TO_CAP = {value: key for key, value in CAP_TO_QT.items()}

JOIN_TO_QT = {
    "miter": Qt.PenJoinStyle.MiterJoin,
    "round": Qt.PenJoinStyle.RoundJoin,
    "bevel": Qt.PenJoinStyle.BevelJoin,
}
QT_TO_JOIN = {value: key for key, value in JOIN_TO_QT.items()}


def parse_color(text: str | None) -> QColor | None:
    """Prevede SVG barvu na QColor. ``none`` vraci None."""
    if text is None:
        return None
    value = text.strip()
    if not value or value.lower() in ("none", "transparent"):
        return None
    if value.lower() == "currentcolor":
        return QColor("#000000")
    match = _RGB_RE.fullmatch(value)
    if match:
        pieces = [p.strip() for p in match.group(1).replace("/", ",").split(",") if p.strip()]
        numbers: list[float] = []
        for piece in pieces:
            if piece.endswith("%"):
                numbers.append(float(piece[:-1]) * 255.0 / 100.0)
            else:
                numbers.append(float(piece))
        while len(numbers) < 3:
            numbers.append(0.0)
        color = QColor(int(numbers[0]), int(numbers[1]), int(numbers[2]))
        if len(numbers) > 3:
            alpha = numbers[3]
            color.setAlphaF(alpha if alpha <= 1.0 else alpha / 255.0)
        return color
    color = QColor(value)
    return color if color.isValid() else None


def color_to_svg(color: QColor | None) -> str:
    if color is None:
        return "none"
    return color.name(QColor.NameFormat.HexRgb)


@dataclass
class Style:
    """Vzhled jednoho tvaru."""

    fill: QColor | None = field(default_factory=lambda: QColor("#4a90d9"))
    stroke: QColor | None = field(default_factory=lambda: QColor("#1f2933"))
    stroke_width: float = 3.0
    opacity: float = 1.0
    linecap: str = "round"
    linejoin: str = "round"
    dash: list[float] | None = None

    def copy(self) -> "Style":
        return replace(
            self,
            fill=QColor(self.fill) if self.fill else None,
            stroke=QColor(self.stroke) if self.stroke else None,
            dash=list(self.dash) if self.dash else None,
        )

    # -- prevod na Qt -----------------------------------------------------
    def pen(self) -> QPen:
        if self.stroke is None or self.stroke_width <= 0:
            return QPen(Qt.PenStyle.NoPen)
        pen = QPen(QColor(self.stroke))
        pen.setWidthF(float(self.stroke_width))
        pen.setCapStyle(CAP_TO_QT.get(self.linecap, Qt.PenCapStyle.RoundCap))
        pen.setJoinStyle(JOIN_TO_QT.get(self.linejoin, Qt.PenJoinStyle.RoundJoin))
        if self.dash:
            width = max(0.001, float(self.stroke_width))
            pen.setDashPattern([max(0.01, value / width) for value in self.dash])
        pen.setCosmetic(False)
        return pen

    def brush(self) -> QBrush:
        if self.fill is None:
            return QBrush(Qt.BrushStyle.NoBrush)
        return QBrush(QColor(self.fill))

    # -- prevod na SVG ----------------------------------------------------
    def to_attrs(self) -> dict[str, str]:
        attrs: dict[str, str] = {
            "fill": color_to_svg(self.fill),
            "stroke": color_to_svg(self.stroke),
        }
        if self.stroke is not None:
            attrs["stroke-width"] = f"{self.stroke_width:g}"
            attrs["stroke-linecap"] = self.linecap
            attrs["stroke-linejoin"] = self.linejoin
            if self.dash:
                attrs["stroke-dasharray"] = " ".join(f"{value:g}" for value in self.dash)
            if self.stroke.alphaF() < 1.0:
                attrs["stroke-opacity"] = f"{self.stroke.alphaF():g}"
        if self.fill is not None and self.fill.alphaF() < 1.0:
            attrs["fill-opacity"] = f"{self.fill.alphaF():g}"
        if self.opacity < 1.0:
            attrs["opacity"] = f"{self.opacity:g}"
        return attrs

    @classmethod
    def from_attrs(cls, attrs: dict[str, str]) -> "Style":
        merged = dict(attrs)
        inline = attrs.get("style")
        if inline:
            for item in inline.split(";"):
                if ":" in item:
                    key, value = item.split(":", 1)
                    merged[key.strip()] = value.strip()

        style = cls()
        style.fill = parse_color(merged.get("fill", "#000000"))
        style.stroke = parse_color(merged.get("stroke", "none"))
        try:
            style.stroke_width = float(merged.get("stroke-width", 1.0))
        except ValueError:
            style.stroke_width = 1.0
        try:
            style.opacity = max(0.0, min(1.0, float(merged.get("opacity", 1.0))))
        except ValueError:
            style.opacity = 1.0
        cap = merged.get("stroke-linecap", "round")
        style.linecap = cap if cap in CAP_TO_QT else "round"
        join = merged.get("stroke-linejoin", "round")
        style.linejoin = join if join in JOIN_TO_QT else "round"

        dash = merged.get("stroke-dasharray")
        if dash and dash.strip().lower() != "none":
            values: list[float] = []
            for piece in re.split(r"[\s,]+", dash.strip()):
                try:
                    values.append(float(piece))
                except ValueError:
                    values = []
                    break
            style.dash = values or None

        for key, target in (("fill-opacity", "fill"), ("stroke-opacity", "stroke")):
            raw = merged.get(key)
            color = getattr(style, target)
            if raw and color is not None:
                try:
                    color.setAlphaF(max(0.0, min(1.0, float(raw))))
                except ValueError:
                    pass
        return style
