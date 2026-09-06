"""Prevod mezi SVG atributem ``d`` a QPainterPath.

Parser zvlada podmnozinu SVG cest: M, L, H, V, C, S, Q, T, A, Z v absolutni
i relativni variante. Priznaky u oblouku (``A``) musi byt oddelene mezerou
nebo carkou, coz plati pro vsechny bezne exportery.
"""

from __future__ import annotations

import math
import re

from PySide6.QtGui import QPainterPath

_TOKEN_RE = re.compile(
    r"([MmZzLlHhVvCcSsQqTtAa])|([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)"
)

_ARGC = {
    "M": 2, "L": 2, "H": 1, "V": 1,
    "C": 6, "S": 4, "Q": 4, "T": 2,
    "A": 7, "Z": 0,
}


def fmt(value: float) -> str:
    """Cislo do SVG: max tri desetinna mista, bez zbytecnych nul."""
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-") else "0"


def _tokens(data: str):
    for match in _TOKEN_RE.finditer(data):
        if match.group(1):
            yield "cmd", match.group(1)
        else:
            yield "num", float(match.group(2))


def parse_path_data(data: str) -> tuple[QPainterPath, bool]:
    """Vrati cestu a priznak, zda byla uzavrena prikazem Z."""
    path = QPainterPath()
    closed = False
    cx = cy = 0.0
    start_x = start_y = 0.0
    last_c: tuple[float, float] | None = None  # ridici bod pro S
    last_q: tuple[float, float] | None = None  # ridici bod pro T
    started = False

    command: str | None = None
    args: list[float] = []

    def flush() -> None:
        nonlocal cx, cy, start_x, start_y, closed, last_c, last_q, started, command
        if command is None:
            return
        upper = command.upper()
        relative = command.islower()
        count = _ARGC[upper]

        if upper == "Z":
            if started:
                path.closeSubpath()
                closed = True
                cx, cy = start_x, start_y
            last_c = last_q = None
            return

        if count == 0 or not args:
            return

        index = 0
        first = True
        while index + count <= len(args):
            chunk = args[index:index + count]
            index += count
            code = upper
            # Opakovane parametry za M se chovaji jako L.
            if upper == "M" and not first:
                code = "L"

            if code == "M":
                x, y = chunk
                if relative:
                    x, y = cx + x, cy + y
                path.moveTo(x, y)
                cx = cy = 0.0
                cx, cy = x, y
                start_x, start_y = x, y
                started = True
                last_c = last_q = None
            elif code in ("L", "H", "V"):
                if code == "L":
                    x, y = chunk
                    if relative:
                        x, y = cx + x, cy + y
                elif code == "H":
                    x = cx + chunk[0] if relative else chunk[0]
                    y = cy
                else:
                    x = cx
                    y = cy + chunk[0] if relative else chunk[0]
                if not started:
                    path.moveTo(cx, cy)
                    started = True
                    start_x, start_y = cx, cy
                path.lineTo(x, y)
                cx, cy = x, y
                last_c = last_q = None
            elif code in ("C", "S"):
                if code == "C":
                    x1, y1, x2, y2, x, y = chunk
                    if relative:
                        x1, y1 = cx + x1, cy + y1
                        x2, y2 = cx + x2, cy + y2
                        x, y = cx + x, cy + y
                else:
                    x2, y2, x, y = chunk
                    if relative:
                        x2, y2 = cx + x2, cy + y2
                        x, y = cx + x, cy + y
                    if last_c is None:
                        x1, y1 = cx, cy
                    else:
                        x1, y1 = 2 * cx - last_c[0], 2 * cy - last_c[1]
                if not started:
                    path.moveTo(cx, cy)
                    started = True
                    start_x, start_y = cx, cy
                path.cubicTo(x1, y1, x2, y2, x, y)
                cx, cy = x, y
                last_c = (x2, y2)
                last_q = None
            elif code in ("Q", "T"):
                if code == "Q":
                    x1, y1, x, y = chunk
                    if relative:
                        x1, y1 = cx + x1, cy + y1
                        x, y = cx + x, cy + y
                else:
                    x, y = chunk
                    if relative:
                        x, y = cx + x, cy + y
                    if last_q is None:
                        x1, y1 = cx, cy
                    else:
                        x1, y1 = 2 * cx - last_q[0], 2 * cy - last_q[1]
                if not started:
                    path.moveTo(cx, cy)
                    started = True
                    start_x, start_y = cx, cy
                path.quadTo(x1, y1, x, y)
                cx, cy = x, y
                last_q = (x1, y1)
                last_c = None
            elif code == "A":
                rx, ry, rot, large, sweep, x, y = chunk
                if relative:
                    x, y = cx + x, cy + y
                if not started:
                    path.moveTo(cx, cy)
                    started = True
                    start_x, start_y = cx, cy
                _arc_to(path, cx, cy, rx, ry, rot, int(large) != 0, int(sweep) != 0, x, y)
                cx, cy = x, y
                last_c = last_q = None
            first = False

    for kind, value in _tokens(data):
        if kind == "cmd":
            flush()
            command = value
            args = []
            if value.upper() == "Z":
                flush()
                command = None
        else:
            args.append(value)
    flush()
    return path, closed


