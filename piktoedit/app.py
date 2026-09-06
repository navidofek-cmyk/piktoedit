"""Spusteni aplikace."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .mainwindow import MainWindow
from .paths import ensure_templates


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    ensure_templates()
    app = QApplication(argv)
    app.setApplicationName("PiktoEdit")
    app.setOrganizationName("AAC")

    path = argv[1] if len(argv) > 1 else None
    window = MainWindow(path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
