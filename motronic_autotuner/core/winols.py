"""WinOLS CSV export parser: pulls map axes and factory values into a preset.

Port of the ImportWinOLS_ButtonPushed callback in Scripts/GUI_app_code.m,
including its orientation healing for ME7 maps that WinOLS exports with
RPM on the x axis.

The export is semicolon separated, one map per line, with a header line
naming the fields. Fields used: ``IdName`` (index 1), ``Columns`` (13),
``Rows`` (14), ``AxisX.Name`` / ``AxisX.Unit`` / ``AxisY.Name`` /
``AxisY.Unit`` where the header has them, and the last three fields, the
map values, the x axis values and the y axis values, each a space
separated list of numbers.

Orientation: the tool keeps rpm on the rows of every map whose y axis key
says rpm. Which exported axis is the rpm one is decided from the axis
values first (an increasing list from at least 300 to at least 2000), and
only when that is ambiguous from the export's axis names and units,
because WinOLS has been seen to export the value lists swapped against
the axis names (the 032HJ export) and to leave the names empty (the
362287 export). A map whose value lists are swapped against its declared
columns and rows is transposed back first.
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
_LEGACY_X_NAME, _LEGACY_X_UNIT = 7, 8
"""Where the MATLAB code read the x axis name and unit; kept for exports without a header."""
RPM_AXIS_MIN, RPM_AXIS_TOP = 300.0, 2000.0


@dataclass(frozen=True)
class TargetMap:
    winols_name: str
    y_axis_key: str
    x_axis_key: str
    base_map_key: str
    area: str
    direct: bool = False
    """Report as "Loaded (Direct)"; the rpm-on-rows rule still applies when the y axis key says rpm."""


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


def header_fields(lines: list[list[str]]) -> dict[str, int]:
    """Field name -> index from the export's header line, empty when there is none."""
    if not lines:
        return {}
    names = [s.strip() for s in lines[0]]
    return {n: i for i, n in enumerate(names)} if "IdName" in names else {}


def looks_like_rpm(values) -> bool:
    """An increasing axis from at least 300 to at least 2000 with three or more points."""
    v = np.asarray(values, dtype=float).ravel()
    return v.size >= 3 and bool(np.all(np.diff(v) > 0)) and float(v.min()) >= RPM_AXIS_MIN and float(v.max()) >= RPM_AXIS_TOP


def _says_rpm(name: str, unit: str) -> bool:
    name, unit = name.strip().lower(), unit.strip().lower()
    return any(w in name for w in _RPM_NAME_WORDS) or any(w in unit for w in _RPM_UNIT_WORDS)


def _axis_text(parts: list[str], header: dict[str, int]) -> tuple[bool, bool]:
    """Whether the export's own names or units call the x and the y axis an rpm axis."""
    def field(key: str, legacy: int | None = None) -> str:
        i = header.get(key, legacy)
        return parts[i] if i is not None and i < len(parts) else ""
    x = _says_rpm(field("AxisX.Name", _LEGACY_X_NAME), field("AxisX.Unit", _LEGACY_X_UNIT))
    y = _says_rpm(field("AxisY.Name"), field("AxisY.Unit"))
    return x, y


def _rpm_is_on_x(x: np.ndarray, y: np.ndarray, x_text: bool, y_text: bool) -> bool:
    x_num, y_num = looks_like_rpm(x), looks_like_rpm(y)
    if x_num != y_num:
        return x_num
    return x_text and not y_text


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
    header = header_fields(lines)
    result = ImportResult()
    for t in targets:
        status = MapStatus(t.winols_name, STATUS_MISSING, "-", t.area)
        result.rows.append(status)
        parts = find_map(lines, t.winols_name)
        if parts is None:
            continue
        _extract(parts, t, result, status, header)
    return result


def _extract(parts: list[str], t: TargetMap, result: ImportResult, status: MapStatus,
             header: dict[str, int] | None = None) -> None:
    header = header or {}
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
    try:
        z_matrix = z.reshape(num_rows, num_cols)
    except ValueError:
        status.status = STATUS_MATRIX_ERROR
        return

    # the value lists swapped against the declared columns and rows: transpose back
    healed = False
    if x.size != num_cols or y.size != num_rows:
        if x.size == num_rows and y.size == num_cols and num_rows != num_cols:
            z_matrix = z_matrix.T.copy()
            healed = True
        else:
            status.status = STATUS_MISMATCH
            return
    # from here z_matrix is (y.size, x.size): x along the columns, y down the rows

    expects_rpm_rows = "rpm" in t.y_axis_key.lower()
    x_text, y_text = _axis_text(parts, header)
    if expects_rpm_rows and _rpm_is_on_x(x, y, x_text, y_text):
        result.base_maps[t.base_map_key] = z_matrix.T.copy()
        result.axes[t.x_axis_key] = y
        result.axes[t.y_axis_key] = x
        status.status, status.dims = STATUS_FLIPPED, f"{x.size} x {y.size}"
    else:
        result.base_maps[t.base_map_key] = z_matrix
        result.axes[t.x_axis_key] = x
        result.axes[t.y_axis_key] = y
        status.status = STATUS_DIRECT if t.direct else (STATUS_TRANSPOSED if healed else STATUS_LOADED)
        status.dims = f"{y.size} x {x.size}"


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
