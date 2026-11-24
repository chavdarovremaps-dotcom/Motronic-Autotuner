"""Fuel trim correction FKKVS on injector on-time against RPM.

Port of Scripts/Utilities/GenerateFKKVS.m. Rows with the short-term trim at
exactly neutral (lambda control not running) are left out.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear
from . import column, drop_lambda_off, trim_percent


def generate_fkkvs(data: pd.DataFrame, v: dict[str, str], *, min_samples: float, trim_format: str,
                   axis_rpm: np.ndarray, axis_te: np.ndarray,
                   messages: list[str] | None = None) -> list[CalibrationMap]:
    data = drop_lambda_off(data, v, trim_format, "FKKVS", messages)
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_te = np.asarray(axis_te, dtype=float).ravel()
    trim = trim_percent(column(data, v["stft"]), column(data, v["ltft"]), trim_format)
    fkkvs, counts = bilinear(column(data, v["inj"]), column(data, v["rpm"]), trim, axis_te, axis_rpm, min_samples)
    fkkvs = np.nan_to_num(fkkvs, nan=0.0)
    return [
        CalibrationMap("fkkvs", "FKKVS (Fuel Trim Correction %)", fkkvs, axis_te, axis_rpm,
                       counts=counts, counts_title="FKKVS - SAMPLE WEIGHTS"),
    ]
