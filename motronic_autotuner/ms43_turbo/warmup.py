"""Warm-up enrichment: ip_ti_tco_wup_ron98 (and its idle twin) from cold-engine logs.

During warm-up the MS43X multiplies the injection time by 1 + E with

    E = base x fade
    base = ip_ti_wup_ron98__n__maf             (rpm down the rows, injection load across)
    fade = ip_ti_tco_wup_ron98__tco__tco_st    (coolant now down the rows, coolant at start across)
           ip_ti_tco_wup_is_ron98__tco__tco_st at idle

Checked on the 2026-10-31 warm-up log (v4 bin): the injection time over the
hot injection line matched base x fade at idle, and the overlap table
ip_ti_vo_wup does not scale the whole injection time.

The warm-up target lambda comes from the calibrator's own table of coolant
against lambda (a setting; 0.90 at 0 C rising to 1.00 at 60 C until changed),
linear between its points and held beyond its ends, and is applied to the
logged AFR target.
Per cold row (coolant below the warm-engine threshold, steady, outside fuel
cut, wideband live):

    f      = Wideband AFR / (AFR target x warm-up lambda) + trims / 100
    f_ve   = the VE correction the hot rows of the same run give at this
             row's VE cell: the base-fueling error, which is not warm-up.
             A row whose cell has no hot data is skipped, or taken with
             f_ve = 1 when the VE is assumed right.
    E_new  = (1 + E) x f / f_ve - 1
    wanted fade = E_new / base

The wanted fade is splatted on the fade table's grid with each row weighted
by base squared, which is a least-squares fit of the fade per cell; the base
table is left as it is. Cells are clipped to what the table can hold (0 and
up): a negative wanted fade means the engine runs richer than the target
even without warm-up enrichment, which the warm-up tables cannot fix.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from .splat import lookup_values, splat_values
from .ve import VE_TABLES, channel, has, row_factors, table_shares

FADE = "ip_ti_tco_wup_ron98__tco__tco_st"
FADE_IS = "ip_ti_tco_wup_is_ron98__tco__tco_st"
BASE = "ip_ti_wup_ron98__n__maf"
CORNER = "Coolant \\ Coolant at start"
TARGET_TCO = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 80.0)
TARGET_LAMBDA = (0.900, 0.917, 0.933, 0.950, 0.967, 0.983, 1.000, 1.000)
DEFAULT_TARGET = {"x": list(TARGET_TCO), "y": list(TARGET_LAMBDA)}
"""The calibrator's warm-up lambda by coolant (C): 0.90 at 0 C to 1.00 at 60 C until they change it."""
LAMBDA_MIN, LAMBDA_MAX = 0.5, 1.5
WARM_ENGINE = 80.0
"""Coolant (C) from which a row counts as a warm engine: VE, ip_maf_1_diag and ignition use only those."""
STEADY_WINDOW = 0.5
STEADY_RPM_RATE = 300.0
STEADY_LOAD_RATE = 100.0
FADE_MAX = 255 * 0.0078125
"""The fade tables store 8 bits at 1/128."""
SKIP, ASSUME = "skip", "assume"
MIN_CHECK_ROWS = 50


def target_curve(value) -> tuple[np.ndarray, np.ndarray]:
    """Coolant points and target lambdas from the setting; ValueError when the table is unusable."""
    try:
        x = np.asarray(value["x"], dtype=float).ravel()
        y = np.asarray(value["y"], dtype=float).ravel()
    except (TypeError, KeyError, ValueError):
        raise ValueError("Warm-up target lambda table is unreadable.") from None
    if x.size == 0 or x.size != y.size:
        raise ValueError("Warm-up target lambda table: the coolant and lambda rows need the same number of points.")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("Warm-up target lambda table: every point needs a number.")
    if (np.diff(x) <= 0).any():
        raise ValueError("Warm-up target lambda table: the coolant points must rise from left to right.")
    if ((y < LAMBDA_MIN) | (y > LAMBDA_MAX)).any():
        raise ValueError(f"Warm-up target lambda table: lambda must lie between {LAMBDA_MIN:g} and {LAMBDA_MAX:g}.")
    return x, y


