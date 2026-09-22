"""Warm-up enrichment: KFFWL, KFFWLW and the hot-trim map FKKVS_RL.

Port of Scripts/Utilities/GenerateWarmupMaps.m. The MATLAB code hard-coded
80 degrees C as the hot threshold; here it is ``hot_temp`` and the family
passes the ingestion tab's warmup max temp, which defaults to 80.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear, linear_1d
from . import column, trim_percent

MIN_HOT_ROWS = 10


def generate_warmup_maps(
    data_warmup: pd.DataFrame,
    data_full: pd.DataFrame,
    v: dict[str, str],
    *,
    min_samples: float,
    trim_format: str,
    axis_tmot: np.ndarray,
    axis_load: np.ndarray,
    axis_rpm: np.ndarray,
    hot_temp: float = 80.0,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    messages = messages if messages is not None else []
    axis_tmot = np.asarray(axis_tmot, dtype=float).ravel()
    axis_load = np.asarray(axis_load, dtype=float).ravel()
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()

    for key in ("tmot", "stft", "ltft", "load", "rpm"):
        name = v[key]
        if name not in data_warmup.columns or name not in data_full.columns:
            raise KeyError(f"Missing required variable for Warmup: {name}")

    trim_hot_all = trim_percent(column(data_full, v["stft"]), column(data_full, v["ltft"]), trim_format)
    trim_cold = trim_percent(column(data_warmup, v["stft"]), column(data_warmup, v["ltft"]), trim_format)

    hot_mask = column(data_full, v["tmot"]) >= hot_temp
    trim_hot = trim_hot_all[hot_mask]
    load_hot = column(data_full, v["load"])[hot_mask]
    rpm_hot = column(data_full, v["rpm"])[hot_mask]

    if hot_mask.sum() > MIN_HOT_ROWS:
        base_hot_trim = float(np.nanmean(trim_hot))
    else:
        base_hot_trim = 0.0
        messages.append(f"Warning: Not enough data > {hot_temp:g}C to calculate hot trims. Assuming base fueling is perfect.")

    fkkvs_rl, _ = bilinear(load_hot, rpm_hot, trim_hot, axis_load, axis_rpm, min_samples)
    fkkvs_rl_filled = np.where(np.isnan(fkkvs_rl), base_hot_trim, fkkvs_rl)

    net_warmup = trim_cold - base_hot_trim
    kffwl, kffwl_counts = linear_1d(column(data_warmup, v["tmot"]), net_warmup, axis_tmot, min_samples)
    kffwl[(axis_tmot >= hot_temp) & ~np.isnan(kffwl)] = 0.0

    kffwlw_raw, kffwlw_counts = bilinear(
        column(data_warmup, v["load"]), column(data_warmup, v["rpm"]), trim_cold, axis_load, axis_rpm, min_samples,
    )
    kffwlw = kffwlw_raw - fkkvs_rl_filled

    return [
        CalibrationMap("kffwl", "KFFWL (Warmup Enrichment % vs Temp)", kffwl, axis_tmot, ["Trim %"],
                       counts=kffwl_counts, counts_title="KFFWL - SAMPLE WEIGHTS"),
        CalibrationMap("fkkvs_rl", "FKKVS_RL (Hot Trims mapped to Load/RPM)", fkkvs_rl, axis_load, axis_rpm),
        CalibrationMap("kffwlw", "KFFWLW (Warmup Weighting % vs Load/RPM)", kffwlw, axis_load, axis_rpm,
                       counts=kffwlw_counts, counts_title="KFFWLW - SAMPLE WEIGHTS"),
    ]