def _arc_to(path: QPainterPath, x1: float, y1: float, rx: float, ry: float,
            rotation: float, large_arc: bool, sweep: bool, x2: float, y2: float) -> None:
    """Elipticky oblouk prevedeny na kubicke bezierovy segmenty."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        path.lineTo(x2, y2)
        return

    phi = math.radians(rotation)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1.0:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale

    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    factor = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large_arc == sweep:
        factor = -factor
    cxp = factor * rx * y1p / ry
    cyp = -factor * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2.0

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        norm = math.hypot(ux, uy) * math.hypot(vx, vy)
        if norm == 0:
            return 0.0
        value = max(-1.0, min(1.0, (ux * vx + uy * vy) / norm))
        result = math.acos(value)
        return -result if ux * vy - uy * vx < 0 else result

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    theta = angle(1.0, 0.0, ux, uy)
    delta = angle(ux, uy, vx, vy)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi

    segments = max(1, int(math.ceil(abs(delta) / (math.pi / 2))))
    step = delta / segments
    alpha = 4.0 / 3.0 * math.tan(step / 4.0)

    def point(cos_t: float, sin_t: float) -> tuple[float, float]:
        return (cos_phi * rx * cos_t - sin_phi * ry * sin_t + cx,
                sin_phi * rx * cos_t + cos_phi * ry * sin_t + cy)

    def derivative(cos_t: float, sin_t: float) -> tuple[float, float]:
        return (-cos_phi * rx * sin_t - sin_phi * ry * cos_t,
                -sin_phi * rx * sin_t + cos_phi * ry * cos_t)

    for _ in range(segments):
        cos1, sin1 = math.cos(theta), math.sin(theta)
        theta2 = theta + step
        cos2, sin2 = math.cos(theta2), math.sin(theta2)
        p1 = point(cos1, sin1)
        p2 = point(cos2, sin2)
        d1 = derivative(cos1, sin1)
        d2 = derivative(cos2, sin2)
        path.cubicTo(p1[0] + alpha * d1[0], p1[1] + alpha * d1[1],
                     p2[0] - alpha * d2[0], p2[1] - alpha * d2[1],
                     p2[0], p2[1])
        theta = theta2


def path_to_data(path: QPainterPath, closed: bool = False) -> str:
    """Serializuje QPainterPath do atributu ``d``.

    Kazda uzavrena podcast dostane vlastni ``Z``. Qt uzavreni nezaznamenava
    zvlast, pozna se podle toho, ze podcast konci tam, kde zacala.
    """
    parts: list[str] = []
    index = 0
    count = path.elementCount()
    start: tuple[float, float] | None = None
    last: tuple[float, float] | None = None

    def close_if_needed() -> None:
        nonlocal start, last
        if start is None or last is None:
            return
        if abs(start[0] - last[0]) < 0.01 and abs(start[1] - last[1]) < 0.01:
            # Uzavirajici usecka je v zapisu nadbytecna, nahradi ji Z.
            if parts and parts[-1].startswith("L"):
                parts.pop()
            parts.append("Z")

    while index < count:
        element = path.elementAt(index)
        if element.type == QPainterPath.ElementType.MoveToElement:
            close_if_needed()
            parts.append(f"M {fmt(element.x)} {fmt(element.y)}")
            start = last = (element.x, element.y)
            index += 1
        elif element.type == QPainterPath.ElementType.LineToElement:
            parts.append(f"L {fmt(element.x)} {fmt(element.y)}")
            last = (element.x, element.y)
            index += 1
        elif element.type == QPainterPath.ElementType.CurveToElement and index + 2 < count:
            c1 = element
            c2 = path.elementAt(index + 1)
            end = path.elementAt(index + 2)
            parts.append(
                f"C {fmt(c1.x)} {fmt(c1.y)} {fmt(c2.x)} {fmt(c2.y)} {fmt(end.x)} {fmt(end.y)}"
            )
            last = (end.x, end.y)
            index += 3
        else:
            index += 1

    close_if_needed()
    if closed and (not parts or parts[-1] != "Z"):
        parts.append("Z")
    return " ".join(parts)
