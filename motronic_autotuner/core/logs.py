"""Logger CSV ingestion: read, clean, transient-filter, align, and split into
the Full, WOT, Warmup and Hot subsets.

Port of Scripts/Utilities/ProcessRawLogs.m (the GUI route) plus the column
scrubbing and fuzzy header matching of MS43_Tune_helper.m. The command-line
Prep_Bosch_ME.m differed only in using ``>`` instead of ``>=`` for the WOT
pedal test; the GUI's ``>=`` is used here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .preset import Preset

PrepHook = Callable[[pd.DataFrame, Preset, list[str]], pd.DataFrame]
"""Applied to each cleaned file before splitting. May return a new frame."""

FLAG_SHARE = 0.05
"""A text column is an ON/OFF flag when at least this share of its cells say ON or OFF."""


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
    """Session settings read from the ingestion tab. Infinite rates disable the transient filter."""

    max_rpm_roc: float = 1000.0
    max_pedal_roc: float = 33.0
    wot_min: float = 70.0
    temp_max: float = 80.0

    @property
    def transient_filter(self) -> bool:
        return math.isfinite(self.max_rpm_roc) or math.isfinite(self.max_pedal_roc)


def read_logger_csv(path: str | Path) -> pd.DataFrame:
    """Read one logger CSV into an all-numeric frame.

    Handles the shapes seen so far: ME7-Logger (header, units row, alias row,
    data), TunerPro (one title line above the header, a units row, ON/OFF
    text columns) and plain CSV. ON/OFF flags become 1/0, every other column
    is coerced to numbers, so units and alias rows become NaN and are dropped
    by the caller.
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
    for c in df.columns:
        if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]):
            s = df[c].astype(str).str.strip().str.upper()
            if s.isin(("ON", "OFF")).mean() > FLAG_SHARE:
                df[c] = s.map({"ON": 1.0, "OFF": 0.0})
    df = df.apply(pd.to_numeric, errors="coerce")
    # trailing separators produce unnamed, empty columns; drop them so they
    # do not wipe every row in dropna()
    unnamed = [c for c in df.columns if c.startswith("Unnamed:") and df[c].isna().all()]
    return df.drop(columns=unnamed)


def resolve_columns(df: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """Rename columns so each wanted name is present when a case-insensitive
    or substring match exists (the MS43 helper's fuzzy header matcher)."""
    cols = list(df.columns)
    lower = [c.lower() for c in cols]
    rename = {}
    for name in names:
        if not name or name in cols:
            continue
        target = name.lower()
        idx = next((i for i, c in enumerate(lower) if c == target), None)
        if idx is None:
            idx = next((i for i, c in enumerate(lower) if target in c), None)
        if idx is not None and cols[idx] not in rename:
            rename[cols[idx]] = name
    return df.rename(columns=rename) if rename else df


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


def process_raw_logs(
    folder: str | Path,
    preset: Preset,
    settings: IngestSettings,
    hooks: list[PrepHook] | None = None,
    *,
    reader: Callable[[Path], pd.DataFrame] = read_logger_csv,
    fuzzy_columns: bool = False,
    required_columns: list[str] | None = None,
) -> SplitLogs:
    """Read every CSV in ``folder`` and return the four filtered subsets.

    ``required_columns`` limits the NaN row drop to those columns (the MS43
    helper's "smart NaN filter"); by default a row with any NaN is dropped,
    as the ME7 scripts do.
    """
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
        df = reader(path)
        if fuzzy_columns:
            df = resolve_columns(df, [v for v in preset.vars.values() if v])
        if len(df) > 1:
            df = df.iloc[:-1]
        if required_columns:
            present = [c for c in required_columns if c in df.columns]
            df = df.dropna(subset=present) if present else df
        else:
            df = df.dropna()
        df = df.reset_index(drop=True)
        if len(df) < 2:
            log.append(f"  -> [SKIP] {path.name}: Insufficient rows after cleanup.")
            continue

        cols = set(df.columns)
        if settings.transient_filter:
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
        else:
            log.append(f"  -> Loaded {path.name}: {len(df)} rows.")

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
