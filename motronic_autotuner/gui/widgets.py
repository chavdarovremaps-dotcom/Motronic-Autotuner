"""Small reusable widgets: a status lamp and a form generated from ParamSpecs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QHeaderView, QLabel,
    QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
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
    """Input fields from a list of ParamSpec, read back as a dict.

    Each group is a box. A family that names sections gets one tab per
    section; every page scrolls on its own, so the form brings its own
    scrolling. Labels line up across the boxes of a page, numbers sit in
    fields of one width with their unit after the value, the long
    explanation is the tooltip, and a field with ``enabled_when`` greys out
    while the setting it depends on says it is not used.
    """

    NUMBER_WIDTH = 130

    def __init__(self, specs: list[ParamSpec], parent=None):
        super().__init__(parent)
        self._widgets: dict[str, tuple[ParamSpec, QWidget]] = {}
        self._labels: dict[str, QLabel] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget() if any(spec.section for spec in specs) else None
        if self.tabs is not None:
            outer.addWidget(self.tabs)
        pages: dict[str, QVBoxLayout] = {}
        page_labels: dict[str, list[QLabel]] = {}
        forms: dict[tuple[str, str], QFormLayout] = {}
        for spec in specs:
            section = spec.section or "Settings"
            if section not in pages:
                pages[section] = self._page(section, outer)
                page_labels[section] = []
            form = forms.get((section, spec.group))
            if form is None:
                box = QGroupBox(spec.group.replace("&", "&&"))
                form = QFormLayout(box)
                form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                forms[(section, spec.group)] = form
                pages[section].addWidget(box)
            widget = self._make(spec)
            label = QLabel(spec.label)
            if spec.tip:
                label.setToolTip(spec.tip)
                widget.setToolTip(spec.tip)
            if spec.kind == "curve":
                label.setWordWrap(True)
                form.addRow(label)
                form.addRow(widget)
            else:
                form.addRow(label, widget)
                page_labels[section].append(label)
            self._widgets[spec.key] = (spec, widget)
            self._labels[spec.key] = label
        for section, layout in pages.items():
            layout.addStretch(1)
            labels = page_labels[section]
            if labels:
                width = max(lbl.sizeHint().width() for lbl in labels)
                for lbl in labels:
                    lbl.setMinimumWidth(width)
        for spec, _widget in self._widgets.values():
            if spec.enabled_when and spec.enabled_when[0] in self._widgets:
                self._watch(self._widgets[spec.enabled_when[0]][1])
        self._refresh()

    def _page(self, section: str, outer: QVBoxLayout) -> QVBoxLayout:
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        if self.tabs is not None:
            self.tabs.addTab(scroll, section.replace("&", "&&"))
        else:
            outer.addWidget(scroll)
        return layout

    def _watch(self, w: QWidget) -> None:
        if isinstance(w, QCheckBox):
            w.toggled.connect(self._refresh)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(self._refresh)
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.valueChanged.connect(self._refresh)

    def _refresh(self, *_args) -> None:
        for key, (spec, widget) in self._widgets.items():
            if not spec.enabled_when or spec.enabled_when[0] not in self._widgets:
                continue
            source, wanted = spec.enabled_when
            value = self.value(source)
            on = value in wanted if isinstance(wanted, tuple) else value == wanted
            widget.setEnabled(on)
            self._labels[key].setEnabled(on)

    @classmethod
    def _make(cls, spec: ParamSpec) -> QWidget:
        if spec.kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(spec.default))
            return w
        if spec.kind == "int":
            w = QSpinBox()
            w.setRange(int(max(spec.minimum, -2_000_000_000)), int(min(spec.maximum, 2_000_000_000)))
            w.setValue(int(spec.default))
            if spec.unit:
                w.setSuffix(f" {spec.unit}")
            w.setFixedWidth(cls.NUMBER_WIDTH)
            return w
        if spec.kind == "float":
            w = QDoubleSpinBox()
            w.setDecimals(spec.decimals)
            w.setRange(spec.minimum, spec.maximum)
            w.setValue(float(spec.default))
            if spec.unit:
                w.setSuffix(f" {spec.unit}")
            w.setFixedWidth(cls.NUMBER_WIDTH)
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
        self._refresh()
