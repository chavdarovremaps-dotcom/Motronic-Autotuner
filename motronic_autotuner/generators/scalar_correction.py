"""Percent-error correction of a multiplicative base map.

A logged error in percent (a fuel trim, a lambda error) is averaged per
cell of the map's own grid and the base map is scaled by ``1 + error / 100``
where data exists. Cells without data keep their factory value.
"""

from __future__ import annotations

import numpy as np

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear


def generate_scalar_correction(
    x: np.ndarray,
    y: np.ndarray,
    error_pct: np.ndarray,
    *,
    base_map: np.ndarray,
    base_title: str,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    x_label: str,
    y_label: str,
    min_samples: float,
    key: str,
    error_title: str = "Error (%)",
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    messages = messages if messages is not None else []
    axis_x = np.asarray(axis_x, dtype=float).ravel()
    axis_y = np.asarray(axis_y, dtype=float).ravel()
    base = np.asarray(base_map, dtype=float)
    if base.shape != (axis_y.size, axis_x.size):
        raise ValueError(f"{base_title}: base map is {base.shape}, axes give {(axis_y.size, axis_x.size)}")

    error, counts = bilinear(x, y, error_pct, axis_x, axis_y, min_samples)
    has = ~np.isnan(error)
    corrected = np.where(has, base * (1.0 + error / 100.0), base)
    messages.append(
        f"{base_title}: {int(has.sum())} of {error.size} cells have data; "
        f"error {np.nanmin(error):+.2f} % to {np.nanmax(error):+.2f} %." if has.any() else f"{base_title}: no cells with data."
    )
    corner = f"{y_label} \\ {x_label}"
    return [
        CalibrationMap(f"{key}_error", f"{base_title}: {error_title}", error, axis_x, axis_y,
                       counts=counts, counts_title=f"{base_title}: SAMPLE WEIGHTS", corner_label=corner),
        CalibrationMap(f"{key}_corrected", f"{base_title} Corrected (paste into TunerPro)", corrected,
                       axis_x, axis_y, corner_label=corner),
    ]
