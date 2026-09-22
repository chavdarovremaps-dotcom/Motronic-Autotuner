"""WinOLS CSV export parser: pulls map axes and factory values into a preset.

Port of the ImportWinOLS_ButtonPushed callback in Scripts/GUI_app_code.m,
including its orientation healing for ME7 maps that WinOLS exports with
RPM on the x axis.

The export is semicolon separated, one map per line. Fields used (1-based
as in the MATLAB code): 2 = map id name, 8 = x axis name, 9 = x axis unit,
14 = columns, 15 = rows, and the last three = map values, x axis values,
y axis values, each a space separated list of numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

STATUS_LOADED = "Loaded"
STATUS_DIRECT = "Loaded (Direct)"
STATUS_FROM_JSON = "Loaded (From JSON)"
STATUS_FLIPPED = "RPM Flipped"
STATUS_TRANSPOSED = "Size Auto-Transposed"
STATUS_MISMATCH = "Axis Size Mismatch"
STATUS_MATRIX_ERROR = "Matrix Error"
STATUS_EMPTY = "Empty Data"
STATUS_MISSING = "Missing"

OK_STATUSES = {STATUS_LOADED, STATUS_DIRECT, STATUS_FROM_JSON, STATUS_FLIPPED, STATUS_TRANSPOSED}

_RPM_NAME_WORDS = ("motordrehzahl", "rpm", "giri")
_RPM_UNIT_WORDS = ("u/min", "rpm", "1/min", "giri")


@dataclass(frozen=True)
class TargetMap:
    winols_name: str
    y_axis_key: str
    x_axis_key: str
    base_map_key: str
    area: str
    direct: bool = False
    """Store exactly as exported (x = columns, y = rows) with no ME7 orientation healing."""


@dataclass
class MapStatus:
    name: str
    status: str
    dims: str
    area: str

    @property
    def ok(self) -> bool:
        return self.status in OK_STATUSES


@dataclass
class ImportResult:
    axes: dict[str, np.ndarray] = field(default_factory=dict)
    base_maps: dict[str, np.ndarray] = field(default_factory=dict)
    rows: list[MapStatus] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        return [r.name for r in self.rows if r.status == STATUS_MISSING]

    @property
    def loaded(self) -> int:
        return sum(1 for r in self.rows if r.ok)


def _numbers(text: str) -> np.ndarray:
    try:
        return np.array(text.replace(",", " ").split(), dtype=float)
    except ValueError:
        return np.array([], dtype=float)


def read_export_lines(path: str | Path) -> list[list[str]]:
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        return [line.rstrip("\r\n").split(";") for line in f]


def find_map(lines: list[list[str]], winols_name: str) -> list[str] | None:
    """First export line whose map id equals ``winols_name`` or starts with ``winols_name + "_"``."""
    for parts in lines:
        if len(parts) > 15:
            name = parts[1].strip()
            if name == winols_name or name.startswith(winols_name + "_"):
                return parts
    return None


def parse_export(path: str | Path, targets: list[TargetMap]) -> ImportResult:
    lines = read_export_lines(path)
    result = ImportResult()
    for t in targets:
        status = MapStatus(t.winols_name, STATUS_MISSING, "-", t.area)
        result.rows.append(status)
        parts = find_map(lines, t.winols_name)
        if parts is None:
            continue
        _extract(parts, t, result, status)
    return result


def _extract(parts: list[str], t: TargetMap, result: ImportResult, status: MapStatus) -> None:
    try:
        num_cols = int(float(parts[13]))
        num_rows = int(float(parts[14]))
    except ValueError:
        status.status = STATUS_MATRIX_ERROR
        return
    z = _numbers(parts[-3])
    x = _numbers(parts[-2])
    y = _numbers(parts[-1])
    if y.size == 0 and num_rows == 1:
        y = np.array([0.0])
    if x.size == 0 or y.size == 0 or z.size == 0:
        status.status = STATUS_EMPTY
        return

    x_name = parts[7].strip().lower()
    x_unit = parts[8].strip().lower()
    x_is_rpm = any(w in x_name for w in _RPM_NAME_WORDS) or any(w in x_unit for w in _RPM_UNIT_WORDS)
    expects_rpm_rows = "rpm" in t.y_axis_key.lower()
    needs_flip = expects_rpm_rows and x_is_rpm

    try:
        z_matrix = z.reshape(num_rows, num_cols)
    except ValueError:
        status.status = STATUS_MATRIX_ERROR
        return

    size_mismatch = (x.size != num_cols) or (y.size != num_rows)
    can_heal = (x.size == num_rows) and (y.size == num_cols) and (num_rows != num_cols)

    if t.direct:
        result.base_maps[t.base_map_key] = z_matrix
        result.axes[t.x_axis_key] = x
        result.axes[t.y_axis_key] = y
        status.status, status.dims = STATUS_DIRECT, f"{num_rows} x {num_cols}"
    elif needs_flip:
        result.base_maps[t.base_map_key] = z_matrix.T.copy()
        result.axes[t.x_axis_key] = y
        result.axes[t.y_axis_key] = x
        status.status, status.dims = STATUS_FLIPPED, f"{num_cols} x {num_rows}"
    elif size_mismatch:
        if can_heal:
            result.base_maps[t.base_map_key] = z_matrix.T.copy()
            result.axes[t.x_axis_key] = x
            result.axes[t.y_axis_key] = y
            status.status, status.dims = STATUS_TRANSPOSED, f"{num_cols} x {num_rows}"
        else:
            status.status = STATUS_MISMATCH
    else:
        result.base_maps[t.base_map_key] = z_matrix
        result.axes[t.x_axis_key] = x
        result.axes[t.y_axis_key] = y
        status.status, status.dims = STATUS_LOADED, f"{num_rows} x {num_cols}"


def status_from_preset(preset_base_maps: dict[str, np.ndarray], targets: list[TargetMap]) -> list[MapStatus]:
    """Status rows for maps already held in a loaded preset (LoadExistingProfile in the GUI)."""
    rows = []
    for t in targets:
        m = preset_base_maps.get(t.base_map_key)
        if m is not None and np.asarray(m).size:
            m2 = np.atleast_2d(np.asarray(m))
            rows.append(MapStatus(t.winols_name, STATUS_FROM_JSON, f"{m2.shape[0]} x {m2.shape[1]}", t.area))
        else:
            rows.append(MapStatus(t.winols_name, STATUS_MISSING, "-", t.area))
    return rows