def warmup_lambda(tco, target_tco=TARGET_TCO, target_lambda=TARGET_LAMBDA) -> np.ndarray:
    """The target lambda from the table: linear between its points, held beyond its ends."""
    return np.interp(np.asarray(tco, dtype=float), np.asarray(target_tco, dtype=float),
                     np.asarray(target_lambda, dtype=float))


def rate(time, values, window_s: float = STEADY_WINDOW) -> np.ndarray:
    """Rate of change per second over a window centred on each row (shortened at the ends)."""
    t = np.asarray(time, dtype=float)
    x = np.asarray(values, dtype=float)
    if t.size < 2:
        return np.zeros(t.size)
    h = window_s / 2.0
    lo, hi = np.maximum(t - h, t[0]), np.minimum(t + h, t[-1])
    span = hi - lo
    return np.where(span > 0, (np.interp(hi, t, x) - np.interp(lo, t, x)) / np.where(span > 0, span, 1.0), 0.0)


def steady_rows(time, rpm, load, *, window_s=STEADY_WINDOW, max_rpm_rate=STEADY_RPM_RATE,
                max_load_rate=STEADY_LOAD_RATE) -> np.ndarray:
    return ((np.abs(rate(time, rpm, window_s)) <= max_rpm_rate)
            & (np.abs(rate(time, load, window_s)) <= max_load_rate))


def start_info(time, start_flag, coolant) -> tuple[np.ndarray, np.ndarray, bool]:
    """Seconds after start and coolant at start, per row of one log file.

    A start ends where the Engine Start flag goes off; rows before the first
    start get NaN. Without a start in the file the coolant at start is the
    first logged coolant, the seconds after start are unknown (NaN), and the
    third value is False."""
    t = np.asarray(time, dtype=float)
    cool = np.asarray(coolant, dtype=float)
    n = t.size
    on = np.zeros(n, dtype=bool) if start_flag is None else np.asarray(start_flag, dtype=float) == 1
    ends = np.flatnonzero(on[:-1] & ~on[1:]) + 1
    if ends.size == 0:
        return np.full(n, np.nan), np.full(n, cool[0] if n else np.nan), False
    t_ast, tco_st = np.full(n, np.nan), np.full(n, np.nan)
    for i, e in enumerate(ends):
        stop = ends[i + 1] if i + 1 < ends.size else n
        t_ast[e:stop] = t[e:stop] - t[e]
        tco_st[e:stop] = cool[e]
    return t_ast, tco_st, True


def hot_ve_error(data: pd.DataFrame, v: dict[str, str], factor_hot: np.ndarray, *, axis_rpm, axis_map,
                 min_weight: float) -> np.ndarray:
    """Per row, the VE correction factor the hot rows give at that row's VE cell (NaN without hot data there)."""
    shares = table_shares(channel(data, v["ve_table"]))
    rpm, mp = channel(data, v["rpm"]), channel(data, v["map"])
    out = np.zeros(len(data))
    for k in range(1, VE_TABLES + 1):
        need = shares[:, k - 1] > 0
        if not need.any():
            continue
        w = np.where(np.isfinite(factor_hot), shares[:, k - 1], 0.0)
        if not (w > 0).any():
            out[need] = np.nan
            continue
        grid = splat_values(rpm, mp, factor_hot, axis_rpm, axis_map, min_weight, row_weight=w).values
        at = lookup_values(grid, axis_rpm, axis_map, rpm, mp)
        out += np.where(need, shares[:, k - 1] * at, 0.0)
    return out


