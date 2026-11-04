"""Throttle handover: base wastegate pressure curve, KFVPDKSD and KFVPDKSE.

Port of Scripts/Utilities/GenerateBaseWGPressure.m, GenerateKFVPDKSD.m and
GenerateKFVPDKSE.m (the MED9.1 transform, here for ME7.6.2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from ..core.maps import CalibrationMap
from ..core.splatting import linear_1d
from . import axis_block, column

BASE_WG_MAX_DUTY = 10.0
HANDOVER_LOW = 0.95
HANDOVER_HIGH = 1.0
AUTO_AXIS_FIRST = (0.95, 1.0)
"""The first two points of an automatic pressure-ratio axis."""
AUTO_AXIS_TOP_FACTOR = 1.2
"""Top of the automatic axis: this times the highest base-wastegate pressure ratio."""
STOCK_BELOW_RATIO = 1.2
"""Rows of the automatic axis under this ratio keep the file's values."""
AUTO_AXIS_POINTS = 12


def pratio_axis_from_curve(curve, pu_constant: float, n_points: int = AUTO_AXIS_POINTS, *,
                           top_factor: float = AUTO_AXIS_TOP_FACTOR) -> np.ndarray | None:
    """0.95, 1.0, then even steps from 1.0 up to ``top_factor`` times the
    highest ratio of the base-wastegate curve; None without a usable peak."""
    c = np.asarray(curve, dtype=float).ravel()
    c = c[np.isfinite(c)]
    if c.size == 0 or n_points < len(AUTO_AXIS_FIRST) + 1 or pu_constant <= 0:
        return None
    top = float(c.max()) / pu_constant * top_factor
    if top <= AUTO_AXIS_FIRST[-1]:
        return None
    even = np.linspace(AUTO_AXIS_FIRST[-1], top, n_points - len(AUTO_AXIS_FIRST) + 1)[1:]
    return np.round(np.concatenate([AUTO_AXIS_FIRST, even]), 4)


def stock_rows(kfvp: np.ndarray, axis_rpm: np.ndarray, axis_pratio: np.ndarray, base: np.ndarray,
               base_axis_rpm: np.ndarray, base_axis_pratio: np.ndarray, below: float) -> tuple[np.ndarray, bool]:
    """Overwrite the rows of ``kfvp`` (rows = ratio, columns = rpm) whose ratio
    is under ``below`` with the file's values at the same rpm, read from the
    imported map (rows = rpm, columns = ratio) by interpolation along its
    axes, clamped to their range. Returns the map and whether it was done."""
    out = kfvp.copy()
    base = np.asarray(base, dtype=float)
    base_axis_rpm = np.asarray(base_axis_rpm, dtype=float).ravel()
    base_axis_pratio = np.asarray(base_axis_pratio, dtype=float).ravel()
    if base.shape != (base_axis_rpm.size, base_axis_pratio.size):
        if base.shape == (base_axis_pratio.size, base_axis_rpm.size):
            base = base.T
        else:
            return out, False
    rows = np.flatnonzero(np.asarray(axis_pratio, dtype=float) < below)
    for c, rpm_c in enumerate(np.asarray(axis_rpm, dtype=float).ravel()):
        at_rpm = np.array([np.interp(rpm_c, base_axis_rpm, base[:, j]) for j in range(base_axis_pratio.size)])
        out[rows, c] = np.interp(np.asarray(axis_pratio, dtype=float)[rows], base_axis_pratio, at_rpm)
    return out, True


