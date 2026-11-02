"""Patches: fixed values written into an MS43X binary through the XDF.

A patch lists XDF objects and the values to write, in the copy-paste layout
of the MS4X wiki: the object's name on its own line, then its values row by
row as TunerPro shows them (one value per line for a curve). Names are XDF
titles; a wiki name without the axis suffix the XDF adds (ip_pvs_isa_isapwm
for ip_pvs_isa_isapwm__isapwm) matches the one title that starts with the
name and a double underscore.

Nothing is written unless every object is found, the patch has its shape,
and every value fits the stored type. Then every object is read back and
compared, the monitor sum is recalculated and the calibration CRC kept equal
to the input bin's (see checksum.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..core.xdf import Table, Xdf, linear_coefficients
from . import checksum

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SHOW_CELLS = 12
"""Objects up to this many cells are reported value by value."""


@dataclass(frozen=True)
class Patch:
    key: str
    title: str
    description: str
    values: str
    """Wiki copy-paste layout: a name line, then the value rows."""
    reminders: tuple[str, ...] = ()


class PatchError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass
class PatchResult:
    data: bytes
    lines: list[str]


def parse_values(text: str) -> list[tuple[str, np.ndarray]]:
    items: list[tuple[str, np.ndarray]] = []
    name, rows = None, []

    def flush():
        if name is None:
            return
        if not rows:
            raise ValueError(f"{name}: no values")
        if len({len(r) for r in rows}) != 1:
            raise ValueError(f"{name}: rows of different lengths")
        items.append((name, np.array(rows, dtype=float)))

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if NAME.match(s):
            flush()
            name, rows = s, []
            continue
        if name is None:
            raise ValueError(f"values before the first name: {s!r}")
        try:
            rows.append([float(v) for v in s.split()])
        except ValueError:
            raise ValueError(f"{name}: not a row of numbers: {s!r}") from None
    flush()
    return items


def resolve(xdf: Xdf, name: str) -> tuple[str, Table]:
    """The XDF title and object for a patch name; ValueError when it is missing or ambiguous."""
    t = xdf.lookup(name)
    if t is not None:
        return name, t
    hits = [title for title in [*xdf.tables, *xdf.constants] if title.startswith(name + "__")]
    if len(hits) == 1:
        return hits[0], xdf.lookup(hits[0])
    if hits:
        raise ValueError(f"{name}: matches several XDF titles ({', '.join(hits)})")
    raise ValueError(f"{name}: not found in the XDF")


def _fit(values: np.ndarray, rows: int, cols: int) -> np.ndarray | None:
    if values.shape == (rows, cols):
        return values
    if values.size == rows * cols and 1 in values.shape and 1 in (rows, cols):
        return values.reshape(rows, cols)
    return None


def _fmt(values: np.ndarray) -> str:
    return " ".join(f"{v:g}" for v in np.round(values.ravel(), 5))


def apply_patch(xdf: Xdf, data: bytes, patch: Patch,
                checksums: Callable[[bytes, bytes, list[str]], bytes] | None = checksum.fix) -> PatchResult:
    """The patched binary and a report; PatchError (nothing written) when any object fails.
    ``checksums`` makes the checksums of the patched bin as valid as the input's (None skips it)."""
    items = parse_values(patch.values)
    plans, problems = [], []
    for name, values in items:
        try:
            title, t = resolve(xdf, name)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        emb = t.z
        if emb is None or emb.address is None:
            problems.append(f"{name}: {title} has no data address in the XDF")
            continue
        fitted = _fit(values, emb.rows, emb.cols)
        if fitted is None:
            problems.append(f"{name}: the patch has {values.shape[0]} x {values.shape[1]} values, "
                            f"{title} is {emb.rows} x {emb.cols}")
            continue
        try:
            xdf.encode(emb, fitted)
            offset, size = xdf.span(emb)
            if offset < 0 or offset + size > len(data):
                raise ValueError(f"address {emb.address:#x} lies outside the binary")
        except ValueError as exc:
            problems.append(f"{name} ({title}): {exc}")
            continue
        plans.append((name, title, t, fitted))
    if problems:
        raise PatchError(problems)

    buf = bytearray(data)
    lines = [f"Patch: {patch.title}"]
    for name, title, t, values in plans:
        before = xdf.read_raw(data, t.z)
        xdf.write_raw(buf, t.z, values)
        after = xdf.read_raw(bytes(buf), t.z)
        step = abs(linear_coefficients(t.z.equation)[0])
        tol = step / 2 + 1e-9 if not t.z.is_float else 1e-6 * max(1.0, float(np.abs(values).max()))
        if np.abs(after - values).max() > tol:
            raise PatchError([f"{title}: read back {_fmt(after)} instead of {_fmt(values)}"])
        changed = int((np.abs(after - before) > step / 2).sum())
        label = name if title == name else f"{name} ({title})"
        if changed == 0:
            lines.append(f"  {label}: already at the patch values.")
        elif after.size <= SHOW_CELLS:
            lines.append(f"  {label}: {_fmt(before)}  ->  {_fmt(after)}")
        else:
            lines.append(f"  {label}: {changed} of {after.size} cells changed, "
                         f"{before.min():g} .. {before.max():g}  ->  {after.min():g} .. {after.max():g}")
    try:
        out = checksums(data, bytes(buf), lines) if checksums else bytes(buf)
    except ValueError as exc:
        raise PatchError([f"Checksum: {exc}"]) from None
    lines += [f"Reminder: {r}" for r in patch.reminders]
    return PatchResult(out, lines)


