"""Knock-based timing removal for a base ignition map.

The logged knock correction (degrees of retard, sign ignored) is averaged
per cell of the ignition map's own grid. Where that average is non-zero
and above a floor, timing is removed in whole steps of the map's
resolution, rounding up: an average pull of 0.4 with a 0.375 step removes
0.75. The corrected map is the base map minus the removal, ready to paste.
"""

from __future__ import annotations

import numpy as np

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear

DEFAULT_STEP = 0.375
DEFAULT_MIN_PULL = 0.1
EPS = 1e-9


def timing_removal(mean_pull: np.ndarray, step: float, min_pull: float = 0.0) -> np.ndarray:
    """Round each average pull up to a whole number of steps.

    NaN, zero and averages below ``min_pull`` give 0. The floor matters because
    bilinear weighting leaks a sliver of a knock event into neighbouring cells,
    and without it those cells would lose a full step for an average of 0.001.
    """
    pull = np.nan_to_num(np.abs(mean_pull), nan=0.0)
    removal = np.ceil((pull - EPS) / step) * step
    removal[(pull <= EPS) | (pull < min_pull)] = 0.0
    return removal


def generate_knock_removal(
    x: np.ndarray,
    y: np.ndarray,
    knock: np.ndarray,
    *,
    base_map: np.ndarray,
    base_title: str,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    x_label: str,
    y_label: str,
    min_samples: float,
    step: float = DEFAULT_STEP,
    min_pull: float = DEFAULT_MIN_PULL,
    key: str = "iga",
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """``x`` and ``y`` are the logged coordinates on the map's own axes (``axis_x`` along
    columns, ``axis_y`` along rows); ``base_map`` is ``[len(axis_y), len(axis_x)]``."""
    messages = messages if messages is not None else []
    axis_x = np.asarray(axis_x, dtype=float).ravel()
    axis_y = np.asarray(axis_y, dtype=float).ravel()
    base = np.asarray(base_map, dtype=float)
    if base.shape != (axis_y.size, axis_x.size):
        raise ValueError(f"{base_title}: base map is {base.shape}, axes give {(axis_y.size, axis_x.size)}")

    mean_pull, counts = bilinear(x, y, np.abs(np.asarray(knock, dtype=float)), axis_x, axis_y, min_samples)
    removal = timing_removal(mean_pull, step, min_pull)
    corrected = base - removal

    cells = int((removal > 0).sum())
    ignored = int(((np.nan_to_num(mean_pull) > EPS) & (removal == 0)).sum())
    messages.append(
        f"{base_title}: {cells} cells pulled, max {removal.max():.3f} deg, step {step:g} deg; "
        f"{ignored} cells with an average pull under {min_pull:g} deg left alone."
    )
    corner = f"{y_label} \\ {x_label}"
    return [
        CalibrationMap(f"{key}_knock_avg", f"{base_title}: Knock Correction Average (deg)", mean_pull, axis_x, axis_y,
                       counts=counts, counts_title=f"{base_title}: Knock - SAMPLE WEIGHTS", corner_label=corner),
        CalibrationMap(f"{key}_removal", f"{base_title}: Timing Removal (deg)", removal, axis_x, axis_y, corner_label=corner),
        CalibrationMap(f"{key}_corrected", f"{base_title} Corrected (paste into TunerPro)", corrected,
                       axis_x, axis_y, corner_label=corner),
    ]
