"""Small reusable widgets: a status lamp and a form generated from ParamSpecs."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout, QWidget,
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
        raise ValueError(f"unknown param kind {spec.kind!r}")

    def value(self, key: str) -> Any:
        spec, w = self._widgets[key]
        if spec.kind == "bool":
            return w.isChecked()
        if spec.kind in ("int", "float"):
            return w.value()
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
                else:
                    idx = w.findData(value)
                    if idx >= 0:
                        w.setCurrentIndex(idx)
            except (TypeError, ValueError):
                continue
