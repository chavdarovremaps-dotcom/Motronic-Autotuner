"""ECU Profile tab: logger variable mapping, pre-processing rules, profile
load/save and the map import (WinOLS export, or XDF plus binary) with its
map status table."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTableView, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...core import winols
from ...core.preset import Preset
from ...core.winols import MapStatus, status_from_preset
from ...families.base import Family
from ..state import AppState
from ..table_model import MatrixModel
from ..widgets import Lamp

STATUS_COLORS = {
    "ok": QColor("#c8f7c5"),
    "warn": QColor("#ffe0b2"),
    "missing": QColor("#f8c8c8"),
}


class ProfileTab(QWidget):
    preset_loaded = Signal()

    def __init__(self, family: Family, state: AppState, sync_params: Callable[[], None], parent=None):
        super().__init__(parent)
        self.family = family
        self.state = state
        self._sync_params = sync_params
        self._var_edits: dict[str, QLineEdit] = {}
        self._file_edits: dict[str, QLineEdit] = {}
        self._build()
        self.apply_preset()

    # ---- layout -------------------------------------------------------------

    def _build(self) -> None:
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # left column
        left = QWidget()
        lv = QVBoxLayout(left)
        actions = QGroupBox("Variable Profile Actions")
        ah = QHBoxLayout(actions)
        self.btn_load = QPushButton("Load Existing Profile")
        self.btn_save = QPushButton("Save As New Profile")
        ah.addWidget(self.btn_load)
        ah.addWidget(self.btn_save)
        lv.addWidget(actions)

        if len(self.family.log_sources) > 1:
            src_box = QGroupBox("Log Source")
            sf = QFormLayout(src_box)
            self.source_combo = QComboBox()
            for s in self.family.log_sources:
                self.source_combo.addItem(s.label, s.key)
            sf.addRow("Logs come from", self.source_combo)
            lv.addWidget(src_box)
        else:
            self.source_combo = None

        vars_box = QGroupBox("Logger Variable Mapping")
        vf = QFormLayout(vars_box)
        for key in self.family.default_vars:
            edit = QLineEdit()
            edit.setPlaceholderText(self.family.default_vars[key])
            self._var_edits[key] = edit
            vf.addRow(f"{self.family.var_labels.get(key, key)}  ({key})", edit)
        lv.addWidget(vars_box)

        prep_box = QGroupBox("Pre-Processing Rules")
        pf = QFormLayout(prep_box)
        self.chk_align = QCheckBox("Align timestamps across files")
        self.chk_5120 = QCheckBox("5120 mbar hack (double pressure columns)")
        self.edit_pressure_cols = QLineEdit()
        self.edit_pressure_cols.setPlaceholderText("pvdks_w, pu, ps_w")
        pf.addRow(self.chk_align)
        if self.family.show_pressure_hack:
            pf.addRow(self.chk_5120)
            pf.addRow("Pressure columns", self.edit_pressure_cols)
        lv.addWidget(prep_box)
        lv.addStretch(1)
        splitter.addWidget(left)

        # right column
        right = QWidget()
        rv = QVBoxLayout(right)
        imp = QGroupBox(self.family.map_importer.label)
        grid = QGridLayout(imp)
        for row, inp in enumerate(self.family.map_importer.inputs):
            edit = QLineEdit()
            edit.setReadOnly(True)
            btn = QPushButton("Browse...")
            btn.clicked.connect(lambda _=False, k=inp.key: self.on_browse_file(k))
            self._file_edits[inp.key] = edit
            grid.addWidget(QLabel(inp.label), row, 0)
            grid.addWidget(edit, row, 1)
            grid.addWidget(btn, row, 2)
        self.btn_import = QPushButton("Import maps")
        self.lamp = Lamp()
        grid.addWidget(self.btn_import, 0, 3)
        grid.addWidget(QLabel("Status"), 0, 4)
        grid.addWidget(self.lamp, 0, 5)
        grid.setColumnStretch(1, 1)
        rv.addWidget(imp)

        self.status_table = QTableWidget(0, 4)
        self.status_table.setHorizontalHeaderLabels(["Name", "Status", "Dimensions", "Calibration Area"])
        self.status_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.status_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.status_table.verticalHeader().setVisible(False)
        rv.addWidget(self.status_table, 2)

        rv.addWidget(QLabel("Map Viewer: click a map in the table above to view it"))
        self.viewer_model = MatrixModel(self)
        self.viewer = QTableView()
        self.viewer.setModel(self.viewer_model)
        self.viewer.horizontalHeader().setDefaultSectionSize(72)
        rv.addWidget(self.viewer, 3)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 1000])

        self.btn_load.clicked.connect(self.on_load)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_import.clicked.connect(self.on_import_maps)
        self.status_table.cellClicked.connect(self.on_status_clicked)

    # ---- preset <-> fields --------------------------------------------------

    def apply_preset(self) -> None:
        p = self.state.preset
        for key, edit in self._var_edits.items():
            edit.setText(p.vars.get(key, ""))
        self.chk_align.setChecked(bool(p.prep.get("align_timestamps", False)))
        self.chk_5120.setChecked(bool(p.prep.get("hack_5120", False)))
        self.edit_pressure_cols.setText(", ".join(p.prep.get("pressure_columns", [])))
        for key, edit in self._file_edits.items():
            edit.setText(str(p.files.get(key, "")))
        if self.source_combo is not None:
            idx = self.source_combo.findData(p.log_source)
            self.source_combo.setCurrentIndex(max(idx, 0))
        self.state.map_status = status_from_preset(p.base_maps, self.family.target_maps)
        self._fill_status_table()
        self.viewer_model.clear()
        loaded = sum(1 for r in self.state.map_status if r.ok)
        if loaded == len(self.family.target_maps):
            self.lamp.set_state("ok")
        elif loaded:
            self.lamp.set_state("warn")
        else:
            self.lamp.set_state("off")

    def read_fields(self) -> None:
        p = self.state.preset
        for key, edit in self._var_edits.items():
            p.vars[key] = edit.text().strip() or self.family.default_vars[key]
        p.prep["align_timestamps"] = self.chk_align.isChecked()
        if self.family.show_pressure_hack:
            p.prep["hack_5120"] = self.chk_5120.isChecked()
            p.prep["pressure_columns"] = [s.strip() for s in self.edit_pressure_cols.text().split(",") if s.strip()]
        for key, edit in self._file_edits.items():
            p.files[key] = edit.text().strip()
        if self.source_combo is not None:
            p.log_source = self.source_combo.currentData()

    # ---- actions ------------------------------------------------------------

    def on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ECU Profile to Load", "", "JSON profile (*.json)")
        if not path:
            return
        try:
            preset = Preset.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error loading JSON Profile: {exc}")
            return
        if preset.family != self.family.key:
            answer = QMessageBox.question(
                self, "Different family",
                f"This profile is for '{preset.family}', but this app is '{self.family.key}'. Load it anyway?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            preset.family = self.family.key
        self.family.fill_defaults(preset)
        self.state.preset = preset
        self.apply_preset()
        self.preset_loaded.emit()
        QMessageBox.information(self, "Load Complete", f"Successfully loaded Profile: {Path(path).name}")

    def on_save(self) -> None:
        self.read_fields()
        self._sync_params()
        path, _ = QFileDialog.getSaveFileName(self, "Save New ECU Template As", "", "JSON profile (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.state.preset.save(path)
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Could not save profile: {exc}")
            return
        QMessageBox.information(self, "Success", f"Successfully created Template: {Path(path).name}")

    def on_browse_file(self, key: str) -> bool:
        inp = next(i for i in self.family.map_importer.inputs if i.key == key)
        start = self._file_edits[key].text() or ""
        path, _ = QFileDialog.getOpenFileName(self, f"Select the {inp.label}", start, inp.filter)
        if not path:
            return False
        self._file_edits[key].setText(path)
        return True

    def on_import_maps(self) -> None:
        for inp in self.family.map_importer.inputs:
            if not self._file_edits[inp.key].text().strip() and not self.on_browse_file(inp.key):
                return
        self.read_fields()
        self.lamp.set_state("busy")
        try:
            result = self.family.import_maps(self.state.preset)
        except Exception as exc:
            self.lamp.set_state("error")
            QMessageBox.critical(self, "Error", f"Failed to import maps: {exc}")
            return
        p = self.state.preset
        p.axes = dict(result.axes)
        p.base_maps = dict(result.base_maps)
        self.state.map_status = result.rows
        self._fill_status_table()
        self.viewer_model.clear()
        self.lamp.set_state("warn" if result.missing else "ok")
        self.preset_loaded.emit()

    def on_status_clicked(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self.state.map_status):
            return
        name = self.state.map_status[row].name
        target = next((t for t in self.family.target_maps if t.winols_name == name), None)
        if target is None:
            return
        p = self.state.preset
        values = p.base_map(target.base_map_key)
        if values is None:
            self.viewer_model.clear()
            return
        x = p.axis(target.x_axis_key)
        y = p.axis(target.y_axis_key)
        self.viewer_model.set_matrix(
            values,
            [_fmt(v) for v in x] if x is not None else None,
            [_fmt(v) for v in y] if y is not None else None,
        )

    # ---- helpers ------------------------------------------------------------

    def _fill_status_table(self) -> None:
        rows = self.state.map_status
        self.status_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, text in enumerate((r.name, r.status, r.dims, r.area)):
                item = QTableWidgetItem(text)
                if c == 1:
                    item.setBackground(_status_color(r))
                self.status_table.setItem(i, c, item)


def _status_color(r: MapStatus) -> QColor:
    if r.ok:
        return STATUS_COLORS["ok"]
    if r.status == winols.STATUS_MISSING:
        return STATUS_COLORS["missing"]
    return STATUS_COLORS["warn"]


def _fmt(v: float) -> str:
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:g}"
