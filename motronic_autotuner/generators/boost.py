"""Boost control: KFLDIMX, KFLDRL and the absolute WGDC map.

Port of Scripts/Utilities/GenerateBoostMaps.m.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import QhullError

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear
from . import column

MAX_PID_LIMIT = 100.0
WGDC_CLAMP_MAX = 95.0


def fill_gaps(values: np.ndarray, x_axis: np.ndarray, y_axis: np.ndarray) -> np.ndarray:
    """Replace NaN cells by linear interpolation inside the hull of valid
    cells and nearest-neighbour outside it (MATLAB scatteredInterpolant
    with 'linear', 'nearest'). Needs more than four valid cells."""
    valid = ~np.isnan(values)
    if valid.sum() <= 4:
        return values
    X, Y = np.meshgrid(x_axis, y_axis)
    pts = np.column_stack([X[valid], Y[valid]])
    vals = values[valid]
    try:
        out = LinearNDInterpolator(pts, vals)(X, Y)
    except QhullError:
        out = np.full_like(values, np.nan)
    miss = np.isnan(out)
    if miss.any():
        out[miss] = NearestNDInterpolator(pts, vals)(X[miss], Y[miss])
    return out


def generate_boost_maps(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    cwldimx: bool,
    ambient_pressure: float,
    min_samples: float,
    fill_missing: bool,
    axis_rpm: np.ndarray,
    axis_boost: np.ndarray,
    axis_kfldrl_x: np.ndarray,
    safety_margin: float = 0.0,
) -> list[CalibrationMap]:
    """``safety_margin`` is accepted for parity with the MATLAB signature; it was never applied there."""
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_boost = np.asarray(axis_boost, dtype=float).ravel()
    axis_kfldrl_x = np.asarray(axis_kfldrl_x, dtype=float).ravel()

    boost = column(data, v["boost"])
    rpm = column(data, v["rpm"])
    wgdc = column(data, v["wgdc"])
    rel_boost = boost - column(data, v["pu"]) if cwldimx else boost - ambient_pressure

    lo, hi = axis_boost[0], axis_boost.max()
    span = hi - lo
    ramp = (axis_boost - lo) / span * MAX_PID_LIMIT
    kfldimx = np.tile(ramp, (axis_rpm.size, 1))

    physical_boost_axis = lo + (axis_kfldrl_x / MAX_PID_LIMIT) * span
    kfldrl, kfldrl_counts = bilinear(rel_boost, rpm, wgdc, physical_boost_axis, axis_rpm, min_samples)
    if fill_missing:
        kfldrl = fill_gaps(kfldrl, physical_boost_axis, axis_rpm)
        kfldrl[:, -1] = MAX_PID_LIMIT
    kfldrl = np.clip(kfldrl, 0.0, WGDC_CLAMP_MAX)

    axis_boost_abs = axis_boost + ambient_pressure
    abs_wgdc, abs_counts = bilinear(boost, rpm, wgdc, axis_boost_abs, axis_rpm, min_samples)

    return [
        CalibrationMap("kfldimx", "KFLDIMX (Linear Converter Map)", kfldimx, axis_boost, axis_rpm),
        CalibrationMap(
            "kfldrl", "KFLDRL (Base Linearization - WGDC %)", kfldrl, axis_kfldrl_x, axis_rpm,
            counts=kfldrl_counts, counts_title="KFLDRL - SAMPLE WEIGHTS",
            secondary_x_label="Target Rel Boost (mbar)", secondary_x=physical_boost_axis,
        ),
        CalibrationMap(
            "abs_wgdc", "ABSOLUTE WGDC MAP (Abs Boost vs RPM)", abs_wgdc, axis_boost_abs, axis_rpm,
            counts=abs_counts, counts_title="ABS WGDC - SAMPLE WEIGHTS",
        ),
    ]
