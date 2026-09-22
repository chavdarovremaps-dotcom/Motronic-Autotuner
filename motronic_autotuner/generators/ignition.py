"""Ignition knock correction KFZW (VVT off) and KFZW2 (VVT on).

Port of Scripts/Utilities/GenerateKFZW.m. The VVT split angle was
hard-coded at 18 degrees there; it is ``vvt_split`` here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear
from . import column, column_ci


def generate_kfzw(data: pd.DataFrame, v: dict[str, str], *, min_samples: float, axis_rpm: np.ndarray,
                  axis_load: np.ndarray, vvt_split: float = 18.0) -> list[CalibrationMap]:
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_load = np.asarray(axis_load, dtype=float).ravel()
    rpm = column(data, v["rpm"])
    load = column(data, v["load"])
    knock = column(data, v["knock"])
    vvt = column_ci(data, v.get("vvt", ""))

    maps = []
    if vvt is not None:
        off, on = vvt <= vvt_split, vvt > vvt_split
        kfzw, c1 = bilinear(load[off], rpm[off], knock[off], axis_load, axis_rpm, min_samples)
        kfzw2, c2 = bilinear(load[on], rpm[on], knock[on], axis_load, axis_rpm, min_samples)
        maps.append(CalibrationMap("kfzw", "KFZW (Ignition Knock Correction - VVT OFF)", np.nan_to_num(kfzw, nan=0.0),
                                   axis_load, axis_rpm, counts=c1, counts_title="KFZW - SAMPLE WEIGHTS"))
        maps.append(CalibrationMap("kfzw2", "KFZW2 (Ignition Knock Correction - VVT ON)", np.nan_to_num(kfzw2, nan=0.0),
                                   axis_load, axis_rpm, counts=c2, counts_title="KFZW2 - SAMPLE WEIGHTS"))
    else:
        kfzw, c1 = bilinear(load, rpm, knock, axis_load, axis_rpm, min_samples)
        maps.append(CalibrationMap("kfzw", "KFZW (Ignition Knock Correction - VVT OFF)", np.nan_to_num(kfzw, nan=0.0),
                                   axis_load, axis_rpm, counts=c1, counts_title="KFZW - SAMPLE WEIGHTS"))
    return maps
