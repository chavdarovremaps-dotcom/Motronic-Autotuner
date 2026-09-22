"""Knock-based timing removal for a base ignition map.

The logged knock correction (negative degrees of retard) is averaged per
cell of the ignition map's own RPM x load grid. Where that average is
non-zero, timing is removed in whole steps of the map's resolution,
rounding up: an average pull of 0.4 with a 0.375 step removes 0.75. The
corrected map is the base map minus the removal, ready to paste.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear
from . import column

DEFAULT_STEP = 0.375
EPS = 1e-9


def timing_removal(mean_pull: np.ndarray, step: float) -> np.ndarray:
    """Round each non-zero average pull up to a whole number of steps; NaN and zero give 0."""
    pull = np.nan_to_num(np.abs(mean_pull), nan=0.0)
    removal = np.ceil((pull - EPS) / step) * step
    removal[pull <= EPS] = 0.0
    return removal


def generate_knock_removal(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    base_map: np.ndarray,
    base_title: str,
    axis_rpm: np.ndarray,
    axis_load: np.ndarray,
    min_samples: float,
    step: float = DEFAULT_STEP,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """``base_map`` is ``[len(axis_rpm), len(axis_load)]``, RPM rows and load columns as in the XDF."""
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_load = np.asarray(axis_load, dtype=float).ravel()
    base = np.asarray(base_map, dtype=float)
    if base.shape != (axis_rpm.size, axis_load.size):
        raise ValueError(f"base ignition map is {base.shape}, axes give {(axis_rpm.size, axis_load.size)}")

    knock = np.abs(column(data, v["knock"]))
    mean_pull, counts = bilinear(column(data, v["load_ign"]), column(data, v["rpm"]), knock, axis_load, axis_rpm, min_samples)
    removal = timing_removal(mean_pull, step)
    corrected = base - removal

    cells = int((removal > 0).sum())
    messages.append(f"Knock removal: {cells} cells pulled, max {removal.max():.3f} deg, step {step:g} deg.")
    corner = "RPM \\ Load"
    return [
        CalibrationMap("knock_avg", "Knock Correction Average (deg CRK)", mean_pull, axis_load, axis_rpm,
                       counts=counts, counts_title="Knock - SAMPLE WEIGHTS", corner_label=corner),
        CalibrationMap("iga_removal", "Ignition Timing Removal (deg CRK)", removal, axis_load, axis_rpm, corner_label=corner),
        CalibrationMap("iga_corrected", f"{base_title} Corrected (deg CRK, paste into TunerPro)", corrected,
                       axis_load, axis_rpm, corner_label=corner),
    ]
