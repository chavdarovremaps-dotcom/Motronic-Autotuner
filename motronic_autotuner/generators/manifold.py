"""Intake manifold model (Saugrohrmodell).

KFURL slope and KFPRG intercept per RPM bin and VVT state, from a linear fit
of load against manifold pressure (port of
Scripts/Utilities/GenerateSaugrohrmodell.m, including the anchoring of
negative intercepts to 20 hPa and the physics bounds), and on top of that
line the non-linear correction maps KFPBRK (VVT off) and KFPBRKNW (VVT on).

The ECU model, as read from the ME7.5 function frame::

    rl = (ps * f - KFPRG) * KFURL        f = KFPBRK(rpm, rl) or KFPBRKNW(rpm, rl)
    ps = (rl / KFURL + KFPRG) / f

so for every logged row the factor that makes the fitted line hit the
logged pressure is ``(rl / KFURL + KFPRG) / ps``. The factors are averaged
per cell of the factory KFPBRK grid (rpm by load). Because the logged
pressure already contains the file's current factor, the result is the full
map value, not a multiplier on the factory map. ``apply_to="load"`` gives
the alternative reading of the frame, with the factor on the load:
``rl = (ps - KFPRG) * KFURL * f``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear
from . import column, column_ci
from .boost_feedforward import map_lookup

MIN_LOAD = 15.0
MIN_PRESSURE_RANGE = 20.0
ANCHOR_HPA = 20.0
INTERCEPT_MIN, INTERCEPT_MAX = -200.0, 800.0
RPM_EDGE_PAD = 200.0
PS_SATURATED = 2559.0
"""A 16-bit pressure word at its ceiling (2559.96 hPa) carries no information."""
FACTOR_MIN, FACTOR_MAX = 0.5, 2.0
MIN_PS_ABOVE_PIRG = 50.0


def _rpm_bin(axis_rpm: np.ndarray, r: int) -> tuple[float, float]:
    """Half-way edges of bin ``r``, padded at both ends of the axis."""
    target = axis_rpm[r]
    lo = target - RPM_EDGE_PAD if r == 0 else (axis_rpm[r - 1] + axis_rpm[r]) / 2
    hi = target + RPM_EDGE_PAD if r == axis_rpm.size - 1 else (axis_rpm[r] + axis_rpm[r + 1]) / 2
    return lo, hi


def _vvt_states(data: pd.DataFrame, v: dict[str, str], vvt_enabled: bool, vvt_threshold: float,
                messages: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """The VVT axis (one or two columns) and each row's column index."""
    axis_vvt = np.array([0.0, float(vvt_threshold)]) if vvt_enabled else np.array([0.0])
    vvt = column_ci(data, v.get("vvt", "")) if vvt_enabled else None
    if vvt is None:
        messages.append("  [INFO] VVT Disabled or missing. Forcing single-column calculation.")
        state = np.zeros(len(data), dtype=int)
    else:
        state = (vvt >= vvt_threshold).astype(int)
    return axis_vvt, state


