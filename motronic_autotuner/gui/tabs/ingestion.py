"""Data Ingestion & Filtering tab: log folder, math parameters, import button and console."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from ...families.base import Family
from ..state import AppState
from ..widgets import Lamp, ParamForm

BACKUP_PROFILE_NAME = "Used_ECU_Profile.json"


class IngestionTab(QWidget):
    logs_ready = Signal()

    def __init__(self, family: Family, state: AppState, parent=None):
        super().__init__(parent)
        self.family = family
        self.state = state
        self._build()
        self.apply_preset()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        left = QWidget()
        lv = QVBoxLayout(left)
        box = QGroupBox("Data Ingestion")
        bv = QVBoxLayout(box)
        row = QHBoxLayout()
        self.edit_folder = QLineEdit()
        self.edit_folder.setPlaceholderText("Folder containing the raw CSV logs")
        self.btn_browse = QPushButton("Browse...")
        row.addWidget(QLabel("Logs folder"))
        row.addWidget(self.edit_folder, 1)
        row.addWidget(self.btn_browse)
        bv.addLayout(row)
        row2 = QHBoxLayout()
        self.btn_import = QPushButton("Import & Auto-Split Raw Logs")
        self.lamp = Lamp()
        row2.addWidget(self.btn_import, 1)
        row2.addWidget(QLabel("Status"))
        row2.addWidget(self.lamp)
        bv.addLayout(row2)
        lv.addWidget(box)

        self.form = ParamForm(self.family.params)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        lv.addWidget(scroll, 1)
        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel("Output"))
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        rv.addWidget(self.console, 1)
        splitter.addWidget(right)
        splitter.setSizes([620, 880])

        self.btn_browse.clicked.connect(self.on_browse)
        self.btn_import.clicked.connect(self.on_import)

    # ---- preset <-> fields --------------------------------------------------

    def apply_preset(self) -> None:
        self.form.set_values(self.state.preset.params)

    def sync_to_preset(self) -> None:
        self.state.preset.params.update(self.form.values())

    # ---- actions ------------------------------------------------------------

    def log(self, *lines: str) -> None:
        for line in lines:
            self.console.appendPlainText(line)

    def on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing Raw CSV Logs", self.edit_folder.text())
        if folder:
            self.edit_folder.setText(folder)

    def on_import(self) -> None:
        folder = self.edit_folder.text().strip()
        if not folder:
            self.on_browse()
            folder = self.edit_folder.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(self, "Missing Data", "Please select a valid folder containing your raw CSV logs.")
            return
        self.sync_to_preset()
        self.state.log_folder = folder
        self.lamp.set_state("busy")
        self.console.clear()
        self.log("Starting log ingestion...", "Applying transient filters... please wait.")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            try:
                self.state.preset.save(Path(folder) / BACKUP_PROFILE_NAME)
                backup_note = "Saved backup JSON profile to log folder."
            except OSError as exc:
                backup_note = f"Could not save backup JSON: {exc}"
            logs = self.family.ingest(folder, self.state.preset)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self.lamp.set_state("error")
            self.log("ERROR PROCESSING LOGS:", str(exc))
            return
        QApplication.restoreOverrideCursor()
        self.state.logs = logs
        self.state.result = None
        counts = logs.counts()
        self.log(*logs.messages)
        self.log(
            "--- SUCCESS: Logs Split & Filtered ---",
            f"FULL Data: {counts['full']} rows",
            f"WOT Data: {counts['wot']} rows",
            f"WARMUP Data: {counts['warmup']} rows",
            f"HOT Data: {counts['hot']} rows",
            backup_note,
            "Ready for Calibration Math.",
        )
        self.lamp.set_state("ok" if counts["full"] else "warn")
        self.logs_ready.emit()
