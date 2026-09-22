"""TunerPro XDF definitions plus a binary: read map axes and values.

Covers what tuning definitions use in practice: XDFTABLE entries whose
axes are either literal LABELs or linked (``embedinfo type="3"``) to another
table whose z data holds the axis values, EMBEDDEDDATA with 8, 16 or 32 bit
elements, signed or unsigned, either byte order, and MATH equations of the
form ``a*X+b`` (any arithmetic in X, evaluated with a tiny safe evaluator).
"""

from __future__ import annotations

import ast
import operator
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Pow: operator.pow,
}


def evaluate(equation: str, x: np.ndarray) -> np.ndarray:
    """Evaluate an XDF MATH equation such as ``0.0082921489*X`` or ``X/8-40`` on an array."""
    expr = equation.replace("^", "**")
    tree = ast.parse(expr, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id.upper() == "X":
            return x
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"unsupported XDF equation: {equation!r}")

    return np.asarray(ev(tree), dtype=float)


FLAG_SIGNED = 0x01
FLAG_LSB_FIRST = 0x02
FLAG_COLUMN_MAJOR = 0x04
FLAG_FLOAT = 0x10000


@dataclass
class Embedded:
    address: int | None
    element_bits: int
    rows: int
    cols: int
    signed: bool
    lsb_first: bool
    equation: str = "X"
    column_major: bool = False
    is_float: bool = False


@dataclass
class Axis:
    id: str
    count: int
    units: str = ""
    labels: list[float] | None = None
    text_labels: list[str] | None = None
    link_id: str | None = None
    embedded: Embedded | None = None


@dataclass
class Table:
    uid: str
    title: str
    description: str = ""
    axes: dict[str, Axis] = field(default_factory=dict)

    @property
    def z(self) -> Embedded | None:
        a = self.axes.get("z")
        return a.embedded if a else None


@dataclass
class XdfMap:
    title: str
    values: np.ndarray
    x_axis: np.ndarray
    y_axis: np.ndarray
    x_units: str = ""
    y_units: str = ""
    z_units: str = ""


