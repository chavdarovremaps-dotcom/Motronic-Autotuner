"""Closed-loop VE correction tables: fuel trim splatted onto RPM x MAP for
each VE table index (Siemens MS43 with the MS4X firmware).

Port of the VE calibration engine in Scripts/MS43_Tune_helper.m: rows are
kept when lambda control is ON on every logged bank, the trim per bank is
short term plus multiplicative long term in percent, banks are averaged,
and the result is splatted trilinearly over RPM, MAP and the active VE
table index.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import trilinear
from . import column


def closed_loop_mask(data: pd.DataFrame, v: dict[str, str], messages: list[str]) -> tuple[np.ndarray, bool]:
    """Rows in closed loop, and whether only bank 1 is to be used."""
    l1, l2 = v.get("lambda1", ""), v.get("lambda2", "")
    has1, has2 = l1 in data.columns, l2 in data.columns
    single_bank = False
    if has1 and has2:
        if (column(data, l2) == 1).sum() == 0:
            single_bank = True
            messages.append("*** Detected Single Bank Operation (Lambda Control 2 is OFF). Using Bank 1 only. ***")
        else:
            messages.append("Detected Dual Bank Operation. Averaging Bank 1 and Bank 2 trims.")
    elif has1:
        single_bank = True
        messages.append("*** Detected Single Bank Operation (Lambda Control 2 not logged). Using Bank 1 only. ***")
    else:
        messages.append("Lambda control flags not logged. Using every row.")

    mask = column(data, l1) == 1 if has1 else np.ones(len(data), dtype=bool)
    if has2 and not single_bank:
        mask &= column(data, l2) == 1
    return mask, single_bank


def generate_ve_corrections(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    min_samples: float,
    axis_rpm: np.ndarray,
    axis_map: np.ndarray,
    n_tables: int = 8,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    messages = messages if messages is not None else []
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_map = np.asarray(axis_map, dtype=float).ravel()
    axis_idx = np.arange(1, n_tables + 1, dtype=float)

    mask, single_bank = closed_loop_mask(data, v, messages)
    d = data[mask]
    messages.append(f"Extracted {len(d)} Closed-Loop rows for VE Calibration.")
    if len(d) == 0:
        raise ValueError("No closed-loop rows: lambda control was never ON.")

    trim_b1 = column(d, v["stft_b1"]) + column(d, v["ltft_m_b1"])
    if single_bank:
        total = trim_b1
    else:
        trim_b2 = column(d, v["stft_b2"]) + column(d, v["ltft_m_b2"])
        total = (trim_b1 + trim_b2) / 2.0

    maps3d, counts3d = trilinear(
        column(d, v["rpm"]), column(d, v["map"]), column(d, v["ve_table"]), total,
        axis_rpm, axis_map, axis_idx, min_samples,
    )
    out = []
    for z in range(n_tables):
        out.append(CalibrationMap(
            f"ve{z + 1}", f"VE Table {z + 1} Correction (%)", maps3d[:, :, z], axis_rpm, axis_map,
            counts=counts3d[:, :, z], counts_title=f"VE Table {z + 1} - SAMPLE WEIGHTS",
            corner_label="MAP \\ RPM", skip_if_empty=True,
        ))
    return out
