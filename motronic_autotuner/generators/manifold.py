"""Intake manifold model (Saugrohrmodell): KFURL slope and KFPRG intercept
per RPM bin and VVT state, from a linear fit of load against manifold pressure.

Port of Scripts/Utilities/GenerateSaugrohrmodell.m, including the anchoring
of negative intercepts to 20 hPa and the physics bounds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from . import column, column_ci

MIN_LOAD = 15.0
MIN_PRESSURE_RANGE = 20.0
ANCHOR_HPA = 20.0
INTERCEPT_MIN, INTERCEPT_MAX = -200.0, 800.0
RPM_EDGE_PAD = 200.0


def generate_manifold_maps(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    min_samples: float,
    vvt_enabled: bool,
    vvt_threshold: float,
    axis_rpm: np.ndarray,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_vvt = np.array([0.0, float(vvt_threshold)]) if vvt_enabled else np.array([0.0])

    rpm = column(data, v["rpm"])
    load = column(data, v["load"])
    if v["ps_w"] not in data.columns:
        raise KeyError(f"Intake pressure column ({v['ps_w']}) not found in logs.")
    ps = column(data, v["ps_w"])
    vvt = column_ci(data, v.get("vvt", "")) if vvt_enabled else None
    if vvt is None:
        messages.append("  [INFO] VVT Disabled or missing. Forcing single-column calculation.")
        vvt = np.zeros(len(data))

    n_rpm, n_vvt = axis_rpm.size, axis_vvt.size
    kfurl = np.full((n_rpm, n_vvt), np.nan)
    kfprg = np.full((n_rpm, n_vvt), np.nan)
    counts = np.zeros((n_rpm, n_vvt))

    for r in range(n_rpm):
        target_rpm = axis_rpm[r]
        rpm_min = target_rpm - RPM_EDGE_PAD if r == 0 else (axis_rpm[r - 1] + axis_rpm[r]) / 2
        rpm_max = target_rpm + RPM_EDGE_PAD if r == n_rpm - 1 else (axis_rpm[r] + axis_rpm[r + 1]) / 2
        for c in range(n_vvt):
            if vvt_enabled and n_vvt == 2:
                vvt_min, vvt_max = (-np.inf, vvt_threshold) if c == 0 else (vvt_threshold, np.inf)
            else:
                vvt_min, vvt_max = -np.inf, np.inf
            idx = (rpm >= rpm_min) & (rpm < rpm_max) & (vvt >= vvt_min) & (vvt < vvt_max)
            bin_ps, bin_load = ps[idx], load[idx]
            keep = bin_load > MIN_LOAD
            bin_ps, bin_load = bin_ps[keep], bin_load[keep]
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