def base_wg_pressure(data: pd.DataFrame, v: dict[str, str], min_samples: float,
                     axis_rpm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Boost against RPM using only rows where the wastegate is effectively closed."""
    wgdc = column(data, v["wgdc"])
    mask = wgdc < BASE_WG_MAX_DUTY
    rpm = column(data, v["rpm"])[mask]
    boost = column(data, v["boost"])[mask]
    return linear_1d(rpm, boost, axis_rpm, min_samples)


def box3_mean(m: np.ndarray) -> np.ndarray:
    """3 by 3 mean with edge replication (MATLAB pad + conv2 'valid'). NaN propagates."""
    p = np.pad(m, 1, mode="edge")
    acc = np.zeros_like(m)
    for dr in (0, 1, 2):
        for dc in (0, 1, 2):
            acc += p[dr:dr + m.shape[0], dc:dc + m.shape[1]]
    return acc / 9.0


def generate_kfvpdksd(curve: np.ndarray, axis_rpm: np.ndarray, axis_pratio: np.ndarray,
                      pu_constant: float) -> np.ndarray:
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_pratio = np.asarray(axis_pratio, dtype=float).ravel()
    curve = np.asarray(curve, dtype=float).ravel()
    valid = ~np.isnan(curve)
    if valid.sum() >= 2:
        f = interp1d(axis_rpm[valid], curve[valid], kind="linear", fill_value="extrapolate")
        filled = f(axis_rpm)
    else:
        filled = curve

    m = np.ones((axis_pratio.size, axis_rpm.size))
    for c in range(axis_rpm.size):
        if np.isnan(filled[c]):
            m[:, c] = np.nan
            continue
        base_ratio = filled[c] / pu_constant
        m[:, c] = np.where(base_ratio > axis_pratio, HANDOVER_LOW, HANDOVER_HIGH)

    valid_mask = ~np.isnan(m)
    if valid_mask.any():
        sm = np.clip(box3_mean(m), HANDOVER_LOW, HANDOVER_HIGH)
        sm[~valid_mask] = np.nan
        m = sm
    return m


def generate_handover_maps(data: pd.DataFrame, v: dict[str, str], *, min_samples_base_wg: float,
                           ambient_pressure: float, axis_rpm: np.ndarray, axis_pratio: np.ndarray,
                           auto_axis: bool = False, base_map: np.ndarray | None = None,
                           base_axis_rpm: np.ndarray | None = None, base_axis_pratio: np.ndarray | None = None,
                           stock_below: float = STOCK_BELOW_RATIO,
                           messages: list[str] | None = None) -> list[CalibrationMap]:
    """Base-wastegate pressure curve and KFVPDKSD.

    With ``auto_axis`` the pressure-ratio axis is rebuilt from the curve's
    peak (see :func:`pratio_axis_from_curve`) and written out as a block; the
    rows under ``stock_below`` keep the imported map's values when it is given.
    """
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_pratio = np.asarray(axis_pratio, dtype=float).ravel()
    curve, counts = base_wg_pressure(data, v, min_samples_base_wg, axis_rpm)
    maps = [CalibrationMap("base_press", "Base WG Pressure (Abs mbar)", curve, axis_rpm, ["Base Boost"],
                           counts=counts, counts_title="Base WG - SAMPLE WEIGHTS")]
    new_axis = None
    if auto_axis:
        n_points = axis_pratio.size if axis_pratio.size >= len(AUTO_AXIS_FIRST) + 1 else AUTO_AXIS_POINTS
        new_axis = pratio_axis_from_curve(curve, ambient_pressure, n_points)
        if new_axis is None:
            messages.append("Auto axis KFVPDKSD: no base-wastegate peak above ambient in the logs, factory axis kept.")
        else:
            peak = float(np.nanmax(curve))
            messages.append(f"Auto axis KFVPDKSD: base-WG peak {peak:.0f} hPa, ratio {peak / ambient_pressure:.3f} "
                            f"x {AUTO_AXIS_TOP_FACTOR:g} = {new_axis[-1]:.3f} at the top; "
                            f"axis {', '.join(f'{a:g}' for a in new_axis)}.")
            axis_pratio = new_axis
            maps.append(axis_block("pratio_axis_kfvp", "KFVPDKSD pressure-ratio axis (paste into WinOLS)", new_axis, "Ratio"))
    kfvp = generate_kfvpdksd(curve, axis_rpm, axis_pratio, ambient_pressure)
    if new_axis is not None:
        under = int((axis_pratio < stock_below).sum())
        if base_map is None or base_axis_rpm is None or base_axis_pratio is None:
            messages.append(f"Auto axis KFVPDKSD: no imported map, the {under} rows under {stock_below:g} follow the pattern.")
        else:
            kfvp, done = stock_rows(kfvp, axis_rpm, axis_pratio, base_map, base_axis_rpm, base_axis_pratio, stock_below)
            messages.append(f"Auto axis KFVPDKSD: {under} rows under {stock_below:g} kept at the imported values."
                            if done else "Auto axis KFVPDKSD: imported map does not match its axes, rows under "
                                         f"{stock_below:g} follow the pattern.")
    maps.append(CalibrationMap("kfvp", "KFVPDKSD (Steady State Throttle Handover)", kfvp, axis_rpm, axis_pratio))
    return maps


ZERO_DUTY = 0.5
"""Rows at or under this duty are the 0 % pull: the gate on its spring alone."""


def _held(axis_from, values, axis_to) -> np.ndarray:
    """``values`` on ``axis_from`` read at ``axis_to``: linear, held flat past the ends, NaN skipped."""
    axis_from, values = np.asarray(axis_from, dtype=float).ravel(), np.asarray(values, dtype=float).ravel()
    ok = np.isfinite(values)
    return np.interp(np.asarray(axis_to, dtype=float).ravel(), axis_from[ok], values[ok])


def generate_kfvpdkse(data: pd.DataFrame, v: dict[str, str], *, min_samples: float, ambient_pressure: float,
                      axis_rpm: np.ndarray, axis_ratio: np.ndarray,
                      max_ratio_curves: list[tuple[np.ndarray, np.ndarray]],
                      plgru: np.ndarray | None = None,
                      messages: list[str] | None = None) -> list[CalibrationMap]:
    """KFVPDKSE, the steady-state target pressure ratio over the throttle, on
    its normalised axis (ps - plgru) / (plsolmax - plgru).

    The measured base boost is the boost of the WOT rows at 0 % duty (the
    0 % pull), held flat outside the rpm it covers. ``plgru`` is the ECU's
    base boost on ``axis_rpm`` (hPa abs, ME7.6.2: pu + DPLPU), which defines
    the axis; without it the measured base boost stands in. The highest
    target plsolmax is the lowest of the compressor pressure-ratio limits
    given (ME7.6.2: VVMDXSN for altitude, VVNTUXS for turbo overspeed) times
    the ambient pressure. Each cell stands for the absolute pressure plgru +
    ratio x (plsolmax - plgru) at its rpm and takes the ME7 KFVPDKSD value
    there, judged against the measured base boost: 0.95 below it, 1.0 above,
    3 x 3 smoothed on the automatic ratio axis (MATLAB GenerateKFVPDKSE for
    MED9.1).
    """
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_ratio = np.asarray(axis_ratio, dtype=float).ravel()
    zero = column(data, v["wgdc"]) <= ZERO_DUTY
    rpm, boost = column(data, v["rpm"])[zero], column(data, v["boost"])[zero]
    base_raw, counts = linear_1d(rpm, boost, axis_rpm, min_samples)
    if np.isfinite(base_raw).sum() < 2:
        raise ValueError(f"KFVPDKSE needs a WOT pull at 0 % duty: {int(zero.sum())} WOT rows at 0 %, "
                         "fewer than two rpm points with data.")
    base = _held(axis_rpm, base_raw, axis_rpm)
    if not max_ratio_curves:
        raise ValueError("KFVPDKSE needs the compressor pressure-ratio limit (VVMDXSN) for the highest target boost.")
    limit = np.min([_held(a, r, axis_rpm) for a, r in max_ratio_curves], axis=0)
    ecu_base = base if plgru is None else np.asarray(plgru, dtype=float).ravel()
    top = np.maximum(limit * ambient_pressure, ecu_base + 1.0)

    grid = pratio_axis_from_curve(base, ambient_pressure)
    if grid is None:
        grid = np.round(np.linspace(HANDOVER_LOW, float(top.max()) / ambient_pressure, AUTO_AXIS_POINTS), 4)
    me7 = generate_kfvpdksd(base, axis_rpm, grid, ambient_pressure)

    target = ecu_base[None, :] + axis_ratio[:, None] * (top - ecu_base)[None, :]
    kfvpdkse = np.empty_like(target)
    for c in range(axis_rpm.size):
        kfvpdkse[:, c] = np.interp(target[:, c] / ambient_pressure, grid, me7[:, c])
    kfvpdkse = np.minimum(kfvpdkse, HANDOVER_HIGH)

    covered = axis_rpm[np.isfinite(base_raw)]
    messages.append(
        f"KFVPDKSE: base boost from {int(zero.sum())} WOT rows at 0 % duty, {np.nanmin(base_raw):.0f} to "
        f"{np.nanmax(base_raw):.0f} hPa abs at {covered[0]:g} to {covered[-1]:g} rpm, held flat beyond; "
        + ("axis base = the measured one; " if plgru is None else
           f"axis base = the ECU's plgru, {ecu_base.min():.0f} to {ecu_base.max():.0f} hPa; ")
        + f"highest target = lowest pressure-ratio limit x {ambient_pressure:.0f} hPa, {top.min():.0f} to "
        f"{top.max():.0f} hPa; each cell takes the ME7 handover value (0.95 below the measured base boost, 1.0 "
        f"above, smoothed) at plgru + ratio x (top - plgru).")
    return [
        CalibrationMap("kfvpdkse_base", "KFVPDKSE base boost from the 0 % duty pull (hPa abs)", base_raw, axis_rpm,
                       ["Base boost"], counts=counts, counts_title="Base boost - SAMPLE WEIGHTS"),
        CalibrationMap("kfvpdkse_top", "KFVPDKSE highest target boost, pressure-ratio limit x ambient (hPa abs)",
                       top, axis_rpm, ["Max target"]),
        CalibrationMap("kfvpdkse_target", "KFVPDKSE: boost each cell stands for (hPa abs)", target, axis_rpm,
                       axis_ratio, corner_label="Ratio \\ RPM"),
        CalibrationMap("kfvpdkse", "KFVPDKSE (steady-state throttle pressure ratio, paste into WinOLS)", kfvpdkse,
                       axis_rpm, axis_ratio, corner_label="Ratio \\ RPM"),
    ]
