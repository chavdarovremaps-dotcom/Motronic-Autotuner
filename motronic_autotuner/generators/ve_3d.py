"""VE correction tables: a fuel error splatted onto RPM x MAP for each VE
table index (Siemens MS43 with the MS4X firmware).

Port of the VE calibration engine in Scripts/MS43_Tune_helper.m, with a
second error source. Either:

* ``"trims"``: rows in closed loop on every logged bank, error per bank is
  short term plus multiplicative long term trim in percent, banks averaged.
* ``"wideband"``: every row with a valid analog wideband reading. The
  controller's AFR is ``V * gain / 5 + offset`` and the error is
  ``(measured / target - 1) * 100`` so that a lean reading is positive,
  the same sign convention as the trims: a positive error raises VE.

The error is splatted trilinearly over RPM, MAP and the active VE table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..core.splatting import trilinear
from . import column

SOURCE_TRIMS = "trims"
SOURCE_WIDEBAND = "wideband"
WIDEBAND_GAIN = 15.04
WIDEBAND_OFFSET = 7.35
RAIL_LOW_V = 0.02
RAIL_HIGH_V = 4.98
"""Readings at the 0 or 5 V rail mean no sensor signal; those rows are dropped."""


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


def wideband_afr(volts: np.ndarray, gain: float = WIDEBAND_GAIN, offset: float = WIDEBAND_OFFSET) -> np.ndarray:
    return volts * gain / 5.0 + offset


def trim_error(data: pd.DataFrame, v: dict[str, str], messages: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    mask, single_bank = closed_loop_mask(data, v, messages)
    d = data[mask]
    messages.append(f"Extracted {len(d)} Closed-Loop rows for VE Calibration.")
    if len(d) == 0:
        raise ValueError("No closed-loop rows: lambda control was never ON.")
    trim_b1 = column(d, v["stft_b1"]) + column(d, v["ltft_m_b1"])
    if single_bank:
        return d, trim_b1
    trim_b2 = column(d, v["stft_b2"]) + column(d, v["ltft_m_b2"])
    return d, (trim_b1 + trim_b2) / 2.0


def wideband_error(data: pd.DataFrame, v: dict[str, str], gain: float, offset: float,
                   messages: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    volts = column(data, v["wideband_v"])
    target = column(data, v["afr_target"])
    valid = (volts > RAIL_LOW_V) & (volts < RAIL_HIGH_V) & (target > 0) & ~np.isnan(volts) & ~np.isnan(target)
    d = data[valid]
    measured = wideband_afr(volts[valid], gain, offset)
    error = (measured / target[valid] - 1.0) * 100.0
    messages.append(
        f"Wideband on {v['wideband_v']}: AFR = V * {gain:g} / 5 + {offset:g}. Using {len(d)} rows with a live signal "
        f"(AFR {measured.min():.2f} to {measured.max():.2f}); {int((~valid).sum())} rows at the rails or without a target dropped."
    )
    if len(d) == 0:
        raise ValueError("No usable wideband rows: the analog input sat at 0 or 5 V.")
    return d, error


def generate_ve_corrections(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    min_samples: float,
    axis_rpm: np.ndarray,
    axis_map: np.ndarray,
    n_tables: int = 8,
    base_maps: dict[int, np.ndarray] | None = None,
    source: str = SOURCE_TRIMS,
    wideband_gain: float = WIDEBAND_GAIN,
    wideband_offset: float = WIDEBAND_OFFSET,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """``base_maps`` maps a table index to its factory VE values ``[len(axis_map), len(axis_rpm)]``;
    for every table with data a corrected copy, ``base * (1 + error / 100)``, is added."""
    messages = messages if messages is not None else []
    base_maps = base_maps or {}
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_map = np.asarray(axis_map, dtype=float).ravel()
    axis_idx = np.arange(1, n_tables + 1, dtype=float)

    if source == SOURCE_WIDEBAND:
        d, error = wideband_error(data, v, wideband_gain, wideband_offset, messages)
        label = "VE Error from Wideband (%)"
    else:
        d, error = trim_error(data, v, messages)
        label = "Correction (%)"

    maps3d, counts3d = trilinear(
        column(d, v["rpm"]), column(d, v["map"]), column(d, v["ve_table"]), error,
        axis_rpm, axis_map, axis_idx, min_samples,
    )
    out = []
    for z in range(n_tables):
        corr = maps3d[:, :, z]
        out.append(CalibrationMap(
            f"ve{z + 1}", f"VE Table {z + 1} {label}", corr, axis_rpm, axis_map,
            counts=counts3d[:, :, z], counts_title=f"VE Table {z + 1} - SAMPLE WEIGHTS",
            corner_label="MAP \\ RPM", skip_if_empty=True,
        ))
        base = base_maps.get(z + 1)
        if base is None or np.isnan(corr).all():
            continue
        base = np.asarray(base, dtype=float)
        if base.shape != corr.shape:
            messages.append(f"VE Table {z + 1}: base map is {base.shape}, correction is {corr.shape}; not corrected.")
            continue
        corrected = np.where(np.isnan(corr), base, base * (1.0 + corr / 100.0))
        out.append(CalibrationMap(
            f"ve{z + 1}_corrected", f"VE Table {z + 1} Corrected (paste into TunerPro)", corrected,
            axis_rpm, axis_map, corner_label="MAP \\ RPM",
        ))
    return out
