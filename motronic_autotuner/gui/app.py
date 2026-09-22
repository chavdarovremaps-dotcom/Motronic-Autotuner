"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ..families.base import Family
from .main_window import MainWindow


def run(family: Family, argv: list[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Motronic Autotuner")
    window = MainWindow(family)
    window.show()
    return app.exec()
