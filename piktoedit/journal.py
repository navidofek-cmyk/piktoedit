"""Viditelna historie operaci.

Kazda uprava kresby zapise jeden radek, ktery rika, co se stalo a s cim.
Radky jsou zamerne psane jako prikazy - stejny zapis pozdeji posaji
prikazova radka a generovani, takze historie nebude jen popis, ale i
navod, jak kresbu zopakovat.

    13:42:05  obdelnik 256 256 448 336 --vypln #ffffff --obrys #000000
    13:42:11  nuz "Krivka" --v 512,480 --krizeni 2 --zbylo 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def number(value: float) -> str:
    """Cislo do zapisu: bez zbytecnych desetinnych mist."""
    text = f"{float(value):.1f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-") else "0"


def point(x: float, y: float) -> str:
    return f"{number(x)},{number(y)}"


def color(value) -> str:
    return value.name() if value is not None else "zadna"


def quoted(text: str) -> str:
    cleaned = str(text).replace('"', "'")
    return f'"{cleaned}"'


def style_args(style) -> str:
    """Spolecny zapis vyplne, obrysu a tloustky."""
    parts = [f"--vypln {color(style.fill)}", f"--obrys {color(style.stroke)}"]
    if style.stroke is not None:
        parts.append(f"--tloustka {number(style.stroke_width)}")
    if style.opacity < 1.0:
        parts.append(f"--kryti {number(style.opacity * 100)}")
    return " ".join(parts)


#: Nazvy tvaru v zapisu. Historie i budouci prikazova radka mluvi cesky.
KIND_NAMES = {
    "rect": "obdelnik",
    "ellipse": "elipsa",
    "line": "cara",
    "path": "krivka",
    "text": "text",
}


def kind_name(shape) -> str:
    return KIND_NAMES.get(getattr(shape, "kind", ""), getattr(shape, "kind", "tvar"))


def shape_line(shape) -> str:
    """Cely radek pro nove vznikly tvar."""
    return f"{kind_name(shape)} {shape_args(shape)}"


def shape_args(shape) -> str:
    """Popis tvaru tak, jak by sel zadat."""
    rect = shape.mapToScene(shape.local_rect()).boundingRect()
    parts = [f"{number(rect.x())} {number(rect.y())}",
             f"{number(rect.width())} {number(rect.height())}"]
    if shape.rotation():
        parts.append(f"--uhel {number(shape.rotation())}")
    parts.append(style_args(shape.style))
    return " ".join(parts)


@dataclass
class Entry:
    """Jeden radek historie."""

    time: datetime
    text: str

    def line(self) -> str:
        return f"{self.time:%H:%M:%S}  {self.text}"


@dataclass
class Journal:
    """Historie jedne kresby."""

    entries: list[Entry] = field(default_factory=list)
    #: Kolik radku se drzi; starsi se zahazuji, aby pamet nerostla donekonecna.
    limit: int = 2000

    def record(self, text: str) -> Entry:
        entry = Entry(datetime.now(), text.strip())
        self.entries.append(entry)
        if len(self.entries) > self.limit:
            del self.entries[:len(self.entries) - self.limit]
        return entry

    def clear(self, reason: str = "") -> None:
        self.entries.clear()
        if reason:
            self.record(reason)

    def lines(self) -> list[str]:
        return [entry.line() for entry in self.entries]

    def to_text(self, title: str = "") -> str:
        head = []
        if title:
            head.append(f"# {title}")
            head.append(f"# zapsano {datetime.now():%d.%m.%Y %H:%M}")
            head.append("")
        return "\n".join(head + self.lines()) + "\n"

    def save(self, path: str | Path, title: str = "") -> Path:
        target = Path(path)
        target.write_text(self.to_text(title), encoding="utf-8")
        return target

    def __len__(self) -> int:
        return len(self.entries)
