"""Map generators, one module per calibration area. Pure math: pandas in, CalibrationMap out."""

from __future__ import annotations

import numpy as np
import pandas as pd


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
