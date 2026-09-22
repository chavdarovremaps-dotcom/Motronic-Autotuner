"""MHD Flasher data logs.

Shape: a few ``#`` comment lines (encoding, CALID, PRGID, VIN), one header
row whose names carry the unit in brackets, e.g. ``Boost (Bar)`` or
``Boost (PSI)``, then data. The unit set follows the phone's settings, so
the reader strips the units from the names and converts every column to
one metric set: bar, degrees C, km/h. Names then match the family's
variable map regardless of how the log was recorded.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

_UNIT_RX = re.compile(r"^(?P<name>.*?)\s*\((?P<unit>[^()]*)\)\s*$")

PSI_PER_BAR = 14.5037738
KPA_PER_BAR = 100.0

# unit as MHD writes it -> (canonical unit, converter)
_CONVERT = {
    "psi": ("bar", lambda s: s / PSI_PER_BAR),
    "kpa": ("bar", lambda s: s / KPA_PER_BAR),
    "*f": ("c", lambda s: (s - 32.0) * 5.0 / 9.0),
    "°f": ("c", lambda s: (s - 32.0) * 5.0 / 9.0),
    "f": ("c", lambda s: (s - 32.0) * 5.0 / 9.0),
    "mph": ("km/h", lambda s: s * 1.609344),
}
_CANONICAL = {"bar": "bar", "*c": "c", "°c": "c", "c": "c", "km/h": "km/h"}


def split_unit(header: str) -> tuple[str, str]:
    """``"Boost (Bar)"`` -> ``("Boost", "Bar")``; a name without brackets keeps an empty unit."""
    m = _UNIT_RX.match(header.strip())
    if not m:
        return header.strip(), ""
    return m.group("name").strip(), m.group("unit").strip()


def is_mhd_log(path: str | Path) -> bool:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        first = f.readline()
    return first.startswith("#")


def read_mhd_csv(path: str | Path) -> pd.DataFrame:
    """Read an MHD log into an all-numeric frame with unit-free column names in metric units.

    The frame carries the original units per column in ``df.attrs["units"]``.
    """
    df = pd.read_csv(path, comment="#", encoding="utf-8-sig", encoding_errors="replace",
                     skipinitialspace=True, low_memory=False)
    names, units = {}, {}
    for col in df.columns:
        name, unit = split_unit(str(col))
        if name in names.values():  # duplicate after stripping: keep the unit to stay unique
            name = f"{name} ({unit})"
        names[col] = name
        units[name] = unit
    df = df.rename(columns=names)
    df = df.apply(pd.to_numeric, errors="coerce")
    for name, unit in units.items():
        key = unit.lower()
        if key in _CONVERT:
            canonical, fn = _CONVERT[key]
            df[name] = fn(df[name])
            units[name] = canonical
        elif key in _CANONICAL:
            units[name] = _CANONICAL[key]
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed:") and df[c].isna().all()]
    df = df.drop(columns=unnamed)
    df.attrs["units"] = units
    return df
