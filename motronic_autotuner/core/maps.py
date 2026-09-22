"""A calculated calibration map: values on named axes, with optional sample counts."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class CalibrationMap:
    key: str
    """Short identifier, e.g. ``"kfldrl"``. Unique within one calculation run."""

    title: str
    """Block title written to Excel and shown in the calculate tab."""

    values: np.ndarray
    """2D ``[len(y_axis), len(x_axis)]`` or 1D ``[len(x_axis)]``. NaN = no data."""

    x_axis: np.ndarray
    y_axis: np.ndarray | list[str] = field(default_factory=list)
    """Numeric breakpoints, or text labels for a 1D map (e.g. ``["Trim %"]``)."""

    counts: np.ndarray | None = None
    counts_title: str = ""
    secondary_x_label: str = ""
    secondary_x: np.ndarray | None = None
    """An extra header row under the x axis, e.g. physical boost targets for KFLDRL."""

    def as_2d(self) -> np.ndarray:
        return np.atleast_2d(np.asarray(self.values, dtype=float))

    def counts_2d(self) -> np.ndarray | None:
        return None if self.counts is None else np.atleast_2d(np.asarray(self.counts, dtype=float))

    def shape_label(self) -> str:
        v = self.as_2d()
        return f"{v.shape[0]}x{v.shape[1]}"

    @property
    def is_empty(self) -> bool:
        return self.values is None or np.asarray(self.values).size == 0

    def x_labels(self) -> list[str]:
        return [_fmt(v) for v in np.asarray(self.x_axis).ravel()]

    def y_labels(self) -> list[str]:
        if isinstance(self.y_axis, list):
            return [str(v) for v in self.y_axis]
        return [_fmt(v) for v in np.asarray(self.y_axis).ravel()]


def _fmt(v: float) -> str:
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:g}"
