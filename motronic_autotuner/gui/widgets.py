"""Small reusable widgets: a status lamp and a form generated from ParamSpecs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHeaderView, QLabel, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..families.base import ParamSpec

LAMP_COLORS = {
    "off": "#555555",
    "busy": "#f2c200",
    "ok": "#2ecc40",
    "warn": "#ff851b",
    "error": "#ff4136",
}


class Lamp(QLabel):
    """A coloured circle, like App Designer's uilamp."""

    def __init__(self, parent=None, size: int = 18):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.set_state("off")

    def set_state(self, state: str) -> None:
        color = LAMP_COLORS.get(state, LAMP_COLORS["off"])
        self.setStyleSheet(
            f"background-color: {color}; border-radius: {self._size // 2}px; border: 1px solid #333;"
        )
        self.setToolTip(state)


class CurveEditor(QTableWidget):
    """A curve as a two-row table: breakpoints on the first row, values on the
    second, edited cell by cell. A cell that is not a number goes back to its
    last value."""

    def __init__(self, x_label: str = "", y_label: str = "", decimals: int = 3, parent=None):
        super().__init__(2, 0, parent)
        self._decimals = (1, decimals)
        self._last: list[list[float]] = [[], []]
        self.setVerticalHeaderLabels([x_label or "X", y_label or "Y"])
        self.horizontalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setMinimumSectionSize(44)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.setFixedHeight(self.verticalHeader().length() + 2 * self.frameWidth() + 2)
        self.itemChanged.connect(self._check)

    def set_curve(self, curve: dict[str, Any]) -> None:
        x = [float(v) for v in curve["x"]]
        y = [float(v) for v in curve["y"]]
        if len(x) != len(y):
            raise ValueError("curve rows of different lengths")
        self.blockSignals(True)
        self.setColumnCount(len(x))
        for col, (a, b) in enumerate(zip(x, y)):
            for row, v in ((0, a), (1, b)):
                item = QTableWidgetItem(self._fmt(row, v))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, col, item)
        self.blockSignals(False)
        self._last = [x, y]

    def curve(self) -> dict[str, list[float]]:
        return {"x": list(self._last[0]), "y": list(self._last[1])}

    def _fmt(self, row: int, v: float) -> str:
        return f"{v:.{self._decimals[row]}f}"

    def _check(self, item: QTableWidgetItem) -> None:
        row, col = item.row(), item.column()
        try:
            self._last[row][col] = float(item.text().replace(",", "."))
        except ValueError:
            pass
        self.blockSignals(True)
        item.setText(self._fmt(row, self._last[row][col]))
        self.blockSignals(False)


class ParamForm(QWidget):
    """Builds grouped input fields from a list of ParamSpec and reads them back as a dict."""

    def __init__(self, specs: list[ParamSpec], parent=None):
        super().__init__(parent)
        self._widgets: dict[str, tuple[ParamSpec, QWidget]] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        forms: dict[str, QFormLayout] = {}
        for spec in specs:
            form = forms.get(spec.group)
            if form is None:
                box = QGroupBox(spec.group)
                form = QFormLayout(box)
                forms[spec.group] = form
                outer.addWidget(box)
            widget = self._make(spec)
            if spec.kind == "curve":
                form.addRow(QLabel(spec.label))
                form.addRow(widget)
            else:
                form.addRow(spec.label, widget)
            self._widgets[spec.key] = (spec, widget)
        outer.addStretch(1)

    @staticmethod
    def _make(spec: ParamSpec) -> QWidget:
        if spec.kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(spec.default))
            return w
        if spec.kind == "int":
            w = QSpinBox()
            w.setRange(int(max(spec.minimum, -2_000_000_000)), int(min(spec.maximum, 2_000_000_000)))
            w.setValue(int(spec.default))
            return w
        if spec.kind == "float":
            w = QDoubleSpinBox()
            w.setDecimals(spec.decimals)
            w.setRange(spec.minimum, spec.maximum)
            w.setValue(float(spec.default))
            return w
        if spec.kind == "choice":
            w = QComboBox()
            for label, value in spec.choices:
                w.addItem(label, value)
            idx = w.findData(spec.default)
            w.setCurrentIndex(max(idx, 0))
            return w
        if spec.kind == "curve":
            w = CurveEditor(spec.x_label, spec.y_label, spec.decimals)
            w.set_curve(spec.default)
            return w
        raise ValueError(f"unknown param kind {spec.kind!r}")

    def value(self, key: str) -> Any:
        spec, w = self._widgets[key]
        if spec.kind == "bool":
            return w.isChecked()
        if spec.kind in ("int", "float"):
            return w.value()
        if spec.kind == "curve":
            return w.curve()
        return w.currentData()

    def values(self) -> dict[str, Any]:
        return {key: self.value(key) for key in self._widgets}

    def set_values(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            if key not in self._widgets or value is None:
                continue
            spec, w = self._widgets[key]
            try:
                if spec.kind == "bool":
                    w.setChecked(bool(value))
                elif spec.kind == "int":
                    w.setValue(int(value))
                elif spec.kind == "float":
                    w.setValue(float(value))
                elif spec.kind == "curve":
                    w.set_curve(value)
                else:
                    idx = w.findData(value)
                    if idx >= 0:
                        w.setCurrentIndex(idx)
            except (TypeError, ValueError, KeyError):
                continue
