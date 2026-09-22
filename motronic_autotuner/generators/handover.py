"""Throttle handover: base wastegate pressure curve and KFVPDKSD.

Port of Scripts/Utilities/GenerateBaseWGPressure.m and GenerateKFVPDKSD.m.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from ..core.maps import CalibrationMap
from ..core.splatting import linear_1d
from . import column

BASE_WG_MAX_DUTY = 10.0
HANDOVER_LOW = 0.95
HANDOVER_HIGH = 1.0


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
                           ambient_pressure: float, axis_rpm: np.ndarray,
                           axis_pratio: np.ndarray) -> list[CalibrationMap]:
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_pratio = np.asarray(axis_pratio, dtype=float).ravel()
    curve, counts = base_wg_pressure(data, v, min_samples_base_wg, axis_rpm)
    kfvp = generate_kfvpdksd(curve, axis_rpm, axis_pratio, ambient_pressure)
    return [
        CalibrationMap("base_press", "Base WG Pressure (Abs mbar)", curve, axis_rpm, ["Base Boost"],
                       counts=counts, counts_title="Base WG - SAMPLE WEIGHTS"),
        CalibrationMap("kfvp", "KFVPDKSD (Steady State Throttle Handover)", kfvp, axis_rpm, axis_pratio),
    ]
