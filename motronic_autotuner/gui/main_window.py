"""The main window: one tab group built from the family declaration."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from ..families.base import Family
from .state import AppState
from .tabs.calculate import CalculateTab
from .tabs.ingestion import IngestionTab
from .tabs.profile import ProfileTab


class MainWindow(QMainWindow):
    def __init__(self, family: Family, parent=None):
        super().__init__(parent)
        self.family = family
        self.state = AppState(family=family, preset=family.default_preset())
        self.setWindowTitle(f"Motronic Autotuner - {family.display_name}")
        self.resize(1500, 950)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.ingestion = IngestionTab(family, self.state)
        self.profile = ProfileTab(family, self.state, sync_params=self.ingestion.sync_to_preset)
        self.calculate = CalculateTab(family, self.state, sync_params=self.ingestion.sync_to_preset)

        self.tabs.addTab(self.profile, "ECU Profile")
        self.tabs.addTab(self.ingestion, "Data Ingestion && Filtering")
        self.tabs.addTab(self.calculate, "Calculate")
        for tab_cls in family.extra_tabs:
            tab = tab_cls(family, self.state)
            self.tabs.addTab(tab, getattr(tab, "TITLE", tab_cls.__name__))

        self.profile.preset_loaded.connect(self.ingestion.apply_preset)
        self.ingestion.logs_ready.connect(lambda: self.statusBar().showMessage("Logs ready. Go to Calculate.", 5000))
        self.statusBar().showMessage(f"Family: {family.display_name}")
