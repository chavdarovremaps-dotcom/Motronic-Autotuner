"""Base boost curves (ME7.6.2 DPLPU / DPLPUR) from the 0 % duty pull.

The ECU's base boost is plgru_w = pu + DPLPU(nmot) (function BGPLGU); the
LDR measures its target from it (plsolr_w = plsol_w - plgru_w). DPLPUR
("real" base boost, LDRPLSBY) holds the same curve in the Astra H file.
Both are 4-point curves over rpm, so the boost logged at 0 % duty is fitted
as the line through the curve's own breakpoints by least squares, the way
the ECU interpolates it, and rounded to the 10 hPa step the curves store.
pu is not logged: each row's pu is the logged plgru_w minus the file's
DPLPU at that rpm (980 to 992 hPa on the Astra logs), else the ambient
setting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import locate
from . import column
from .handover import ZERO_DUTY

DPLPU_STEP = 10.0
"""hPa per bit: DPLPU and DPLPUR are bytes with factor 10."""
DPLPU_MAX = 2550.0


def ambient_per_row(data: pd.DataFrame, v: dict[str, str], dplpu_axis, dplpu_values,
                    fallback: float) -> tuple[np.ndarray, bool]:
    """pu of each row: logged plgru_w minus the file's DPLPU at the row's rpm,
    where both are there; else ``fallback``. Returns ``(pu, from_logs)``."""
    rpm = column(data, v["rpm"])
    col = v.get("plgru", "")
    if col and col in data.columns and dplpu_axis is not None and dplpu_values is not None:
        plgru = column(data, col)
        pu = plgru - np.interp(rpm, np.asarray(dplpu_axis, dtype=float).ravel(),
                               np.asarray(dplpu_values, dtype=float).ravel())
        if np.isfinite(pu).any():
            return np.where(np.isfinite(pu), pu, np.nanmedian(pu)), True
    return np.full(rpm.shape, float(fallback)), False


def fit_on_breakpoints(x, y, axis, *, min_weight: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """The piecewise-linear curve on ``axis`` (held flat outside it) that fits
    the points best by least squares. Each point loads its two neighbouring
    breakpoints by distance, as the ECU reads the curve. A breakpoint with
    less than ``min_weight`` is left out of the fit and interpolated from the
    others. Returns ``(values, weights)``; all NaN without two fitted points."""
    x, y = np.asarray(x, dtype=float).ravel(), np.asarray(y, dtype=float).ravel()
    axis = np.asarray(axis, dtype=float).ravel()
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    basis = np.zeros((x.size, axis.size))
    if x.size:
        i, f = locate(x, axis)
        rows = np.arange(x.size)
        basis[rows, i] += 1.0 - f
        inner = i < axis.size - 1
        basis[rows[inner], i[inner] + 1] += f[inner]
    weights = basis.sum(axis=0)
    keep = weights >= min_weight
    values = np.full(axis.size, np.nan)
    if keep.sum() >= 2:
        sol, *_ = np.linalg.lstsq(basis[:, keep], y, rcond=None)
        values[keep] = sol
        values = np.interp(axis, axis[keep], values[keep])
    elif keep.sum() == 1:
        values[:] = float(np.average(y, weights=basis[:, keep].ravel()))
    return values, weights


def generate_base_boost_maps(data: pd.DataFrame, v: dict[str, str], *,
                             curves: dict[str, tuple[np.ndarray, np.ndarray]], ambient_pressure: float,
                             min_samples: float = 1.0, messages: list[str] | None = None) -> list[CalibrationMap]:
    """DPLPU and DPLPUR (keys of ``curves``: name -> (rpm axis, file values))
    from the WOT rows at 0 % duty: boost above each row's pu, fitted on each
    curve's own axis. DPLPU, when given, also supplies the per-row pu."""
    messages = messages if messages is not None else []
    zero = column(data, v["wgdc"]) <= ZERO_DUTY
    if int(zero.sum()) < 2:
        raise ValueError(f"DPLPU / DPLPUR need a WOT pull at 0 % duty: {int(zero.sum())} WOT rows at 0 %.")
    dplpu = curves.get("DPLPU")
    pu, from_logs = ambient_per_row(data, v, *(dplpu if dplpu else (None, None)), fallback=ambient_pressure)
    rpm = column(data, v["rpm"])[zero]
    above = column(data, v["boost"])[zero] - pu[zero]
    pu_text = (f"pu from plgru_w - DPLPU, median {np.median(pu[zero]):.0f} hPa" if from_logs
               else f"pu = the ambient setting, {ambient_pressure:g} hPa")
    maps = []
    for name, (axis, file_values) in curves.items():
        axis = np.asarray(axis, dtype=float).ravel()
        fitted, weights = fit_on_breakpoints(rpm, above, axis, min_weight=min_samples)
        if not np.isfinite(fitted).any():
            messages.append(f"{name}: too few 0 % duty rows near its breakpoints, left as it is.")
            continue
        values = np.clip(np.round(fitted / DPLPU_STEP) * DPLPU_STEP, 0.0, DPLPU_MAX)
        old = np.asarray(file_values, dtype=float).ravel()
        messages.append(
            f"{name}: base boost above pu from {int(zero.sum())} WOT rows at 0 % duty ({pu_text}); "
            + ", ".join(f"{a:g} rpm {o:+.0f} -> {n:+.0f}" for a, o, n in zip(axis, old, values)) + " hPa.")
        maps.append(CalibrationMap(name.lower(), f"{name} (base boost above pu, paste into WinOLS)", values, axis,
                                   ["hPa"], counts=weights, counts_title=f"{name} - SAMPLE WEIGHTS"))
    return maps
