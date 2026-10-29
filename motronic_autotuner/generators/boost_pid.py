"""Boost PID for ME7: KFLDRQ0 (the P part) from the boost sensitivity in
forced-duty logs, on the KFLDRL rpm axis.

The logs are taken in open loop with the N75 duty forced through KFLDRAPP.
Per rpm point of the KFLDRL axis the mean boost is taken for every duty that
was held there; the steepest rise between neighbouring duties, normalised to
10 % duty, is the plant's highest sensitivity at that rpm. The P part is its
inverse, so that 100 hPa of deviation asks for the duty step that moves boost
by 100 hPa where the turbo is most sensitive:

    P [% per 100 hPa] = 1000 / (steepest rise in hPa per 10 % duty)

200 hPa per 10 % gives 5. Below the spool rpm the turbo cannot follow the
duty and the controller does no work, so those rows take the P of the first
rpm point after the spool. KFLDRQ0, KFLDRQ1, KFLDRQ2 and LDRQ1ST share one
ROM rpm axis, so all four are moved onto the KFLDRL axis; Q1, Q2 and
LDRQ1ST keep their values at the same rpm, and the I and D parts are left
for the tuner to set by hand.

The older rule, scaling all three gains by the ratio of the duty the logs
need over the duty the file holds (read from KFLDRL), stays as a choice.
"""

from __future__ import annotations

import numpy as np

from ..core.maps import CalibrationMap
from ..core.splatting import linear_1d
from . import axis_block
from .boost_feedforward import map_lookup

MIN_FILE_DUTY = 20.0
"""Duty-ratio rule: cells where the file's duty is below this do not enter the ratio."""
MIN_LEVEL_SAMPLES = 10.0
"""Sample weight a duty needs at an rpm point to count."""
MIN_DUTY_STEP = 4.0
"""Two duties closer than this are not compared: a 1 % gap would multiply the noise by ten."""


# ---- rescaling onto the KFLDRL axis -------------------------------------------


def rescale_rows(base: np.ndarray, base_axis_rpm: np.ndarray, new_axis_rpm: np.ndarray) -> np.ndarray:
    """A map with rpm down the rows (or a curve over rpm) moved onto another
    rpm axis by linear interpolation, clamped at the ends as the ECU does."""
    base = np.asarray(base, dtype=float)
    base_axis_rpm = np.asarray(base_axis_rpm, dtype=float).ravel()
    new_axis_rpm = np.asarray(new_axis_rpm, dtype=float).ravel()
    if base.ndim == 1 or base.shape[0] == 1:
        return np.interp(new_axis_rpm, base_axis_rpm, base.ravel())
    return np.column_stack([np.interp(new_axis_rpm, base_axis_rpm, base[:, j]) for j in range(base.shape[1])])


# ---- P from the boost sensitivity ---------------------------------------------


def boost_per_duty(rpm, boost, duty, axis_rpm, *, min_samples: float = MIN_LEVEL_SAMPLES):
    """Mean boost at every rpm point for every duty held there.

    Duties are rounded to whole percent. Rows are shared between the two
    nearest rpm points by distance, as everywhere else in the tool. Returns
    the duty levels, the table (levels x rpm points, NaN where the weight is
    below ``min_samples``) and the weights.
    """
    rpm = np.asarray(rpm, dtype=float)
    boost = np.asarray(boost, dtype=float)
    duty = np.round(np.asarray(duty, dtype=float))
    ok = np.isfinite(rpm) & np.isfinite(boost) & np.isfinite(duty)
    levels = np.unique(duty[ok])
    table = np.full((levels.size, np.asarray(axis_rpm).size), np.nan)
    weights = np.zeros_like(table)
    for i, level in enumerate(levels):
        sel = ok & (duty == level)
        table[i], weights[i] = linear_1d(rpm[sel], boost[sel], axis_rpm, min_samples)
    return levels, table, weights


def steepest_rise(levels: np.ndarray, column: np.ndarray, *, min_step: float = MIN_DUTY_STEP):
    """The steepest boost rise between duties at one rpm point, in hPa per 10 %
    duty, with the pair it came from. Each duty is compared with the nearest
    duty at least ``min_step`` above it. Returns ``(rise, low, high)`` or
    ``(nan, nan, nan)`` when no pair rises."""
    have = np.isfinite(column)
    lv, bv = np.asarray(levels, dtype=float)[have], np.asarray(column, dtype=float)[have]
    best = (np.nan, np.nan, np.nan)
    for i in range(lv.size):
        above = np.flatnonzero(lv >= lv[i] + min_step)
        if above.size == 0:
            continue
        j = above[0]
        rise = (bv[j] - bv[i]) / (lv[j] - lv[i]) * 10.0
        if rise > 0 and (np.isnan(best[0]) or rise > best[0]):
            best = (float(rise), float(lv[i]), float(lv[j]))
    return best


