"""TunerPro RT logs: one CSV per session, a title line, the channel names,
a units row, then one row per sample. ON/OFF channels become 1 / 0."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..core.logs import read_logger_csv


def read_log(path: str | Path) -> pd.DataFrame:
    """One TunerPro CSV as an all-numeric frame. The units row is dropped and
    the unnamed first column is called ``Sample``."""
    df = read_logger_csv(path)
    df = df.dropna(how="all").reset_index(drop=True)
    if len(df.columns) and df.columns[0].startswith("Unnamed:"):
        df = df.rename(columns={df.columns[0]: "Sample"})
    return df


def read_logs(path: str | Path) -> pd.DataFrame:
    """A CSV file, or every CSV in a folder, as one frame with a ``File`` column."""
    path = Path(path)
    files = [path] if path.is_file() else sorted(path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV logs in {path}")
    frames = []
    for f in files:
        df = read_log(f)
        df.insert(0, "File", f.name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
