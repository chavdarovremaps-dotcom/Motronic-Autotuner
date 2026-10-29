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


SPOOL_BOOST_SHARE = 90.0
"""Share of the peak boost (percent) that defines the spool point."""
SPOOL_DUTY_WINDOW = 5.0
"""Rows count as "gate shut" when their duty is within this many percent of the highest duty logged."""
SPOOL_BIN_RPM = 50.0
SPOOL_MIN_BIN_SAMPLES = 3
AXIS_POINTS = 16
AXIS_FINE_STEP, AXIS_COARSE_STEP = 250.0, 500.0
AXIS_POINTS_BELOW, AXIS_FINE_ABOVE = 4, 5


def detect_spool_rpm(rpm, rel_boost, wgdc, *, share: float = SPOOL_BOOST_SHARE, duty_window: float = SPOOL_DUTY_WINDOW,
                     bin_rpm: float = SPOOL_BIN_RPM, min_bin_samples: int = SPOOL_MIN_BIN_SAMPLES):
    """The lowest rpm at which the boost reaches ``share`` percent of the
    highest boost logged, on the rows whose wastegate duty is within
    ``duty_window`` of the highest duty (the turbo spooling with the gate
    shut). Boost is the median of each ``bin_rpm`` bin with at least
    ``min_bin_samples`` rows, so a single sample cannot set the point.
    Returns ``(rpm, info)`` or ``(None, info)``.
    """
    rpm = np.asarray(rpm, dtype=float)
    rel_boost = np.asarray(rel_boost, dtype=float)
    wgdc = np.asarray(wgdc, dtype=float)
    ok = np.isfinite(rpm) & np.isfinite(rel_boost) & np.isfinite(wgdc)
    if not ok.any():
        return None, {"rows": 0}
    top_duty = float(wgdc[ok].max())
    keep = ok & (wgdc >= top_duty - duty_window)
    bins = np.floor(rpm[keep] / bin_rpm) * bin_rpm
    medians: dict[float, float] = {}
    for b in np.unique(bins):
        sel = bins == b
        if int(sel.sum()) >= min_bin_samples:
            medians[float(b)] = float(np.median(rel_boost[keep][sel]))
    info = {"rows": int(keep.sum()), "top_duty": top_duty, "min_duty": top_duty - duty_window, "bins": len(medians),
            "share": share}
    if not medians:
        return None, info
    peak = max(medians.values())
    target = peak * share / 100.0
    info.update(peak=peak, target=target)
    return min(b for b, m in medians.items() if m >= target), info


def spool_rpm_axis(spool: float, *, n: int = AXIS_POINTS, fine: float = AXIS_FINE_STEP, coarse: float = AXIS_COARSE_STEP,
                   below: int = AXIS_POINTS_BELOW, fine_above: int = AXIS_FINE_ABOVE) -> np.ndarray:
    """The KFLDRL rpm axis built around the spool point: ``below`` fine steps
    under it, the spool itself, ``fine_above`` fine steps over it, then coarse
    steps snapped to multiples of the coarse step so the axis ends on a round
    number (3300 gives 2300 .. 4550 in 250s, then 5000 .. 7500)."""
    pts = [spool - fine * k for k in range(below, 0, -1)] + [spool + fine * k for k in range(0, fine_above + 1)]
    nxt = (np.floor(pts[-1] / coarse) + 1) * coarse
    while len(pts) < n:
        pts.append(nxt)
        nxt += coarse
    return np.array(pts[:n], dtype=float)
