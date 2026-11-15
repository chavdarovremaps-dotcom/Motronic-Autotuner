"""Boost control: KFLDIMX, KFLDRL and the absolute WGDC map.

Port of Scripts/Utilities/GenerateBoostMaps.m.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import QhullError

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear, linear_1d
from . import column

MAX_PID_LIMIT = 100.0
WGDC_CLAMP_MAX = 95.0
KFLDRL_METHODS = ("rows", "splat")
"""``rows``: each rpm row interpolated between the duty levels logged there; ``splat``: the bilinear splat."""
DUTY_OUT_OF_REACH = 95.0
"""Duty for the boost targets a row below the spool cannot reach: gate shut, fastest spool."""
NEAR_TOP = 0.25
"""A column this share of a column step above the highest boost a row reached counts as reached (939 for 940)."""


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


def duty_level_points(rpm, rel_boost, duty, axis_rpm, *, min_samples: float = 1.0):
    """Mean boost and mean duty of every duty level at every rpm point.

    Levels are the duties rounded to whole percent, so a forced KFLDRAPP
    level (69.92 = 179/256) is one level. Rows are shared between the two
    nearest rpm points by distance. Returns ``(boost, duty, weights)``, each
    levels x rpm points, NaN where the weight is below ``min_samples``.
    """
    rpm, rel_boost, duty = (np.asarray(a, dtype=float) for a in (rpm, rel_boost, duty))
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    ok = np.isfinite(rpm) & np.isfinite(rel_boost) & np.isfinite(duty)
    level = np.round(duty)
    levels = np.unique(level[ok])
    boost_t = np.full((levels.size, axis_rpm.size), np.nan)
    duty_t = np.full_like(boost_t, np.nan)
    weights = np.zeros_like(boost_t)
    for i, lv in enumerate(levels):
        sel = ok & (level == lv)
        boost_t[i], weights[i] = linear_1d(rpm[sel], rel_boost[sel], axis_rpm, min_samples)
        duty_t[i], _ = linear_1d(rpm[sel], duty[sel], axis_rpm, min_samples)
    return boost_t, duty_t, weights


def rising_points(boost, duty, weights):
    """The duty levels of one rpm row, sorted by duty, with the boost made to
    rise with duty: a weighted isotonic fit (pool adjacent violators), so a
    stray point is averaged with its neighbours instead of hiding every
    level above it. Levels pooled into one boost keep the lowest duty, which
    is where more duty made no more boost (a turbo at its limit).
    Returns ``(boost, duty, weights)``, boost strictly rising."""
    boost, duty, weights = (np.asarray(a, dtype=float) for a in (boost, duty, weights))
    ok = np.isfinite(boost) & np.isfinite(duty) & (weights > 0)
    order = np.argsort(duty[ok], kind="stable")
    b, d, w = boost[ok][order], duty[ok][order], weights[ok][order]
    blocks: list[list[float]] = []  # [weighted boost sum, weight, lowest duty]
    for x, dx, wx in zip(b, d, w):
        blocks.append([x * wx, wx, dx])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] >= blocks[-1][0] / blocks[-1][1]:
            s, ww, _ = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += ww
    return (np.array([s / ww for s, ww, _ in blocks]), np.array([dx for _, _, dx in blocks]),
            np.array([ww for _, ww, _ in blocks]))


def kfldrl_by_rows(boost_t, duty_t, weights, columns_boost):
    """KFLDRL from the duty levels: in each rpm row the duty at a column's boost
    is linear between the two levels whose boost brackets it, and NaN outside
    the boost the row's levels reached; a column just above it (NEAR_TOP)
    takes the top level's duty. A forced level that lands between two
    columns then no longer writes the same duty into both (the flat treads of
    the splat). Returns ``(values, weights, row_top, row_duty)``: the highest
    boost reached and the highest duty logged in each row."""
    columns_boost = np.asarray(columns_boost, dtype=float).ravel()
    n_rows = boost_t.shape[1]
    values = np.full((n_rows, columns_boost.size), np.nan)
    counts = np.zeros_like(values)
    row_top = np.full(n_rows, np.nan)
    row_duty = np.full(n_rows, np.nan)
    for r in range(n_rows):
        b, d, w = rising_points(boost_t[:, r], duty_t[:, r], weights[:, r])
        if b.size:
            row_top[r] = b[-1]
            row_duty[r] = np.nanmax(np.where(np.isfinite(boost_t[:, r]), duty_t[:, r], np.nan))
        if b.size < 2:
            continue
        inside = (columns_boost >= b[0]) & (columns_boost <= b[-1])
        values[r, inside] = np.interp(columns_boost[inside], b, d)
        hi = np.clip(np.searchsorted(b, columns_boost[inside]), 1, b.size - 1)
        counts[r, inside] = w[hi - 1] + w[hi]
        above = np.flatnonzero(columns_boost > b[-1])
        if above.size and above[0] > 0:
            c = above[0]
            if columns_boost[c] - b[-1] <= NEAR_TOP * (columns_boost[c] - columns_boost[c - 1]):
                values[r, c], counts[r, c] = d[-1], w[-1]
    return values, counts, row_top, row_duty


def _fill_inside(row: np.ndarray, columns_boost: np.ndarray) -> np.ndarray:
    """Leading and interior gaps of a row, linear in boost, with column 0 at 0 % duty."""
    out = np.array(row, dtype=float)
    out[0] = 0.0
    known = np.isfinite(out)
    last = int(np.flatnonzero(known)[-1])
    gap = ~known[: last + 1]
    if gap.any():
        out[: last + 1][gap] = np.interp(columns_boost[: last + 1][gap], columns_boost[known], out[known])
    return out


def finish_kfldrl(values, row_top, row_duty, columns_boost, axis_rpm, *, spool_rpm: float | None = None,
                  share: float = 90.0, out_of_reach: float = DUTY_OUT_OF_REACH,
                  messages: list[str] | None = None) -> np.ndarray:
    """The hand finishing of KFLDRL, by spool region.

    Column 0 is 0 % (zero controller output: N75 off, gate on its spring) and
    every row rises with the boost target. Leading and interior gaps are
    linear in boost. The trailing gaps, targets a row's logs never reached,
    depend on where the row sits:

    - spooled rows, from the first axis point at or above ``spool_rpm`` (the
      tuner's setting; without it, the rows that reached ``share`` % of the
      highest boost of any row), get the highest duty logged in them
      (``row_duty``): a ceiling that was actually run, so a turbo out of
      breath at high rpm is not driven harder than that;
    - the row just below the first spooled row takes that row's duties: the
      ECU interpolates between the two, and 95 % here overboosts right after
      the spool;
    - rows further down get ``out_of_reach`` for the fastest spool, their
      first gap cell bridged at the duty the turbo holds after the spool;
    - a row without data gets ``out_of_reach`` below the spool, or the
      nearest spooled row above the spool.
    """
    messages = messages if messages is not None else []
    columns_boost = np.asarray(columns_boost, dtype=float).ravel()
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    v = np.array(values, dtype=float)
    v[:, 0] = np.nan
    has = np.isfinite(v).any(axis=1)
    top = np.where(has, np.asarray(row_top, dtype=float), np.nan)
    if not np.isfinite(top).any():
        messages.append("KFLDRL finish: no row has data above column 0, map left as calculated.")
        out = np.array(values, dtype=float)
        out[:, 0] = 0.0
        return out
    n_rows, width = v.shape
    if spool_rpm:
        at_or_above = np.flatnonzero(axis_rpm >= float(spool_rpm))
        first = int(at_or_above[0]) if at_or_above.size else n_rows - 1
        why = f"the spool rpm setting, {float(spool_rpm):g}"
    else:
        peak = float(np.nanmax(top))
        first = int(np.flatnonzero(np.nan_to_num(top, nan=-np.inf) >= share / 100.0 * peak)[0])
        why = f"where the row reaches {top[first]:.0f} hPa, {share:g} % of the {peak:.0f} hPa peak"
    logged = np.asarray(row_duty, dtype=float)[first:]
    if np.isfinite(logged).any():
        cap = float(np.nanmax(logged))
    else:
        cap = float(np.nanmax(row_duty)) if np.isfinite(row_duty).any() else float(np.nanmax(v))

    out = np.full_like(v, np.nan)
    for r in range(first, n_rows):
        if has[r]:
            row = _fill_inside(v[r], columns_boost)
            row[~np.isfinite(row)] = cap
            out[r] = row
    for r in range(first, n_rows):
        if has[r]:
            continue
        above = [q for q in range(r + 1, n_rows) if has[q]]
        if r > first:
            out[r] = out[r - 1]
        elif above:
            out[r] = out[above[0]]
        else:
            out[r] = np.r_[0.0, np.full(width - 1, cap)]
    bridge = None
    if first > 0:
        t = first - 1
        row = _fill_inside(v[t], columns_boost) if has[t] else np.r_[0.0, np.full(width - 1, np.nan)]
        gap = ~np.isfinite(row)
        row[gap] = out[first][gap]
        out[t] = row
        bridge = float(np.max(row))
        for r in range(t):
            if not has[r]:
                out[r] = np.r_[0.0, np.full(width - 1, out_of_reach)]
                continue
            row = _fill_inside(v[r], columns_boost)
            gap = np.flatnonzero(~np.isfinite(row))
            row[gap] = out_of_reach
            if gap.size and row[gap[0] - 1] < bridge < out_of_reach:
                row[gap[0]] = bridge
            out[r] = row
    out[:, 1:] = np.maximum.accumulate(out[:, 1:], axis=1)
    out[:, 0] = 0.0

    msg = (f"KFLDRL finish: spooled from {axis_rpm[first]:.0f} rpm ({why}); column 0 at 0 %; empty cells from "
           f"there up get {cap:.1f} %, the highest duty logged in those rows")
    if first > 0:
        msg += (f"; {axis_rpm[first - 1]:.0f} rpm takes the {axis_rpm[first]:.0f} rpm duties; rows below get "
                f"{out_of_reach:g} %, the first empty cell bridged at {bridge:.1f} %")
    messages.append(msg + ".")
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
    method: str = "splat",
    finish: bool = False,
    spool_rpm: float | None = None,
    out_of_reach: float = DUTY_OUT_OF_REACH,
    level_min_samples: float = 3.0,
    reference_column: str | None = None,
    reference_label: str = "Target Rel Boost (mbar)",
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """``safety_margin`` is accepted for parity with the MATLAB signature; it was never applied there.
    ``method`` is one of KFLDRL_METHODS. ``finish`` adds the finished KFLDRL (finish_kfldrl on the cells from
    the logs) as a block of its own after the calculated one; ``fill_missing`` only fills the calculated one.
    ``level_min_samples`` is the weight a duty level needs at an rpm point to count there (rows and finish).
    ``reference_column``, when given, is the pressure the boost is measured from, row by row (ME7.6.2:
    the base boost plgru, which its LDR subtracts from the target), in place of pu or the ambient setting;
    ``reference_label`` names the KFLDRL columns accordingly. ``spool_rpm`` is the tuner's spool point for the
    finish; without it the finish judges the spool from the logs (90 % of the highest boost of any row)."""
    messages = messages if messages is not None else []
    if method not in KFLDRL_METHODS:
        raise ValueError(f"unknown KFLDRL method {method!r}")
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_boost = np.asarray(axis_boost, dtype=float).ravel()
    axis_kfldrl_x = np.asarray(axis_kfldrl_x, dtype=float).ravel()

    boost = column(data, v["boost"])
    rpm = column(data, v["rpm"])
    wgdc = column(data, v["wgdc"])
    if reference_column:
        reference = column(data, reference_column)
    else:
        reference = column(data, v["pu"]) if cwldimx else np.full(boost.shape, float(ambient_pressure))
    rel_boost = boost - reference

    lo, hi = axis_boost[0], axis_boost.max()
    span = hi - lo
    ramp = (axis_boost - lo) / span * MAX_PID_LIMIT
    kfldimx = np.tile(ramp, (axis_rpm.size, 1))

    physical_boost_axis = lo + (axis_kfldrl_x / MAX_PID_LIMIT) * span
    if method == "rows" or finish:
        level_boost, level_duty, level_w = duty_level_points(rpm, rel_boost, wgdc, axis_rpm,
                                                             min_samples=level_min_samples)
        by_rows, rows_counts, row_top, row_duty = kfldrl_by_rows(level_boost, level_duty, level_w, physical_boost_axis)
    if method == "rows":
        kfldrl, kfldrl_counts = by_rows, rows_counts
        used = int(np.isfinite(level_boost).any(axis=1).sum())
        messages.append(f"KFLDRL: each rpm row interpolated between the duty levels logged there ({used} levels in "
                        f"whole percent with at least {level_min_samples:g} samples at an rpm point).")
    else:
        kfldrl, kfldrl_counts = bilinear(rel_boost, rpm, wgdc, physical_boost_axis, axis_rpm, min_samples)
    finished = None
    if finish:
        spool_top = row_top
        if reference_column and not spool_rpm:
            # judged from the logs, the spool is taken on the boost above ambient: a reference that falls with rpm
            # (ME7.6.2 plgru) would put the peak of "boost above it" at high rpm where the absolute boost is falling
            lift, _ = linear_1d(rpm, reference - ambient_pressure, axis_rpm, 1.0)
            spool_top = row_top + np.nan_to_num(lift, nan=0.0)
        finished = np.clip(finish_kfldrl(kfldrl, spool_top, row_duty, physical_boost_axis, axis_rpm,
                                         spool_rpm=spool_rpm, out_of_reach=out_of_reach, messages=messages),
                           0.0, WGDC_CLAMP_MAX)
    if fill_missing:
        kfldrl = fill_gaps(kfldrl, physical_boost_axis, axis_rpm)
        kfldrl[:, -1] = MAX_PID_LIMIT
    kfldrl = np.clip(kfldrl, 0.0, WGDC_CLAMP_MAX)

    offset = float(np.nanmedian(reference)) if reference_column and np.isfinite(reference).any() else ambient_pressure
    axis_boost_abs = axis_boost + offset
    abs_wgdc, abs_counts = bilinear(boost, rpm, wgdc, axis_boost_abs, axis_rpm, min_samples)

    maps = [
        CalibrationMap("kfldimx", "KFLDIMX (Linear Converter Map)", kfldimx, axis_boost, axis_rpm),
        CalibrationMap(
            "kfldrl", "KFLDRL (Base Linearization - WGDC %)", kfldrl, axis_kfldrl_x, axis_rpm,
            counts=kfldrl_counts, counts_title="KFLDRL - SAMPLE WEIGHTS",
            secondary_x_label=reference_label, secondary_x=physical_boost_axis,
        ),
    ]
    if finished is not None:
        maps.append(CalibrationMap(
            "kfldrl_finished", "KFLDRL finished (column 0 at 0 %, empty cells by spool region, paste into WinOLS)",
            finished, axis_kfldrl_x, axis_rpm, secondary_x_label=reference_label, secondary_x=physical_boost_axis,
        ))
    maps.append(CalibrationMap(
        "abs_wgdc", "ABSOLUTE WGDC MAP (Abs Boost vs RPM)", abs_wgdc, axis_boost_abs, axis_rpm,
        counts=abs_counts, counts_title="ABS WGDC - SAMPLE WEIGHTS",
    ))
    return maps


AXIS_POINTS = 16
AXIS_FINE_STEP, AXIS_COARSE_STEP = 250.0, 500.0
AXIS_POINTS_BELOW, AXIS_FINE_ABOVE = 4, 5


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
