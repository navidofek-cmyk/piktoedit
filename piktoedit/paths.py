"""Kde editor hleda sablony, kresby a predlohy.

Pri spusteni ze zdrojaku je to primo projektova slozka. V zabalenem .exe
jsou sablony uvnitr souboru, takze se pri prvnim spusteni rozbali vedle nej -
odtud si je uzivatel muze doplnovat o vlastni.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Slozka s daty zabalenymi do .exe, jinak koren projektu."""
    packed = getattr(sys, "_MEIPASS", None)
    if packed:
        return Path(packed)
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Slozka, se kterou pracuje uzivatel."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


PROJECT_DIR = data_dir()
TEMPLATE_DIR = PROJECT_DIR / "sablony"
DRAWING_DIR = PROJECT_DIR / "piktogramy"
REFERENCE_DIR = PROJECT_DIR / "source_example"


def ensure_templates() -> None:
    """Rozbali zabalene sablony vedle .exe, pokud tam jeste nejsou."""
    source = bundle_dir() / "sablony"
    if not source.is_dir() or source.resolve() == TEMPLATE_DIR.resolve():
        return
    for file in source.rglob("*.svg"):
        target = TEMPLATE_DIR / file.relative_to(source)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(file, target)
        except OSError:
            # Zapis vedle .exe nemusi projit, treba na sitovem disku.
            return
