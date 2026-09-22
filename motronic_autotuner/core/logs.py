"""Logger CSV ingestion: read, clean, transient-filter, align, and split into
the Full, WOT, Warmup and Hot subsets.

Port of Scripts/Utilities/ProcessRawLogs.m (the GUI route). The command-line
Prep_Bosch_ME.m differed only in using ``>`` instead of ``>=`` for the WOT
pedal test; the GUI's ``>=`` is used here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .preset import Preset

PrepHook = Callable[[pd.DataFrame, Preset, list[str]], pd.DataFrame]
"""Applied to each cleaned file before splitting. May return a new frame."""


@dataclass
class SplitLogs:
    full: pd.DataFrame = field(default_factory=pd.DataFrame)
    wot: pd.DataFrame = field(default_factory=pd.DataFrame)
    warmup: pd.DataFrame = field(default_factory=pd.DataFrame)
    hot: pd.DataFrame = field(default_factory=pd.DataFrame)
    messages: list[str] = field(default_factory=list)

    def subset(self, name: str) -> pd.DataFrame:
        return getattr(self, name)

    def counts(self) -> dict[str, int]:
        return {k: len(getattr(self, k)) for k in ("full", "wot", "warmup", "hot")}


@dataclass
class IngestSettings:
    """Session settings read from the ingestion tab (not stored in the preset by the GUI at import time)."""

    max_rpm_roc: float = 1000.0
    max_pedal_roc: float = 33.0
    wot_min: float = 70.0
    temp_max: float = 80.0


def read_logger_csv(path: str | Path) -> pd.DataFrame:
    """Read one logger CSV into an all-numeric frame.

    Handles the three shapes seen so far: ME7-Logger (header, units row, alias
    row, data), TunerPro (one extra title line above the header) and plain
    CSV. Every column is coerced to numbers, so units and alias rows become
    NaN and are dropped by the caller.
    """
    path = Path(path)
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        first = f.readline()
    skip = 1 if "TunerPro" in first else 0
    df = pd.read_csv(
        path,
        skiprows=skip,
        encoding="latin-1",
        encoding_errors="replace",
        skipinitialspace=True,
        low_memory=False,
    )
    df.columns = [str(c).strip() for c in df.columns]
    df = df.apply(pd.to_numeric, errors="coerce")
    # trailing separators produce unnamed, empty columns; drop them so they
    # do not wipe every row in dropna()
    unnamed = [c for c in df.columns if c.startswith("Unnamed:") and df[c].isna().all()]
    return df.drop(columns=unnamed)


def transient_mask(time: np.ndarray, rpm: np.ndarray, pedal: np.ndarray,
                   max_rpm_roc: float, max_pedal_roc: float) -> np.ndarray:
    """Rows whose RPM and pedal rates of change are within limits."""
    dt = np.concatenate(([0.1], np.diff(time)))
    dt = np.where(dt <= 0, 0.001, dt)
    rpm_roc = np.concatenate(([0.0], np.diff(rpm))) / dt
    pedal_roc = np.concatenate(([0.0], np.diff(pedal))) / dt
    return (np.abs(rpm_roc) <= max_rpm_roc) & (np.abs(pedal_roc) <= max_pedal_roc)


def hack_5120(df: pd.DataFrame, preset: Preset, messages: list[str]) -> pd.DataFrame:
    """Double every listed pressure column when the 5120 mbar hack is on."""
    if not preset.prep.get("hack_5120", False):
        return df
    for col in preset.prep.get("pressure_columns", []):
        if col in df.columns:
            df[col] = df[col] * 2.0
    return df


def process_raw_logs(folder: str | Path, preset: Preset, settings: IngestSettings,
                     hooks: list[PrepHook] | None = None) -> SplitLogs:
    """Read every CSV in ``folder`` and return the four filtered subsets."""
    folder = Path(folder)
    files = sorted(folder.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in: {folder}")
    hooks = list(hooks or [])

    out = SplitLogs()
    log = out.messages
    parts = {"full": [], "wot": [], "warmup": [], "hot": []}
    global_offset = 0.0

    pedal_col, rpm_col = preset.var("pedal"), preset.var("rpm")
    temp_col, time_col = preset.var("tmot"), preset.var("time")

    for path in files:
        df = read_logger_csv(path)
        if len(df) > 1:
            df = df.iloc[:-1]
        df = df.dropna().reset_index(drop=True)
        if len(df) < 2:
            log.append(f"  -> [SKIP] {path.name}: Insufficient rows after cleanup.")
            continue

        cols = set(df.columns)
        if {time_col, rpm_col, pedal_col} <= cols:
            keep = transient_mask(
                df[time_col].to_numpy(float), df[rpm_col].to_numpy(float),
                df[pedal_col].to_numpy(float), settings.max_rpm_roc, settings.max_pedal_roc,
            )
            removed = int((~keep).sum())
            df = df[keep].reset_index(drop=True)
            log.append(f"  -> [FILTER] {path.name}: Removed {removed} transient rows.")
        else:
            log.append(f"  -> [WARNING] {path.name}: Missing required columns. Skipping filter.")

        if len(df) < 1:
            log.append(f"  -> [SKIP] {path.name}: 0 rows remaining after transient filtering.")
            continue

        if preset.prep.get("align_timestamps", False) and time_col in cols:
            df[time_col] = df[time_col] + global_offset
            global_offset = float(df[time_col].max())

        for hook in hooks:
            df = hook(df, preset, log)

        parts["full"].append(df)
        if pedal_col in cols:
            wot = df[df[pedal_col] >= settings.wot_min]
            if len(wot):
                parts["wot"].append(wot)
        if temp_col in cols:
            warm = df[df[temp_col] < settings.temp_max]
            hot = df[df[temp_col] >= settings.temp_max]
            if len(warm):
                parts["warmup"].append(warm)
            if len(hot):
                parts["hot"].append(hot)

    for name, frames in parts.items():
        if frames:
            setattr(out, name, pd.concat(frames, ignore_index=True))
    return out