def generate_manifold_maps(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    min_samples: float,
    vvt_enabled: bool,
    vvt_threshold: float,
    axis_rpm: np.ndarray,
    fit_load_max: float = 0.0,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """KFURL and KFPRG per RPM bin and VVT state.

    With ``fit_load_max`` above zero the line is fitted on rows up to that
    load, so the correction maps carry only the top of the load range, as
    the factory maps do; a bin without enough such rows falls back to all
    its rows and says so.
    """
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    rpm = column(data, v["rpm"])
    load = column(data, v["load"])
    if v["ps_w"] not in data.columns:
        raise KeyError(f"Intake pressure column ({v['ps_w']}) not found in logs.")
    ps = column(data, v["ps_w"])
    axis_vvt, state = _vvt_states(data, v, vvt_enabled, vvt_threshold, messages)

    n_rpm, n_vvt = axis_rpm.size, axis_vvt.size
    kfurl = np.full((n_rpm, n_vvt), np.nan)
    kfprg = np.full((n_rpm, n_vvt), np.nan)
    counts = np.zeros((n_rpm, n_vvt))

    for r in range(n_rpm):
        target_rpm = axis_rpm[r]
        rpm_min, rpm_max = _rpm_bin(axis_rpm, r)
        for c in range(n_vvt):
            idx = (rpm >= rpm_min) & (rpm < rpm_max) & (state == c) & (load > MIN_LOAD)
            bin_ps, bin_load = ps[idx], load[idx]
            if fit_load_max > 0 and bin_ps.size:
                low = bin_load <= fit_load_max
                enough = low.sum() >= max(min_samples, 2) and (bin_ps[low].max() - bin_ps[low].min()) > MIN_PRESSURE_RANGE
                if enough:
                    bin_ps, bin_load = bin_ps[low], bin_load[low]
                else:
                    messages.append(f"  [FIT] RPM: {target_rpm:g} | VVT: {axis_vvt[c]:g} | only {int(low.sum())} rows "
                                    f"below {fit_load_max:g} % load, fitted on all loads.")
            counts[r, c] = bin_ps.size
            if bin_ps.size == 0 or bin_ps.size < min_samples:
                continue
            if (bin_ps.max() - bin_ps.min()) <= MIN_PRESSURE_RANGE:
                continue

            m, b = np.polyfit(bin_ps, bin_load, 1)
            x_intercept = -b / m
            if x_intercept < 0:
                orig_intercept, orig_slope = x_intercept, m
                x_intercept = ANCHOR_HPA
                m = bin_load.mean() / (bin_ps.mean() - x_intercept)
                messages.append(
                    f"  [ANCHOR APPLIED] RPM: {target_rpm:g} | VVT: {axis_vvt[c]:g} | KFPRG was "
                    f"{orig_intercept:.1f} -> Anchored to {ANCHOR_HPA:g} hPa. KFURL recalculated from "
                    f"{orig_slope:.4f} to {m:.4f}"
                )
            if m > 0 and INTERCEPT_MIN <= x_intercept <= INTERCEPT_MAX:
                kfurl[r, c] = m
                kfprg[r, c] = x_intercept
            else:
                messages.append(
                    f"  [REJECTED] RPM: {target_rpm:g} | VVT: {axis_vvt[c]:g} | Slope: {m:.5f} | "
                    f"Intercept (PRG): {x_intercept:.1f}"
                )

    return [
        CalibrationMap("kfurl", "KFURL: Volumetric Efficiency Slope (% / hPa)", kfurl, axis_vvt, axis_rpm,
                       counts=counts, counts_title="KFURL - SAMPLE WEIGHTS"),
        CalibrationMap("kfprg", "KFPRG: Residual Exhaust Gas Pressure (hPa)", kfprg, axis_vvt, axis_rpm,
                       counts=counts, counts_title="KFPRG - SAMPLE WEIGHTS"),
    ]


def _model_pressure(load, fupsrl, pirg, f, apply_to: str) -> np.ndarray:
    """Pressure the ECU model gives for a load, with the correction factor in place."""
    if apply_to == "load":
        return load / (f * fupsrl) + pirg
    return (load / fupsrl + pirg) / f


def _rms_per_bin(axis_rpm_fit: np.ndarray, rpm: np.ndarray, err: np.ndarray) -> np.ndarray:
    out = np.full(axis_rpm_fit.size, np.nan)
    for r in range(axis_rpm_fit.size):
        lo, hi = _rpm_bin(axis_rpm_fit, r)
        sel = (rpm >= lo) & (rpm < hi)
        if sel.any():
            out[r] = float(np.sqrt(np.mean(err[sel] ** 2)))
    return out


def generate_pbrk_maps(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    kfurl: np.ndarray,
    kfprg: np.ndarray,
    axis_rpm_fit: np.ndarray,
    vvt_enabled: bool,
    vvt_threshold: float,
    axis_rpm: np.ndarray,
    axis_load: np.ndarray,
    base_map: np.ndarray | None,
    axis_rpm_nw: np.ndarray | None = None,
    axis_load_nw: np.ndarray | None = None,
    base_map_nw: np.ndarray | None = None,
    min_samples: float,
    apply_to: str = "pressure",
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """KFPBRK (VVT off) and KFPBRKNW (VVT on) from the residual of the fitted line.

    ``kfurl`` and ``kfprg`` are the maps just fitted on ``axis_rpm_fit``
    (rows) by VVT state (columns); they are interpolated along rpm for every
    row. Cells without data keep the factory value in the paste-ready map.
    A check table reports the model's pressure error per RPM bin before and
    after the correction.
    """
    messages = messages if messages is not None else []
    axis_rpm_fit = np.asarray(axis_rpm_fit, dtype=float).ravel()
    kfurl = np.asarray(kfurl, dtype=float)
    kfprg = np.asarray(kfprg, dtype=float)
    rpm = column(data, v["rpm"])
    load = column(data, v["load"])
    ps = column(data, v["ps_w"])
    _, state = _vvt_states(data, v, vvt_enabled, vvt_threshold, [])
    usable = (load > MIN_LOAD) & (ps < PS_SATURATED) & np.isfinite(ps) & np.isfinite(load)

    grids = {0: ("kfpbrk", "KFPBRK", axis_rpm, axis_load, base_map)}
    if vvt_enabled:
        grids[1] = ("kfpbrknw", "KFPBRKNW", axis_rpm_nw, axis_load_nw, base_map_nw)

    maps: list[CalibrationMap] = []
    check_rows: list[str] = []
    check_vals: list[np.ndarray] = []
    for c, (key, name, g_rpm, g_load, base) in grids.items():
        rows = usable & (state == c)
        label = "VVT ON" if c == 1 else "VVT OFF"
        if not rows.any():
            messages.append(f"  {name}: no {label} rows, skipped.")
            continue
        if g_rpm is None or g_load is None:
            messages.append(f"  {name}: axes not imported, the {label} rows are skipped.")
            continue
        if c >= kfurl.shape[1]:
            messages.append(f"  {name}: no fitted KFURL column for {label}, skipped.")
            continue
        valid = ~np.isnan(kfurl[:, c]) & ~np.isnan(kfprg[:, c])
        if valid.sum() < 2:
            messages.append(f"  {name}: fewer than two fitted RPM bins for {label}, skipped.")
            continue
        g_rpm = np.asarray(g_rpm, dtype=float).ravel()
        g_load = np.asarray(g_load, dtype=float).ravel()
        r_rpm, r_load, r_ps = rpm[rows], load[rows], ps[rows]
        fupsrl = np.interp(r_rpm, axis_rpm_fit[valid], kfurl[valid, c])
        pirg = np.interp(r_rpm, axis_rpm_fit[valid], kfprg[valid, c])
        ok = (r_ps - pirg) > MIN_PS_ABOVE_PIRG
        with np.errstate(divide="ignore", invalid="ignore"):
            if apply_to == "load":
                f = r_load / ((r_ps - pirg) * fupsrl)
            else:
                f = (r_load / fupsrl + pirg) / r_ps
        ok &= np.isfinite(f) & (f >= FACTOR_MIN) & (f <= FACTOR_MAX)
        if not ok.any():
            messages.append(f"  {name}: no usable {label} rows after the physics bounds, skipped.")
            continue
        factor, counts = bilinear(r_load[ok], r_rpm[ok], f[ok], g_load, g_rpm, min_samples)
        has = ~np.isnan(factor)
        if base is not None:
            base = np.asarray(base, dtype=float)
            if base.shape != factor.shape:
                messages.append(f"  {name}: factory map is {base.shape}, axes give {factor.shape}; "
                                "cells without data are left at 1.0.")
                base = None
        filled = np.where(has, factor, base if base is not None else 1.0)
        messages.append(f"  {name}: {int(has.sum())} of {factor.size} cells from {int(ok.sum())} {label} rows, "
                        f"factor {np.nanmin(factor):.4f} to {np.nanmax(factor):.4f} "
                        f"(factor on the {'load' if apply_to == 'load' else 'pressure'}).")

        corner = "RPM \\ Load %"
        maps.append(CalibrationMap(key, f"{name}: Load-to-Pressure Correction Factor ({label})", factor, g_load, g_rpm,
                                   counts=counts, counts_title=f"{name} - SAMPLE WEIGHTS", corner_label=corner))
        maps.append(CalibrationMap(f"{key}_corrected", f"{name} Corrected (paste into WinOLS)", filled, g_load, g_rpm,
                                   corner_label=corner))

        before = _model_pressure(r_load[ok], fupsrl[ok], pirg[ok], 1.0, apply_to) - r_ps[ok]
        f_map = map_lookup(filled, g_load, g_rpm, r_load[ok], r_rpm[ok])
        after = _model_pressure(r_load[ok], fupsrl[ok], pirg[ok], f_map, apply_to) - r_ps[ok]
        check_rows += [f"{label}: before {name} (hPa RMS)", f"{label}: after {name} (hPa RMS)"]
        check_vals += [_rms_per_bin(axis_rpm_fit, r_rpm[ok], before), _rms_per_bin(axis_rpm_fit, r_rpm[ok], after)]
        messages.append(f"  {name}: model pressure error {np.sqrt(np.mean(before ** 2)):.1f} hPa RMS before, "
                        f"{np.sqrt(np.mean(after ** 2)):.1f} hPa RMS after.")

    if check_vals:
        maps.append(CalibrationMap("pbrk_check", "Manifold model pressure error per RPM bin (hPa RMS)",
                                   np.vstack(check_vals), axis_rpm_fit, check_rows, corner_label="Check \\ RPM"))
    return maps