def _fit_table(name, key, factory, axis_tco, axis_tco_st, tco, tco_st, wanted, base, used, min_weight, messages):
    """Least-squares fade per cell; returns the maps for one fade table (or none)."""
    if not used.any():
        messages.append(f"{name}: no usable rows.")
        return []
    counts = splat_values(tco_st, tco, np.ones(tco.size), axis_tco_st, axis_tco, 0.0,
                          row_weight=used.astype(float)).weights
    fit = splat_values(tco_st, tco, wanted, axis_tco_st, axis_tco, 0.0,
                       row_weight=np.where(used, base ** 2, 0.0)).values
    fit = np.where(counts >= min_weight, fit, np.nan)
    if np.isnan(fit).all():
        messages.append(f"{name}: no cell reached {min_weight:g} samples.")
        return []
    neg = np.isfinite(fit) & (fit < 0)
    messages.append(f"{name}: {int(np.isfinite(fit).sum())} cells from {int(used.sum())} rows, "
                    f"wanted fade {np.nanmin(fit):+.3f} to {np.nanmax(fit):+.3f}.")
    if neg.any():
        messages.append(f"{name}: [WARNING] {int(neg.sum())} cells want a negative fade: the engine is richer than "
                        "the warm-up target even without warm-up enrichment there. That is base fueling (VE, "
                        "injector constant), not warm-up; those cells are set to 0.")
    maps = [CalibrationMap(f"{key}_wanted", f"{name}: Wanted Fade from the Logs (unclipped)", fit, axis_tco_st,
                           axis_tco, counts=counts, counts_title=f"{name} - SAMPLE WEIGHTS", corner_label=CORNER)]
    if factory is None:
        messages.append(f"{name}: factory table not imported, so no corrected table.")
        return maps
    factory = np.asarray(factory, dtype=float)
    if factory.shape != fit.shape:
        messages.append(f"{name}: imported table is {factory.shape}, the axes give {fit.shape}; not corrected.")
        return maps
    new = np.where(np.isfinite(fit), np.clip(fit, 0.0, FADE_MAX), factory)
    maps.append(CalibrationMap(f"{key}_new", f"{name} Corrected (paste into TunerPro)", new, axis_tco_st, axis_tco,
                               corner_label=CORNER))
    return maps