def p_from_sensitivity(levels, table, axis_rpm, spool_rpm, *, min_step: float = MIN_DUTY_STEP):
    """P per rpm point and the rows that fed it.

    Points below the spool rpm take the P of the first point at or after it.
    Points after the spool without a rising pair are interpolated between
    their neighbours, or hold the nearest value at the ends.
    """
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    n = axis_rpm.size
    rise, low, high = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    for c in range(n):
        rise[c], low[c], high[c] = steepest_rise(levels, table[:, c], min_step=min_step)
    p_raw = 1000.0 / rise
    after = axis_rpm >= spool_rpm if spool_rpm is not None else np.ones(n, dtype=bool)
    valid = after & np.isfinite(p_raw)
    p_used = np.full(n, np.nan)
    source = ["" for _ in range(n)]
    if not valid.any():
        return {"rise": rise, "low": low, "high": high, "p_raw": p_raw, "p_used": p_used, "source": source}
    first = np.flatnonzero(valid)[0]
    for c in range(n):
        if valid[c]:
            p_used[c], source[c] = p_raw[c], "logs"
        elif c < first:
            p_used[c], source[c] = p_raw[first], f"spool ({axis_rpm[first]:g})"
    gaps = np.isnan(p_used)
    if gaps.any():
        p_used[gaps] = np.interp(axis_rpm[gaps], axis_rpm[valid], p_raw[valid])
        for c in np.flatnonzero(gaps):
            source[c] = "interpolated"
    return {"rise": rise, "low": low, "high": high, "p_raw": p_raw, "p_used": p_used, "source": source}


# ---- the duty-ratio rule --------------------------------------------------------


def duty_ratio(new: np.ndarray, axis_rpm: np.ndarray, axis_x: np.ndarray, factory: np.ndarray,
               factory_axis_rpm: np.ndarray, factory_axis_x: np.ndarray, *,
               min_file_duty: float = MIN_FILE_DUTY) -> dict:
    """Per-rpm and overall ratio of the duty the logs show (computed KFLDRL)
    over the duty the file holds (imported KFLDRL, interpolated onto the
    computed grid), on cells with data where the file's duty is at least
    ``min_file_duty``. Each ratio is a sum over sums."""
    new = np.asarray(new, dtype=float)
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_x = np.asarray(axis_x, dtype=float).ravel()
    X, Y = np.meshgrid(axis_x, axis_rpm)
    file = map_lookup(np.asarray(factory, dtype=float), factory_axis_x, factory_axis_rpm, X.ravel(), Y.ravel()).reshape(new.shape)
    valid = np.isfinite(new) & np.isfinite(file) & (file >= min_file_duty)
    per_rpm = np.full(axis_rpm.size, np.nan)
    file_mean = np.full(axis_rpm.size, np.nan)
    new_mean = np.full(axis_rpm.size, np.nan)
    cells = valid.sum(axis=1)
    for r in range(axis_rpm.size):
        sel = valid[r]
        if sel.any():
            file_mean[r] = file[r, sel].mean()
            new_mean[r] = new[r, sel].mean()
            per_rpm[r] = new[r, sel].sum() / file[r, sel].sum()
    overall = float(new[valid].sum() / file[valid].sum()) if valid.any() else float("nan")
    return {"per_rpm": per_rpm, "overall": overall, "cells": cells, "file_mean": file_mean, "new_mean": new_mean,
            "axis_rpm": axis_rpm}


def ratio_factor(ratio: dict, mode: str) -> np.ndarray:
    """The factor per rpm point of the ratio's own axis: one overall number, or per rpm with gaps filled."""
    per = ratio["per_rpm"]
    ok = np.isfinite(per)
    if mode != "per_rpm" or not ok.any():
        return np.full(per.size, ratio["overall"])
    if ok.sum() == 1:
        return np.full(per.size, per[ok][0])
    return np.interp(ratio["axis_rpm"], ratio["axis_rpm"][ok], per[ok])


# ---- the generator --------------------------------------------------------------


