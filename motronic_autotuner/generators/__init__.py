"""Map generators, one module per calibration area. Pure math: pandas in, CalibrationMap out."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap


def column(data: pd.DataFrame, name: str) -> np.ndarray:
    """A log column as a float array, with a clear error when it is missing."""
    if name not in data.columns:
        raise KeyError(f"Column '{name}' not found in logs")
    return data[name].to_numpy(dtype=float)


def column_ci(data: pd.DataFrame, name: str) -> np.ndarray | None:
    """Case-insensitive column lookup; None when absent."""
    for c in data.columns:
        if c.lower() == name.lower():
            return data[c].to_numpy(dtype=float)
    return None


def trim_percent(stft: np.ndarray, ltft: np.ndarray, trim_format: str) -> np.ndarray:
    """Combined fuel trim in percent.

    ``"lambda"``: trims are multiplicative factors, ``(stft * ltft - 1) * 100``.
    ``"percent"``: trims are already percentages, ``stft + ltft``.
    """
    if trim_format == "percent":
        return stft + ltft
    return (stft * ltft - 1.0) * 100.0


STFT_NEUTRAL_TOL = 1e-5
"""Below one step of frm_w (1/32768): a short-term trim this close to neutral is sitting on it."""


def lambda_control_on(stft: np.ndarray, trim_format: str) -> np.ndarray:
    """Rows where the lambda control is regulating. A short-term trim of exactly
    1.0 (lambda format) or 0 % (percent format) is the controller not running
    yet, or not at all: cold start before the sensor is ready, open loop at full
    load, fuel cut. Such rows say nothing about the fueling."""
    stft = np.asarray(stft, dtype=float)
    neutral = 0.0 if trim_format == "percent" else 1.0
    return np.isfinite(stft) & ~np.isclose(stft, neutral, rtol=0.0, atol=STFT_NEUTRAL_TOL)


def drop_lambda_off(data: pd.DataFrame, v: dict[str, str], trim_format: str, label: str,
                    messages: list[str] | None) -> pd.DataFrame:
    """``data`` without the rows whose lambda control is not regulating, with a line saying how many went."""
    on = lambda_control_on(column(data, v["stft"]), trim_format)
    if messages is not None and len(data) and not on.all():
        neutral = "0 %" if trim_format == "percent" else "1.0"
        messages.append(f"  {label}: {int((~on).sum())} of {len(data)} rows left out, short-term trim at exactly "
                        f"{neutral} (lambda control not running).")
    return data[on]


def near_gear_change(gear, time, blank_s: float) -> np.ndarray:
    """True for rows within ``blank_s`` seconds of a gear change.

    Automatic shifts close the throttle and cut fuel for a few hundred
    milliseconds; the trims, boost and knock channels are meaningless there.
    """
    gear = np.asarray(gear, dtype=float)
    time = np.asarray(time, dtype=float)
    out = np.zeros(gear.size, dtype=bool)
    if gear.size < 2 or blank_s <= 0:
        return out
    for i in np.flatnonzero(np.diff(gear) != 0) + 1:
        out |= np.abs(time - time[i]) <= blank_s
    return out


def axis_block(key: str, title: str, axis, label: str) -> CalibrationMap:
    """A computed axis as a one-row block, points numbered from 1, for pasting into WinOLS."""
    axis = np.asarray(axis, dtype=float).ravel()
    return CalibrationMap(key, title, axis, np.arange(1, axis.size + 1), [label], corner_label="Point")
