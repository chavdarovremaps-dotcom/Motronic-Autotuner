"""VE correction for the MS43X speed-density tables ip_map_ve_1 .. 8.

The tables hold VE as a fraction (0.79 = 79 %), MAP in kPa down the rows and
rpm across the columns. The injection load is proportional to VE x MAP, so
a higher VE means more fuel.

Every usable log row gets a correction factor:

* wideband present: ``f = Wideband AFR / AFR target + STFT / 100 + LTFT / 100``.
  A lean reading (measured above target) gives a factor above one and
  raises VE, the same way a positive trim does.
* no wideband: ``f = 1 + STFT / 100 + LTFT / 100``, closed-loop rows only.

STFT and LTFT are bank 1 (short term and multiplicative long term trim, in
percent, 0 = no correction), or the average of both banks when asked. The
factors are averaged per cell with the 4-cell splat and VEnew = VEold x f.

The firmware blends the two neighbouring tables when the valve overlap lies
between their steps. The logged "Active VE Table" carries that as a
fraction (1.25 = three quarters table 1, one quarter table 2), and each
row counts towards each table by its share.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from .splat import splat_values

VE_TABLES = 8
RAIL_LOW_V, RAIL_HIGH_V = 0.02, 4.98
"""A wideband input at 0 or 5 V is outside the controller output, so the AFR is unknown there."""
LEAN_AFR = 16.5
"""Wideband reading that counts as gone lean when measuring its lag behind a fuel cut."""
CORNER = "MAP \\ RPM"


def channel(data: pd.DataFrame, name: str) -> np.ndarray:
    if not name or name not in data.columns:
        raise KeyError(f"Channel '{name}' is not in the logs")
    return data[name].to_numpy(dtype=float)


def has(data: pd.DataFrame, name: str) -> bool:
    return bool(name) and name in data.columns


def table_shares(active, n_tables: int = VE_TABLES) -> np.ndarray:
    """``[rows, n_tables]``: how much each table counts for each row, from the
    logged active VE table (1-based, fractional while blending)."""
    a = np.asarray(active, dtype=float).ravel()
    shares = np.zeros((a.size, n_tables))
    ok = np.isfinite(a)
    a = np.clip(a[ok], 1.0, float(n_tables))
    lo = np.floor(a).astype(int)
    frac = a - lo
    rows = np.flatnonzero(ok)
    shares[rows, lo - 1] += 1.0 - frac
    up = frac > 0
    shares[rows[up], lo[up]] += frac[up]
    return shares


def trims_percent(data: pd.DataFrame, v: dict[str, str], both_banks: bool) -> np.ndarray:
    """STFT + multiplicative LTFT in percent, bank 1 or the average of both banks."""
    b1 = channel(data, v["stft_b1"]) + channel(data, v["ltft_m_b1"])
    if not both_banks:
        return b1
    return (b1 + channel(data, v["stft_b2"]) + channel(data, v["ltft_m_b2"])) / 2.0


def wideband_factor(wideband_afr, afr_target, trims_pct) -> np.ndarray:
    """Measured over target, plus the trims: lean (measured above target) raises VE."""
    afr = np.asarray(wideband_afr, dtype=float)
    target = np.asarray(afr_target, dtype=float)
    return afr / target + np.asarray(trims_pct, dtype=float) / 100.0


def trims_factor(trims_pct) -> np.ndarray:
    return 1.0 + np.asarray(trims_pct, dtype=float) / 100.0


def fuel_cut_window(time, cut, skip_after_s: float) -> np.ndarray:
    """Rows in a fuel cut, or less than ``skip_after_s`` seconds after one ended
    (the wideband still reads the air the cut pumped through)."""
    time = np.asarray(time, dtype=float)
    cut = np.asarray(cut, dtype=float) == 1
    out = cut.copy()
    if skip_after_s > 0:
        for e in np.flatnonzero(cut[:-1] & ~cut[1:]) + 1:
            out |= (time >= time[e]) & (time < time[e] + skip_after_s)
    return out


def wideband_lag(time, cut, wideband_afr, lean_afr: float = LEAN_AFR, max_s: float = 2.0) -> list[float]:
    """Seconds from each fuel-cut start until the wideband reads lean."""
    time = np.asarray(time, dtype=float)
    cut = np.asarray(cut, dtype=float) == 1
    afr = np.asarray(wideband_afr, dtype=float)
    lags = []
    for s in np.flatnonzero(~cut[:-1] & cut[1:]) + 1:
        lean = np.flatnonzero((time > time[s]) & (afr >= lean_afr))
        if lean.size and time[lean[0]] - time[s] <= max_s:
            lags.append(float(time[lean[0]] - time[s]))
    return lags


def row_factors(data: pd.DataFrame, v: dict[str, str], *, wideband: bool, both_banks: bool,
                skip_col: str | None, messages: list[str], tag: str = "VE") -> np.ndarray:
    """The correction factor per row, NaN for rows that must not be used. It
    scales whatever the ECU calculated from its air estimate: VE, or the load.
    ``tag`` starts each message."""
    n = len(data)
    trims = trims_percent(data, v, both_banks)
    banks = "banks 1 and 2 averaged" if both_banks else "bank 1"
    keep = np.ones(n, dtype=bool)
    if wideband:
        afr, target = channel(data, v["wideband_afr"]), channel(data, v["afr_target"])
        keep &= np.isfinite(afr) & (target > 0)
        if skip_col and skip_col in data.columns:
            window = data[skip_col].to_numpy(dtype=float) == 1
            messages.append(f"{tag}: {int(window.sum())} rows in or just after a fuel cut left out.")
            keep &= ~window
        else:
            messages.append(f"{tag}: fuel cut not logged, no rows left out for it.")
        if has(data, v.get("wideband_v", "")):
            volts = channel(data, v["wideband_v"])
            rail = (volts <= RAIL_LOW_V) | (volts >= RAIL_HIGH_V)
            messages.append(f"{tag}: {int((rail & keep).sum())} rows with the wideband input at 0 or 5 V left out.")
            keep &= ~rail
        factor = wideband_factor(afr, target, trims)
        messages.append(f"{tag} factor from the wideband: f = {v['wideband_afr']} / {v['afr_target']} + (STFT + LTFT) / 100, "
                        f"trims from {banks}. {int(keep.sum())} of {n} rows used.")
        if keep.any():
            messages.append(f"{tag}: measured AFR median {np.median(afr[keep]):.2f} against target median "
                            f"{np.median(target[keep]):.2f}, trims median {np.median(trims[keep]):+.1f} %.")
    else:
        closed = channel(data, v["lambda1"]) == 1
        if both_banks:
            closed &= channel(data, v["lambda2"]) == 1
        keep &= closed
        factor = trims_factor(trims)
        messages.append(f"{tag} factor from the trims only: f = 1 + (STFT + LTFT) / 100, trims from {banks}, "
                        f"closed-loop rows only: {int(keep.sum())} of {n} rows.")
    return np.where(keep, factor, np.nan)


def generate_ve_correction(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    wideband: bool,
    both_banks: bool,
    axis_rpm,
    axis_map,
    base_maps: dict[int, np.ndarray] | None = None,
    min_weight: float = 2.0,
    skip_col: str | None = None,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """Correction in percent and the corrected table for every VE table the logs reached.
    ``base_maps`` maps a table number to its VE values ``[len(axis_map), len(axis_rpm)]``."""
    messages = messages if messages is not None else []
    base_maps = base_maps or {}
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_map = np.asarray(axis_map, dtype=float).ravel()
    factor = row_factors(data, v, wideband=wideband, both_banks=both_banks, skip_col=skip_col, messages=messages)
    if not np.isfinite(factor).any():
        hint = "." if wideband else ": closed loop was never on. Tick 'Wideband present' if one is fitted."
        raise ValueError("No usable rows for the VE correction" + hint)
    shares = table_shares(channel(data, v["ve_table"]))
    rpm, mp = channel(data, v["rpm"]), channel(data, v["map"])
    out = []
    for k in range(1, VE_TABLES + 1):
        weight = shares[:, k - 1]
        if not (np.isfinite(factor) & (weight > 0)).any():
            continue
        s = splat_values(rpm, mp, factor, axis_rpm, axis_map, min_weight, row_weight=weight)
        if np.isnan(s.values).all():
            messages.append(f"VE Table {k}: rows found, but no cell reached {min_weight:g} samples.")
            continue
        corr_pct = (s.values - 1.0) * 100.0
        cells = int(np.isfinite(corr_pct).sum())
        messages.append(f"VE Table {k}: {cells} cells, correction {np.nanmin(corr_pct):+.1f} to {np.nanmax(corr_pct):+.1f} %.")
        out.append(CalibrationMap(
            f"ve{k}_corr", f"VE Table {k} Correction (%)", corr_pct, axis_rpm, axis_map,
            counts=s.weights, counts_title=f"VE Table {k} - SAMPLE WEIGHTS", corner_label=CORNER,
        ))
        base = base_maps.get(k)
        if base is None:
            messages.append(f"VE Table {k}: no factory table imported, so no corrected table.")
            continue
        base = np.asarray(base, dtype=float)
        if base.shape != s.values.shape:
            messages.append(f"VE Table {k}: imported table is {base.shape}, the axes give {s.values.shape}; not corrected.")
            continue
        out.append(CalibrationMap(
            f"ve{k}_new", f"VE Table {k} Corrected (paste into TunerPro)",
            np.where(np.isnan(s.values), base, base * s.values), axis_rpm, axis_map, corner_label=CORNER,
        ))
    if not out:
        raise ValueError("No VE table cell reached the minimum samples.")
    return out
