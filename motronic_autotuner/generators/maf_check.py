"""MAF sanity check for ME7: the corrected airflow ml_w against the airflow the
engine takes at a reference volumetric efficiency, on the KFKHFM grid.

At wide open throttle the pressure before the throttle (pvdks_w, the boost
sensor) is the manifold pressure within a few tens of hPa, and tanslin on the
1.8T sits after the intercooler, so the charge density follows from the ideal
gas law. The airflow at a volumetric efficiency VE is then

    airflow [g/s] = VE * p / (R * T) * displacement * rpm / 120

ps_w is not used: on the 1.8T it is the ECU's model, computed from the MAF.
The error ml_w / expected - 1 is averaged per cell of KFKHFM (nmot by rl_w,
the load the ECU looks the map up with). An implied-VE table on the same
axes separates engine breathing (a whole rpm row off) from the MAF (a
pattern across load at one rpm, or cells that differ between runs).

Information only. KFKHFM changes the load and everything computed from it,
so the "KFKHFM x expected / measured" block is never meant for pasting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear
from . import column

R_AIR = 287.05
"""Specific gas constant of dry air, J/(kg K)."""
DEFAULT_VE = 90.0
DISPLACEMENT_1_8T = 1781.0
DISPLACEMENT_2_0 = 1998.0
DEFAULT_MIN_THROTTLE = 95.0
CEILING_MIN_ROWS = 5
"""A value repeated at the column maximum this often is a sensor at its ceiling."""


def airflow_at_ve(rpm, pressure_hpa, temp_c, displacement_cc: float, ve_pct: float) -> np.ndarray:
    """Airflow in g/s of a four-stroke engine at volumetric efficiency ``ve_pct``."""
    rho = np.asarray(pressure_hpa, dtype=float) * 100.0 / (R_AIR * (np.asarray(temp_c, dtype=float) + 273.15))
    return ve_pct / 100.0 * rho * displacement_cc * 1e-6 * np.asarray(rpm, dtype=float) / 120.0 * 1000.0


def at_ceiling(values: np.ndarray, *, tol: float = 1.0, min_rows: int = CEILING_MIN_ROWS) -> np.ndarray:
    """Rows where a sensor sits at its ceiling: within ``tol`` of the maximum,
    when at least ``min_rows`` rows do so (a plateau, not a single peak)."""
    v = np.asarray(values, dtype=float)
    if v.size == 0 or not np.isfinite(v).any():
        return np.zeros(v.size, dtype=bool)
    at = v >= np.nanmax(v) - tol
    return at if int(at.sum()) >= min_rows else np.zeros(v.size, dtype=bool)


def generate_maf_check(data: pd.DataFrame, v: dict[str, str], *, axis_rpm: np.ndarray, axis_load: np.ndarray,
                       base_map: np.ndarray | None = None, displacement_cc: float = DISPLACEMENT_1_8T,
                       ve_pct: float = DEFAULT_VE, min_throttle: float = DEFAULT_MIN_THROTTLE,
                       min_samples: float = 1.0, messages: list[str] | None = None) -> list[CalibrationMap]:
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_load = np.asarray(axis_load, dtype=float).ravel()
    rpm, load = column(data, v["rpm"]), column(data, v["load"])
    flow, pressure = column(data, v["maf"]), column(data, v["boost"])
    temp, throttle = column(data, v["iat"]), column(data, v["pedal"])

    keep = (throttle >= min_throttle) & np.isfinite(rpm + load + flow + pressure + temp) & (rpm > 0) & (pressure > 0)
    n_open = int(keep.sum())
    if n_open == 0:
        raise ValueError(f"No rows with {v['pedal']} at least {min_throttle:g} % for the MAF check.")
    idx = np.flatnonzero(keep)
    p_top, f_top = at_ceiling(pressure[idx]), at_ceiling(flow[idx])
    idx = idx[~(p_top | f_top)]
    if idx.size == 0:
        raise ValueError("Every wide-open row has the pressure or the airflow at its sensor ceiling.")
    rpm, load, flow, pressure, temp = rpm[idx], load[idx], flow[idx], pressure[idx], temp[idx]

    full = airflow_at_ve(rpm, pressure, temp, displacement_cc, 100.0)
    ve = flow / full * 100.0
    err = (ve / ve_pct - 1.0) * 100.0
    err_map, counts = bilinear(load, rpm, err, axis_load, axis_rpm, min_samples)
    ve_map, _ = bilinear(load, rpm, ve, axis_load, axis_rpm, min_samples)

    excluded = []
    if p_top.any():
        excluded.append(f"{int(p_top.sum())} with {v['boost']} at its ceiling")
    if f_top.any():
        excluded.append(f"{int(f_top.sum())} with {v['maf']} at its ceiling")
    messages.append(
        f"MAF check: {idx.size} rows with {v['pedal']} >= {min_throttle:g} %"
        + (f" ({', '.join(excluded)} left out)" if excluded else "")
        + f"; {v['maf']} against {ve_pct:g} % VE at {displacement_cc:g} cc: median {np.median(err):+.1f} %, "
          f"implied VE median {np.median(ve):.1f} % ({np.percentile(ve, 10):.1f} to {np.percentile(ve, 90):.1f} %). "
          "Information only.")

    corner = "RPM \\ Load %"
    maps = [
        CalibrationMap("maf_error", f"MAF check: {v['maf']} vs airflow at {ve_pct:g} % VE (%)", err_map, axis_load, axis_rpm,
                       counts=counts, counts_title="MAF check - SAMPLE WEIGHTS", corner_label=corner),
        CalibrationMap("maf_ve", "MAF check: implied volumetric efficiency (%)", ve_map, axis_load, axis_rpm,
                       corner_label=corner),
    ]
    if base_map is not None:
        base = np.asarray(base_map, dtype=float)
        if not (np.isfinite(base) & (base > 0)).any():
            messages.append("MAF check: the imported KFKHFM is 0 in every cell, which no running ECU has (it is a "
                            "factor around 1.0): the map's address or factor in the WinOLS map pack is off. The "
                            "information block is left out.")
        elif base.shape == err_map.shape:
            info = np.where(np.isnan(err_map), np.nan, base / (1.0 + err_map / 100.0))
            maps.append(CalibrationMap(
                "kfkhfm_info", "KFKHFM x expected / measured (INFORMATION ONLY: changing KFKHFM changes the load "
                "and everything after it)", info, axis_load, axis_rpm, corner_label=corner))
        else:
            messages.append(f"MAF check: imported KFKHFM is {base.shape}, axes give {err_map.shape}; "
                            "the information block is left out.")
    return maps
