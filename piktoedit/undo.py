"""Zpet a znovu pres snimky cele kresby.

Kresby piktogramu jsou male, takze ulozit cely dokument jako SVG retezec je
levnejsi nez udrzovat prikaz pro kazdou moznou zmenu.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QUndoCommand, QUndoStack


class SnapshotCommand(QUndoCommand):
    def __init__(self, manager: "SnapshotManager", before: str, after: str, text: str):
        super().__init__(text)
        self.manager = manager
        self.before = before
        self.after = after
        self._skip_first = True

    def redo(self) -> None:
        # Prvni redo prijde hned pri vlozeni na zasobnik, kdy uz je stav platny.
        if self._skip_first:
            self._skip_first = False
            return
        self.manager.restore(self.after)

    def undo(self) -> None:
        self.manager.restore(self.before)


class SnapshotManager:
    def __init__(self, capture: Callable[[], str], restore: Callable[[str], None],
                 parent=None):
        # Zasobnik ma vlastnika, aby ho Qt nezrusilo drive nez okno.
        self.stack = QUndoStack(parent)
        self.stack.setUndoLimit(200)
        self._capture = capture
        self._restore = restore
        self.last = ""
        self._blocked = False

    def reset(self) -> None:
        self.last = self._capture()
        self.stack.clear()

    def snapshot(self, label: str) -> None:
        if self._blocked:
            return
        current = self._capture()
        if current == self.last:
            return
        self.stack.push(SnapshotCommand(self, self.last, current, label))
        self.last = current

    def restore(self, state: str) -> None:
        self._blocked = True
        try:
            self._restore(state)
            self.last = state
        finally:
            self._blocked = False