def generate_warmup(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    base: np.ndarray,
    axis_base_load,
    axis_base_rpm,
    fade: np.ndarray,
    axis_fade_tco,
    axis_fade_tco_st,
    fade_is: np.ndarray | None = None,
    axis_fade_is_tco=None,
    axis_fade_is_tco_st=None,
    axis_ve_rpm,
    axis_ve_map,
    warm_engine: float = WARM_ENGINE,
    target_tco=TARGET_TCO,
    target_lambda=TARGET_LAMBDA,
    without_hot: str = SKIP,
    min_weight: float = 2.0,
    ve_min_weight: float = 2.0,
    both_banks: bool = False,
    skip_col: str | None = None,
    steady_col: str | None = None,
    start_col: str | None = None,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    messages = messages if messages is not None else []
    n = len(data)
    cool = channel(data, v["tmot"])
    hot = cool >= warm_engine
    cold = np.isfinite(cool) & ~hot
    target_tco, target_lambda = target_curve({"x": target_tco, "y": target_lambda})
    messages.append(f"Warm-up: {int(cold.sum())} rows with coolant below {warm_engine:g} C, {int(hot.sum())} warm rows. "
                    "Target lambda by coolant: " + ", ".join(f"{a:g} C {b:.3f}" for a, b in zip(target_tco, target_lambda))
                    + ".")
    if not cold.any():
        raise ValueError(f"No rows with coolant below {warm_engine:g} C.")

    # row factor of the cold rows against the warm-up target
    lam = warmup_lambda(cool, target_tco, target_lambda)
    d_cold = data[cold].copy()
    d_cold[v["afr_target"]] = channel(d_cold, v["afr_target"]) * lam[cold]
    f = np.full(n, np.nan)
    f[cold] = row_factors(d_cold, v, wideband=True, both_banks=both_banks, skip_col=skip_col,
                          messages=messages, tag="Warm-up")
    if steady_col and steady_col in data.columns:
        moving = cold & (data[steady_col].to_numpy(dtype=float) != 1) & np.isfinite(f)
        messages.append(f"Warm-up: {int(moving.sum())} rows with rpm or load changing fast left out.")
        f[moving] = np.nan

    # the base-fueling error from the hot rows at the same VE cell
    f_ve = np.full(n, np.nan)
    if hot.any():
        f_hot = np.full(n, np.nan)
        f_hot[hot] = row_factors(data[hot], v, wideband=True, both_banks=both_banks, skip_col=skip_col,
                                 messages=messages, tag="Warm-up, hot rows for the VE error")
        f_ve = hot_ve_error(data, v, f_hot, axis_rpm=axis_ve_rpm, axis_map=axis_ve_map, min_weight=ve_min_weight)
    usable = np.isfinite(f)
    covered = usable & np.isfinite(f_ve)
    missing = usable & ~covered
    if without_hot == ASSUME:
        f_ve = np.where(np.isfinite(f_ve), f_ve, 1.0)
        messages.append(f"Warm-up: {int(covered.sum())} rows corrected for the hot VE error at their cell, "
                        f"{int(missing.sum())} rows without hot data taken as if the VE were right.")
    else:
        messages.append(f"Warm-up: {int(covered.sum())} rows corrected for the hot VE error at their cell, "
                        f"{int(missing.sum())} rows without hot data at their VE cell skipped.")
        f = np.where(covered, f, np.nan)
    usable = np.isfinite(f)
    if not usable.any():
        raise ValueError("No warm-up row has hot VE data at its cell. Log the same conditions warm, or choose "
                         "'Assume the VE is right' once the VE is tuned.")

    # coolant at start
    if start_col and start_col in data.columns:
        tco_st = data[start_col].to_numpy(dtype=float)
    else:
        tco_st = np.full(n, cool[0])
        messages.append(f"Warm-up: coolant at start not known, taken as the first logged value {cool[0]:.1f} C.")
    usable &= np.isfinite(tco_st)

    rpm, load = channel(data, v["rpm"]), channel(data, v["load"])
    base_row = lookup_values(base, axis_base_load, axis_base_rpm, load, rpm)
    idle = (channel(data, v["idle"]) == 1) if has(data, v.get("idle", "")) else np.zeros(n, dtype=bool)
    fade_row = lookup_values(fade, axis_fade_tco_st, axis_fade_tco, tco_st, cool)
    if fade_is is not None:
        fade_row = np.where(idle, lookup_values(fade_is, axis_fade_is_tco_st, axis_fade_is_tco, tco_st, cool), fade_row)
    else:
        idle = np.zeros(n, dtype=bool)
    applied = base_row * fade_row
    wanted_total = (1.0 + applied) * f / f_ve
    wanted_fade = (wanted_total - 1.0) / np.where(base_row > 0, base_row, np.nan)
    usable &= np.isfinite(wanted_fade)

    afr, target = channel(data, v["wideband_afr"]), channel(data, v["afr_target"])
    u = usable
    if u.any():
        messages.append(f"Warm-up: measured lambda median {np.median(afr[u] / target[u]):.3f} against the warm-up "
                        f"target median {np.median(lam[u]):.3f}; applied enrichment median {np.median(applied[u]):+.1%}, "
                        f"wanted {np.median(wanted_total[u] - 1):+.1%}.")
    _check_formula(data, v, hot, cold & usable, applied, idle, messages)

    out = _fit_table(FADE, "wup_fade", fade, axis_fade_tco, axis_fade_tco_st, cool, tco_st, wanted_fade,
                     base_row, usable & ~idle, min_weight, messages)
    if fade_is is not None:
        out += _fit_table(FADE_IS, "wup_fade_is", fade_is, axis_fade_is_tco, axis_fade_is_tco_st, cool, tco_st,
                          wanted_fade, base_row, usable & idle, min_weight, messages)
    if not out:
        raise ValueError("No fade table cell reached the minimum samples.")
    target = CalibrationMap("wup_target", "Warm-up Target Lambda (from the settings)", target_lambda, target_tco,
                            ["Lambda"], corner_label="Coolant (C)")
    return [target, *out]


def _check_formula(data, v, hot, cold, applied, idle, messages) -> None:
    """Compare the enrichment the ECU applied (injection time over the hot injection line)
    with base x fade from the tables."""
    if not has(data, v.get("ti", "")) or int(hot.sum()) < MIN_CHECK_ROWS or not cold.any():
        messages.append("Warm-up: formula check skipped (needs the injection time and at least "
                        f"{MIN_CHECK_ROWS} warm rows in the same logs).")
        return
    ti, load, target = channel(data, v["ti"]), channel(data, v["load"]), channel(data, v["afr_target"])
    line = ti / (load * 14.7 / target)
    k = np.nanmedian(line[hot & (ti > 0)])
    measured = line / k - 1.0
    for label, sel in (("idle", cold & idle), ("part load", cold & ~idle)):
        if sel.any():
            messages.append(f"Warm-up check, {label}: enrichment applied by the ECU {np.median(measured[sel]):+.1%}, "
                            f"base x fade gives {np.median(applied[sel]):+.1%}.")