def generate_pid_maps(*, axis_rpm: np.ndarray, q_maps: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
                      ldrq1st: tuple[np.ndarray, np.ndarray] | None, mode: str,
                      logs_rpm=None, logs_boost=None, logs_duty=None, spool_rpm: float | None = None,
                      kfldrl: CalibrationMap | None = None, factory_kfldrl=None, factory_axis_rpm=None,
                      factory_axis_x=None, min_samples: float = MIN_LEVEL_SAMPLES, min_step: float = MIN_DUTY_STEP,
                      min_file_duty: float = MIN_FILE_DUTY, messages: list[str] | None = None) -> list[CalibrationMap]:
    """``q_maps`` maps "KFLDRQ0" / "KFLDRQ1" / "KFLDRQ2" to ``(base, axis_rpm, axis_deviation)``.

    ``mode`` is "sensitivity" (P from the logs, Q1 and Q2 only moved onto the
    axis), or "overall" / "per_rpm" (all three scaled by the duty ratio).
    """
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    moved = {name: (rescale_rows(base, a_rpm, axis_rpm), np.asarray(a_dev, dtype=float).ravel())
             for name, (base, a_rpm, a_dev) in q_maps.items()}
    maps = [axis_block("rpm_axis_ldrq", "KFLDRQ0 / Q1 / Q2 / LDRQ1ST RPM axis (paste into WinOLS)", axis_rpm, "RPM")]
    corner = "RPM \\ Deviation hPa"
    factor = np.ones(axis_rpm.size)
    how = {name: "same values on the KFLDRL axis" for name in moved}

    if mode == "sensitivity":
        levels, table, weights = boost_per_duty(logs_rpm, logs_boost, logs_duty, axis_rpm, min_samples=min_samples)
        res = p_from_sensitivity(levels, table, axis_rpm, spool_rpm, min_step=min_step)
        if np.isnan(res["p_used"]).all():
            messages.append("Boost PID: no rpm point after the spool shows boost rising with duty, KFLDRQ0 not calculated.")
        else:
            q0, dev = moved["KFLDRQ0"]
            moved["KFLDRQ0"] = (np.tile(res["p_used"][:, None], (1, dev.size)), dev)
            how["KFLDRQ0"] = "P from the boost sensitivity"
            from_logs = [s == "logs" for s in res["source"]]
            messages.append(
                f"Boost PID: P from the logs at {sum(from_logs)} of {axis_rpm.size} rpm points, "
                f"{np.nanmin(res['p_used']):.2f} to {np.nanmax(res['p_used']):.2f} %/100 hPa; spool at "
                f"{spool_rpm:g} rpm, the points below it take the first P after it." if spool_rpm is not None else
                f"Boost PID: P from the logs at {sum(from_logs)} of {axis_rpm.size} rpm points.")
            file_p = q0[:, 0]
            maps.append(CalibrationMap(
                "ldr_sensitivity", "Boost sensitivity and P per rpm", np.vstack([
                    res["rise"], res["low"], res["high"], res["p_raw"], res["p_used"], file_p]),
                axis_rpm, ["Steepest rise (hPa per 10 % duty)", "From duty (%)", "To duty (%)",
                           "P from the logs (%/100 hPa)", "P used (%/100 hPa)", "File P on this axis"],
                corner_label="Sensitivity \\ RPM"))
            used = np.isfinite(table).any(axis=1)                           # duties with at least one usable cell
            maps.append(CalibrationMap(
                "ldr_boost_per_duty", "Mean boost per forced duty (hPa abs)", table[used], axis_rpm,
                [f"{lv:g} %" for lv in levels[used]], counts=weights[used], counts_title="Boost per duty - SAMPLE WEIGHTS",
                corner_label="Duty \\ RPM"))
    else:
        if kfldrl is None or factory_kfldrl is None:
            messages.append("Boost PID: the duty-ratio rule needs KFLDRL from the logs and from the file, nothing scaled.")
        else:
            ratio = duty_ratio(kfldrl.values, kfldrl.y_axis, kfldrl.x_axis, factory_kfldrl, factory_axis_rpm,
                               factory_axis_x, min_file_duty=min_file_duty)
            if not np.isfinite(ratio["overall"]):
                messages.append(f"Boost PID: no KFLDRL cell with data where the file's duty is at least "
                                f"{min_file_duty:g} %, nothing scaled.")
            else:
                factor = np.interp(axis_rpm, ratio["axis_rpm"], ratio_factor(ratio, mode))
                for name in moved:
                    base, dev = moved[name]
                    moved[name] = (base * factor[:, None], dev)
                    how[name] = "per rpm duty ratio" if mode == "per_rpm" else f"x {ratio['overall']:.3f}"
                messages.append(f"Boost PID: the logs need {ratio['overall']:.3f} of the duty in the file "
                                f"({int(ratio['cells'].sum())} KFLDRL cells); Q0, Q1 and Q2 scaled "
                                f"{'per rpm' if mode == 'per_rpm' else 'by that ratio'}.")
                maps.append(CalibrationMap(
                    "ldr_scale", f"LDR PID scale: duty from the logs over duty in the file (overall {ratio['overall']:.3f})",
                    np.vstack([ratio["file_mean"], ratio["new_mean"], ratio["per_rpm"], ratio["cells"].astype(float)]),
                    ratio["axis_rpm"], ["File duty % (used cells)", "Logged duty %", "Ratio", "Cells used"],
                    corner_label="Scale \\ RPM"))

    for name in ("KFLDRQ0", "KFLDRQ1", "KFLDRQ2"):
        if name in moved:
            values, dev = moved[name]
            maps.append(CalibrationMap(f"{name.lower()}_corrected", f"{name} ({how[name]}, paste into WinOLS)",
                                       values, dev, axis_rpm, corner_label=corner))
    if ldrq1st is not None:
        base, a_rpm = ldrq1st
        maps.append(CalibrationMap("ldrq1st_corrected", "LDRQ1ST (same values on the KFLDRL axis, paste into WinOLS)",
                                   rescale_rows(base, a_rpm, axis_rpm), axis_rpm, ["LDRQ1ST"]))
    return maps
