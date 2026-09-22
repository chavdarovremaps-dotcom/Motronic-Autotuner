"""A read-only Qt table model over a NumPy matrix with axis labels as headers."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class MatrixModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._m = np.zeros((0, 0))
        self._x: list[str] = []
        self._y: list[str] = []
        self._decimals = 4

    def set_matrix(self, values, x_labels=None, y_labels=None, decimals: int = 4) -> None:
        self.beginResetModel()
        self._m = np.atleast_2d(np.asarray(values, dtype=float)) if values is not None else np.zeros((0, 0))
        if self._m.size == 0:
            self._m = np.zeros((0, 0))
        self._x = list(x_labels) if x_labels else [str(i + 1) for i in range(self._m.shape[1])]
        self._y = list(y_labels) if y_labels else [str(i + 1) for i in range(self._m.shape[0])]
        self._decimals = decimals
        self.endResetModel()

    def clear(self) -> None:
        self.set_matrix(None)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self._m.shape[0]

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self._m.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            v = self._m[index.row(), index.column()]
            if np.isnan(v):
                return ""
            text = f"{v:.{self._decimals}f}"
            return text.rstrip("0").rstrip(".") if "." in text else text
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        labels = self._x if orientation == Qt.Orientation.Horizontal else self._y
        return labels[section] if section < len(labels) else str(section + 1)