class Xdf:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        root = ET.parse(self.path).getroot()
        header = root.find("XDFHEADER")
        self.title = _text(header, "deftitle") if header is not None else ""
        base = header.find("BASEOFFSET") if header is not None else None
        self.base_offset = int(base.get("offset", "0")) if base is not None else 0
        self.base_subtract = base is not None and base.get("subtract", "0") == "1"
        defaults = header.find("DEFAULTS") if header is not None else None
        self.default_bits = int(defaults.get("datasizeinbits", "8")) if defaults is not None else 8
        self.default_signed = defaults is not None and defaults.get("signed", "0") == "1"
        self.default_lsb_first = defaults is None or defaults.get("lsbfirst", "1") == "1"

        self.tables: dict[str, Table] = {}
        self.by_uid: dict[str, Table] = {}
        for el in root.iter("XDFTABLE"):
            t = self._parse_table(el)
            self.tables[t.title] = t
            self.by_uid[t.uid.lower()] = t

    # ---- parsing ------------------------------------------------------------

    def _parse_table(self, el: ET.Element) -> Table:
        t = Table(uid=el.get("uniqueid", "0x0"), title=_text(el, "title"), description=_text(el, "description"))
        for ax in el.findall("XDFAXIS"):
            axis = Axis(id=ax.get("id", ""), count=int(_text(ax, "indexcount") or "0"), units=_text(ax, "units"))
            labels = ax.findall("LABEL")
            if labels:
                ordered = sorted(labels, key=lambda l: int(l.get("index", "0")))
                axis.text_labels = [l.get("value", "") for l in ordered]
                try:
                    axis.labels = [float(s) for s in axis.text_labels]
                except ValueError:
                    # text labels such as "Map 1": the axis is positional
                    axis.labels = [float(i) for i in range(len(ordered))]
            link = ax.find("embedinfo")
            if link is not None and link.get("type") == "3" and link.get("linkobjid"):
                axis.link_id = link.get("linkobjid").lower()
            emb = ax.find("EMBEDDEDDATA")
            math = ax.find("MATH")
            equation = math.get("equation", "X") if math is not None else "X"
            if emb is not None:
                flags = int(emb.get("mmedtypeflags", "0x0"), 16)
                addr = emb.get("mmedaddress")
                axis.embedded = Embedded(
                    address=int(addr, 16) if addr else None,
                    element_bits=int(emb.get("mmedelementsizebits", str(self.default_bits))),
                    rows=int(emb.get("mmedrowcount", "1") or 1),
                    cols=int(emb.get("mmedcolcount", "1") or 1),
                    signed=bool(flags & FLAG_SIGNED) or (flags == 0 and self.default_signed),
                    lsb_first=bool(flags & FLAG_LSB_FIRST) if flags else self.default_lsb_first,
                    equation=equation,
                    column_major=bool(flags & FLAG_COLUMN_MAJOR),
                    is_float=bool(flags & FLAG_FLOAT),
                )
            t.axes[axis.id] = axis
        return t

    # ---- reading ------------------------------------------------------------

    def find(self, pattern: str) -> list[Table]:
        rx = re.compile(pattern, re.I)
        return [t for t in self.tables.values() if rx.search(t.title)]

    def _file_offset(self, address: int) -> int:
        return address - self.base_offset if self.base_subtract else address + self.base_offset

    def read_raw(self, data: bytes, emb: Embedded) -> np.ndarray:
        if emb.address is None:
            raise ValueError("axis has no address")
        n = emb.rows * emb.cols
        order = "<" if emb.lsb_first else ">"
        if emb.is_float:
            dtype = order + {32: "f4", 64: "f8"}[emb.element_bits]
        else:
            dtype = {8: "i1" if emb.signed else "u1", 16: order + ("i2" if emb.signed else "u2"),
                     32: order + ("i4" if emb.signed else "u4")}[emb.element_bits]
        offset = self._file_offset(emb.address)
        raw = np.frombuffer(data, dtype=dtype, count=n, offset=offset).astype(float)
        values = evaluate(emb.equation, raw)
        if emb.column_major:
            return values.reshape(emb.cols, emb.rows).T.copy()
        return values.reshape(emb.rows, emb.cols)

    def read_axis(self, data: bytes, axis: Axis) -> np.ndarray:
        if axis.link_id:
            linked = self.by_uid.get(axis.link_id)
            if linked is None or linked.z is None:
                raise ValueError(f"axis links to unknown table {axis.link_id}")
            return self.read_raw(data, linked.z).ravel()[: axis.count]
        if axis.embedded is not None and axis.embedded.address is not None:
            return self.read_raw(data, axis.embedded).ravel()[: axis.count]
        if axis.labels is not None:
            return np.asarray(axis.labels, dtype=float)[: axis.count]
        return np.arange(axis.count, dtype=float)

    def read_map(self, data: bytes, title: str) -> XdfMap:
        t = self.tables[title]
        if t.z is None:
            raise ValueError(f"table {title} has no data")
        values = self.read_raw(data, t.z)
        x = self.read_axis(data, t.axes["x"]) if "x" in t.axes else np.arange(values.shape[1], dtype=float)
        y = self.read_axis(data, t.axes["y"]) if "y" in t.axes else np.arange(values.shape[0], dtype=float)
        return XdfMap(
            title=title, values=values, x_axis=x, y_axis=y,
            x_units=t.axes["x"].units if "x" in t.axes else "",
            y_units=t.axes["y"].units if "y" in t.axes else "",
            z_units=t.axes["z"].units if "z" in t.axes else "",
        )


def load_bin(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def _text(el: ET.Element | None, tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


# ---- map import for a family's target list ---------------------------------


def import_xdf_maps(xdf_path: str | Path, bin_path: str | Path, targets):
    """Read every target map's values and axes from an XDF plus binary.

    Returns the same ``ImportResult`` shape as the WinOLS importer so the
    profile tab can treat both sources alike. Target names are XDF table
    titles.
    """
    from .winols import STATUS_LOADED, STATUS_MATRIX_ERROR, STATUS_MISSING, ImportResult, MapStatus

    xdf = Xdf(xdf_path)
    data = load_bin(bin_path)
    result = ImportResult()
    for t in targets:
        status = MapStatus(t.winols_name, STATUS_MISSING, "-", t.area)
        result.rows.append(status)
        if t.winols_name not in xdf.tables:
            continue
        try:
            m = xdf.read_map(data, t.winols_name)
        except Exception:
            status.status = STATUS_MATRIX_ERROR
            continue
        result.base_maps[t.base_map_key] = m.values
        result.axes[t.x_axis_key] = m.x_axis
        result.axes[t.y_axis_key] = m.y_axis
        status.status = STATUS_LOADED
        status.dims = f"{m.values.shape[0]} x {m.values.shape[1]}"
    return result
