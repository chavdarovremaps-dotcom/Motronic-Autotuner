"""Calculate tab: run every generator, show the status table, view a map, export to Excel."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTableView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...core.excel import export_maps
from ...families.base import Family
from ..state import AppState
from ..table_model import MatrixModel

DEFAULT_EXCEL_NAME = "ME_Tuning_Maps.xlsx"


class CalculateTab(QWidget):
    def __init__(self, family: Family, state: AppState, sync_params: Callable[[], None], parent=None):
        super().__init__(parent)
        self.family = family
        self.state = state
        self._sync_params = sync_params
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_calc = QPushButton("Calculate Maps && Export to Excel")
        self.btn_export = QPushButton("Export Again...")
        self.btn_export.setEnabled(False)
        top.addWidget(self.btn_calc)
        top.addWidget(self.btn_export)
        top.addStretch(1)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        lv = QVBoxLayout(left)
        self.status_table = QTableWidget(0, 3)
        self.status_table.setHorizontalHeaderLabels(["Map Name", "Status", "Size"])
        self.status_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.status_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.status_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.status_table.verticalHeader().setVisible(False)
        lv.addWidget(self.status_table, 3)
        lv.addWidget(QLabel("Messages"))
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        lv.addWidget(self.console, 1)
        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel("Map Viewer: click a map in the table to view it"))
        self.viewer_model = MatrixModel(self)
        self.viewer = QTableView()
        self.viewer.setModel(self.viewer_model)
        self.viewer.horizontalHeader().setDefaultSectionSize(72)
        rv.addWidget(self.viewer, 1)
        splitter.addWidget(right)
        splitter.setSizes([520, 1000])
        root.addWidget(splitter, 1)

        self.btn_calc.clicked.connect(self.on_calculate)
        self.btn_export.clicked.connect(self.on_export)
        self.status_table.cellClicked.connect(self.on_status_clicked)

    # ---- actions ------------------------------------------------------------

    def on_calculate(self) -> None:
        if self.state.logs is None or len(self.state.logs.full) == 0:
            QMessageBox.warning(self, "Missing Data", "Please process raw logs in the Data Ingestion tab first.")
            return
        self._sync_params()
        self.btn_calc.setText("Calculating Maps... Please Wait")
        self.btn_calc.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            result = self.family.run_all(self.state.preset, self.state.logs)
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_calc.setText("Calculate Maps && Export to Excel")
            self.btn_calc.setEnabled(True)
        self.state.result = result
        self._fill_status_table()
        self.console.setPlainText("\n".join(result.messages))
        self.viewer_model.clear()
        self.btn_export.setEnabled(bool(result.maps))
        if not result.maps:
            QMessageBox.warning(self, "Nothing calculated", "No map could be calculated. See the status table for why.")
            return
        self.on_export()

    def on_export(self) -> None:
        result = self.state.result
        if result is None or not result.maps:
            return
        default = str(Path(self.state.log_folder or ".") / DEFAULT_EXCEL_NAME)
        path, _ = QFileDialog.getSaveFileName(self, "Save Calculated Maps to Excel", default, "Excel (*.xlsx)")
        if not path:
            QMessageBox.information(self, "Notice", "Calculation complete, but Excel export was canceled.")
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            export_maps(path, result.maps)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Excel Export Error: {exc}")
            return
        QMessageBox.information(self, "Export Complete", f"Successfully exported to: {Path(path).name}")

    def on_status_clicked(self, row: int, _col: int) -> None:
        result = self.state.result
        if result is None or row < 0 or row >= len(result.rows):
            return
        m = result.map(result.rows[row].map_key) if result.rows[row].map_key else None
        if m is None:
            self.viewer_model.clear()
            return
        self.viewer_model.set_matrix(m.as_2d(), m.x_labels(), m.y_labels())

    def _fill_status_table(self) -> None:
        rows = self.state.result.rows if self.state.result else []
        self.status_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, text in enumerate((r.name, r.status, r.size)):
                item = QTableWidgetItem(text)
                if c == 1:
                    item.setBackground(_color(r.status))
                self.status_table.setItem(i, c, item)


def _color(status: str) -> QColor:
    if status == "Calculated":
        return QColor("#c8f7c5")
    if status.startswith("Error"):
        return QColor("#f8c8c8")
    return QColor("#ffe0b2")
