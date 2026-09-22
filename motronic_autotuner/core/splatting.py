"""Weighted scatter ("splatting") of log samples onto fixed axis grids.

Port of Scripts/Utilities/BilinearSplatting.m, LinearSplatting1D.m,
GetInterpolation.m and the TrilinearSplatting helper in MS43_Tune_helper.m.

Each sample is located between its neighbouring axis breakpoints and its
value is added to those cells with linear weights. A cell's result is its
weighted sum over its weighted count. Cells whose weighted count is below
``min_samples`` are left as NaN.
"""

from __future__ import annotations

import numpy as np

ArrayLike = "np.typing.ArrayLike"


def locate(values, axis) -> tuple[np.ndarray, np.ndarray]:
    """Lower breakpoint index and fraction for each value (GetInterpolation.m).

    Values at or below the first breakpoint map to (0, 0). Values at or above
    the last breakpoint map to (n - 1, 0). NaN maps to (n - 1, 0); callers
    mask NaN out before use.
    """
    axis = np.asarray(axis, dtype=float).ravel()
    v = np.asarray(values, dtype=float).ravel()
    n = axis.size
    if n == 0:
        raise ValueError("axis is empty")
    idx = np.searchsorted(axis, v, side="right") - 1
    idx = np.clip(idx, 0, n - 1)
    frac = np.zeros_like(v)
    inner = (v > axis[0]) & (v < axis[-1])
    if n > 1 and inner.any():
        i = idx[inner]
        frac[inner] = (v[inner] - axis[i]) / (axis[i + 1] - axis[i])
    return idx, frac


def _finalize(sums: np.ndarray, counts: np.ndarray, min_samples: float) -> tuple[np.ndarray, np.ndarray]:
    out = np.full(sums.shape, np.nan)
    hit = counts >= min_samples
    with np.errstate(invalid="ignore", divide="ignore"):
        out[hit] = sums[hit] / counts[hit]
    return out, counts


def _clean(*arrays) -> list[np.ndarray]:
    flat = [np.asarray(a, dtype=float).ravel() for a in arrays]
    length = flat[0].size
    for a in flat:
        if a.size != length:
            raise ValueError("all sample arrays must have the same length")
    ok = np.ones(length, dtype=bool)
    for a in flat:
        ok &= ~np.isnan(a)
    return [a[ok] for a in flat]


def linear_1d(x, z, x_axis, min_samples: float) -> tuple[np.ndarray, np.ndarray]:
    """1D splat. Returns (curve[nx], counts[nx])."""
    x, z = _clean(x, z)
    x_axis = np.asarray(x_axis, dtype=float).ravel()
    nx = x_axis.size
    xi, fx = locate(x, x_axis)
    sums = np.zeros(nx)
    counts = np.zeros(nx)
    np.add.at(sums, xi, (1 - fx) * z)
    np.add.at(counts, xi, 1 - fx)
    m = xi < nx - 1
    np.add.at(sums, xi[m] + 1, (fx * z)[m])
    np.add.at(counts, xi[m] + 1, fx[m])
    return _finalize(sums, counts, min_samples)


def bilinear(x, y, z, x_axis, y_axis, min_samples: float) -> tuple[np.ndarray, np.ndarray]:
    """2D splat. Returns (map[ny, nx], counts[ny, nx]).

    ``x`` runs along columns and ``y`` along rows, matching the MATLAB
    convention where the y axis is usually RPM.
    """
    x, y, z = _clean(x, y, z)
    x_axis = np.asarray(x_axis, dtype=float).ravel()
    y_axis = np.asarray(y_axis, dtype=float).ravel()
    nx, ny = x_axis.size, y_axis.size
    xi, fx = locate(x, x_axis)
    yi, fy = locate(y, y_axis)
    sums = np.zeros((ny, nx))
    counts = np.zeros((ny, nx))

    def add(rows, cols, w, mask):
        np.add.at(sums, (rows[mask], cols[mask]), (w * z)[mask])
        np.add.at(counts, (rows[mask], cols[mask]), w[mask])

    everything = np.ones(x.size, dtype=bool)
    add(yi, xi, (1 - fy) * (1 - fx), everything)
    add(yi + 1, xi, fy * (1 - fx), yi < ny - 1)
    add(yi, xi + 1, (1 - fy) * fx, xi < nx - 1)
    add(yi + 1, xi + 1, fy * fx, (yi < ny - 1) & (xi < nx - 1))
    return _finalize(sums, counts, min_samples)


def trilinear(x, y, z, v, x_axis, y_axis, z_axis, min_samples: float) -> tuple[np.ndarray, np.ndarray]:
    """3D splat of value ``v`` onto (y, x, z) cells. Returns (map[ny, nx, nz], counts)."""
    x, y, z, v = _clean(x, y, z, v)
    x_axis = np.asarray(x_axis, dtype=float).ravel()
    y_axis = np.asarray(y_axis, dtype=float).ravel()
    z_axis = np.asarray(z_axis, dtype=float).ravel()
    nx, ny, nz = x_axis.size, y_axis.size, z_axis.size
    xi, fx = locate(x, x_axis)
    yi, fy = locate(y, y_axis)
    zi, fz = locate(z, z_axis)
    sums = np.zeros((ny, nx, nz))
    counts = np.zeros((ny, nx, nz))

    def add(rows, cols, depths, w, mask):
        np.add.at(sums, (rows[mask], cols[mask], depths[mask]), (w * v)[mask])
        np.add.at(counts, (rows[mask], cols[mask], depths[mask]), w[mask])

    mx, my, mz = xi < nx - 1, yi < ny - 1, zi < nz - 1
    everything = np.ones(x.size, dtype=bool)
    add(yi, xi, zi, (1 - fx) * (1 - fy) * (1 - fz), everything)
    add(yi, xi + 1, zi, fx * (1 - fy) * (1 - fz), mx)
    add(yi + 1, xi, zi, (1 - fx) * fy * (1 - fz), my)
    add(yi + 1, xi + 1, zi, fx * fy * (1 - fz), mx & my)
    add(yi, xi, zi + 1, (1 - fx) * (1 - fy) * fz, mz)
    add(yi, xi + 1, zi + 1, fx * (1 - fy) * fz, mx & mz)
    add(yi + 1, xi, zi + 1, (1 - fx) * fy * fz, my & mz)
    add(yi + 1, xi + 1, zi + 1, fx * fy * fz, mx & my & mz)
    return _finalize(sums, counts, min_samples)