ICV_DELETE_M54B30 = Patch(
    key="icv_delete",
    title="Idle Control Valve delete (M54B30 values)",
    description=(
        "Removes the Idle Control Valve (ICV / ISA): the motorised throttle body supplies the idle air instead. "
        "ip_pvs_isa_isapwm is rescaled so the idle duty becomes a throttle opening, the ICV corrections, "
        "diagnosis and adaptation increments are neutralised. Values from the MS4X wiki, ICV Delete Values, "
        "for the M54B30.\n\n"
        "Physically: disconnect the ICV connector, then remove the ICV and plug the opening in the intake "
        "manifold (recommended), or leave it in place sealed so it cannot leak air."
    ),
    reminders=(
        "Clear the ECU idle adaptations after flashing: values learned with the ICV can upset the new idle control.",
        "These are M54B30 values. An M54B22 or M54B25 has a smaller throttle body and may need larger "
        "ip_pvs_isa_isapwm values, in proportion to the throttle opening area, for a stable idle.",
    ),
    values="""
c_n_isa_diag
8160
c_abc_inc_isa_1
0
c_abc_inc_isa_2
0
ip_fac_pq_isa_mon
1.000
1.000
1.000
1.000
ip_fac_pq_isa
1.000
1.000
1.000
1.000
ip_maf_max_isa_mon
0.00
0.00
0.00
0.00
0.00
0.00
ip_maf_max_isa
0.00
0.00
0.00
0.00
0.00
0.00
ip_isapwm_cor_isa
0.000
0.000
0.000
0.000
0.000
0.000
0.000
0.000
ip_fac_isapwm_accin_cor
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
ip_fac_isapwm_cor
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
0.99998 0.99998 0.99998 0.99998
ip_fac_pvs_isa
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
ldp_isapwm__pvs_isa_isapwm
0.000
12.000
17.499
26.001
40.997
75.000
109.998
158.002
171.002
179.999
190.002
200.000
ip_pvs_isa_isapwm
0.000
5.754
6.051
6.445
7.114
8.469
9.336
10.430
10.723
10.906
11.107
11.307
ip_cam_sp_in_isapwm_min
0.00 0.00
0.00 0.00
0.00 0.00
0.00 0.00
0.00 0.00
ip_iga_isapwm_min_is
0.00 0.00
0.00 0.00
0.00 0.00
0.00 0.00
0.00 0.00
ldpm_n_32_3
96
416
576
1184
1408
1600
2016
2496
3488
4512
5504
6496
ldpm_pvs_3
1.000
7.500
12.501
15.000
17.499
20.001
22.500
24.999
30.000
37.500
60.000
78.010
ip_isapwm_pvs
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
ip_tps_sp_pvs
0.000 0.000 0.000 0.000 0.401 0.826 1.761 2.644 4.039 5.145 6.249 7.066
2.234 2.234 2.234 2.234 2.234 2.280 2.470 2.964 4.039 5.145 6.249 7.066
5.255 5.255 5.255 5.255 5.255 5.257 5.259 5.259 5.259 5.760 6.249 7.066
7.053 7.053 7.053 7.053 7.053 7.055 7.057 7.057 7.059 7.064 7.066 7.601
9.014 9.014 9.014 9.014 9.016 9.018 9.020 9.020 9.022 9.029 9.031 9.042
11.127 11.127 11.127 11.127 11.127 11.129 11.131 11.133 11.135 11.142 11.146 11.158
13.369 13.369 13.369 13.369 13.370 13.372 13.376 13.376 13.378 13.389 13.392 13.407
15.732 15.732 15.732 15.732 15.732 15.736 15.740 15.742 15.743 15.754 15.758 15.776
20.782 20.782 20.782 20.782 20.782 20.786 20.790 20.792 20.795 20.810 20.814 20.837
29.002 29.002 29.002 29.002 29.004 29.008 29.013 29.015 29.019 29.035 29.042 29.070
56.587 56.587 56.587 56.587 56.589 56.592 56.596 56.598 56.602 56.616 56.622 56.646
81.000 81.000 81.000 81.000 81.000 81.000 81.000 81.000 81.000 81.000 81.000 81.000
""",
)

PATCHES = [ICV_DELETE_M54B30]
