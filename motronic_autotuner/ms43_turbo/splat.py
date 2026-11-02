"""Put log rows onto a map grid, each row shared by the 4 cells around it.

A row whose x lies between breakpoints x[i] and x[i+1] at fraction fx, and
whose y lies between y[j] and y[j+1] at fraction fy, adds its value to the
four cells with weights (1-fx)(1-fy), fx(1-fy), (1-fx)fy and fx*fy. A row
exactly on a breakpoint goes to that cell alone; a row outside the axis is
held at the edge. Each cell's value is its weighted sum over its summed
weight, and cells whose summed weight is below ``min_weight`` stay empty.

An optional weight per row scales its four shares, e.g. 0.25 for a row the
ECU took a quarter from this table and three quarters from the next one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..core.splatting import locate


@dataclass
class Splat:
    values: np.ndarray
    """``[len(y_axis), len(x_axis)]``, NaN where the summed weight is below ``min_weight``."""
    weights: np.ndarray
    """Summed row weight per cell: how many rows the cell has, counting a shared row by its share."""
    x_axis: np.ndarray
    y_axis: np.ndarray


def splat_values(x, y, z, x_axis, y_axis, min_weight: float = 1.0, row_weight=None) -> Splat:
    """Average ``z`` over the grid; ``x`` runs along the columns, ``y`` down the rows.
    Rows with a missing x, y, z or weight, or a weight of zero, are skipped."""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    z = np.asarray(z, dtype=float).ravel()
    w = np.ones_like(x) if row_weight is None else np.asarray(row_weight, dtype=float).ravel()
    if not (x.size == y.size == z.size == w.size):
        raise ValueError("x, y, z and the row weights must have the same length")
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z) & np.isfinite(w) & (w > 0)
    x, y, z, w = x[ok], y[ok], z[ok], w[ok]
    x_axis = np.asarray(x_axis, dtype=float).ravel()
    y_axis = np.asarray(y_axis, dtype=float).ravel()
    nx, ny = x_axis.size, y_axis.size
    xi, fx = locate(x, x_axis)
    yi, fy = locate(y, y_axis)
    sums = np.zeros((ny, nx))
    weights = np.zeros((ny, nx))
    for dr, dc, share in ((0, 0, (1 - fy) * (1 - fx)), (1, 0, fy * (1 - fx)), (0, 1, (1 - fy) * fx), (1, 1, fy * fx)):
        rows, cols = yi + dr, xi + dc
        inside = (rows < ny) & (cols < nx) & (share > 0)
        np.add.at(sums, (rows[inside], cols[inside]), (share * w * z)[inside])
        np.add.at(weights, (rows[inside], cols[inside]), (share * w)[inside])
    values = np.full((ny, nx), np.nan)
    hit = (weights > 0) & (weights >= min_weight)
    values[hit] = sums[hit] / weights[hit]
    return Splat(values, weights, x_axis, y_axis)


def lookup_values(values, x_axis, y_axis, x, y) -> np.ndarray:
    """Read a grid at points with the same 4-cell weights the splat uses, held at
    the axis ends as the ECU does. NaN where a cell that carries weight is NaN,
    or where x or y is missing."""
    values = np.asarray(values, dtype=float)
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    ny, nx = values.shape
    xi, fx = locate(x, np.asarray(x_axis, dtype=float).ravel())
    yi, fy = locate(y, np.asarray(y_axis, dtype=float).ravel())
    out = np.zeros(x.size)
    for dr, dc, share in ((0, 0, (1 - fy) * (1 - fx)), (1, 0, fy * (1 - fx)), (0, 1, (1 - fy) * fx), (1, 1, fy * fx)):
        rows, cols = np.minimum(yi + dr, ny - 1), np.minimum(xi + dc, nx - 1)
        cell = values[rows, cols]
        out += np.where(share > 0, share * cell, 0.0)
    out[~(np.isfinite(x) & np.isfinite(y))] = np.nan
    return out


def splat(log: pd.DataFrame, x: str, y: str, z: str, x_axis, y_axis, min_weight: float = 1.0, row_weight=None) -> Splat:
    """Average channel ``z`` over the grid of channels ``x`` (columns) and ``y`` (rows)."""
    missing = [c for c in (x, y, z) if c not in log.columns]
    if missing:
        raise KeyError(f"Not in the log: {', '.join(missing)}")
    return splat_values(log[x], log[y], log[z], x_axis, y_axis, min_weight, row_weight)
