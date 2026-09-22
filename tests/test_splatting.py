"""The vectorised splats must match a literal port of the MATLAB loops."""

import numpy as np
import pytest

from motronic_autotuner.core.splatting import bilinear, linear_1d, locate, trilinear


def ref_locate(val, axis):
    n = len(axis)
    if val <= axis[0]:
        return 0, 0.0
    if val >= axis[-1]:
        return n - 1, 0.0
    for i in range(n - 1):
        if axis[i] <= val < axis[i + 1]:
            return i, (val - axis[i]) / (axis[i + 1] - axis[i])
    raise AssertionError


def ref_bilinear(x, y, z, xa, ya, ms):
    nx, ny = len(xa), len(ya)
    s = np.zeros((ny, nx))
    c = np.zeros((ny, nx))
    for xv, yv, zv in zip(x, y, z):
        if np.isnan(xv) or np.isnan(yv) or np.isnan(zv):
            continue
        xi, fx = ref_locate(xv, xa)
        yi, fy = ref_locate(yv, ya)
        w00, w10, w01, w11 = (1 - fy) * (1 - fx), fy * (1 - fx), (1 - fy) * fx, fy * fx
        s[yi, xi] += w00 * zv; c[yi, xi] += w00
        if yi < ny - 1:
            s[yi + 1, xi] += w10 * zv; c[yi + 1, xi] += w10
        if xi < nx - 1:
            s[yi, xi + 1] += w01 * zv; c[yi, xi + 1] += w01
        if yi < ny - 1 and xi < nx - 1:
            s[yi + 1, xi + 1] += w11 * zv; c[yi + 1, xi + 1] += w11
    out = np.full((ny, nx), np.nan)
    for r in range(ny):
        for k in range(nx):
            if c[r, k] >= ms:
                out[r, k] = s[r, k] / c[r, k]
    return out, c


def test_locate_edges():
    axis = np.array([1000.0, 2000.0, 3000.0])
    idx, frac = locate([500, 1000, 1500, 2000, 3000, 4000], axis)
    assert idx.tolist() == [0, 0, 0, 1, 2, 2]
    assert frac.tolist() == [0.0, 0.0, 0.5, 0.0, 0.0, 0.0]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_bilinear_matches_reference(seed):
    rng = np.random.default_rng(seed)
    xa = np.array([0, 10, 20, 35, 50, 80], dtype=float)
    ya = np.array([1000, 1500, 2000, 3000, 4000], dtype=float)
    n = 400
    x = rng.uniform(-5, 90, n)
    y = rng.uniform(800, 4500, n)
    z = rng.normal(50, 10, n)
    x[::37] = np.nan
    got, gc = bilinear(x, y, z, xa, ya, 1.5)
    exp, ec = ref_bilinear(x, y, z, xa, ya, 1.5)
    np.testing.assert_allclose(gc, ec, rtol=1e-12)
    np.testing.assert_allclose(got, exp, rtol=1e-12, equal_nan=True)


def test_linear_1d_matches_reference():
    xa = np.array([-30, 0, 20, 40, 60, 80, 100], dtype=float)
    x = np.array([-40, -30, -10, 10, 20, 30, 70, 100, 150], dtype=float)
    z = np.arange(len(x), dtype=float)
    got, counts = linear_1d(x, z, xa, 0.5)
    # reference via the 2D port with a one-row y axis
    exp, ec = ref_bilinear(x, np.zeros_like(x), z, xa, np.array([0.0]), 0.5)
    np.testing.assert_allclose(got, exp[0], equal_nan=True)
    np.testing.assert_allclose(counts, ec[0])


def test_min_samples_leaves_nan():
    out, counts = bilinear([5.0], [1500.0], [42.0], [0, 10], [1000, 2000], 0.9)
    assert np.isnan(out).all()  # each of the four cells got weight 0.25
    assert counts.sum() == pytest.approx(1.0)


def test_trilinear_shape_and_mass():
    rng = np.random.default_rng(3)
    n = 200
    x, y, z = rng.uniform(0, 10, n), rng.uniform(0, 10, n), rng.uniform(0, 10, n)
    v = np.ones(n)
    out, counts = trilinear(x, y, z, v, [0, 5, 10], [0, 10], [0, 2, 4, 6, 8, 10], 0)
    assert out.shape == (2, 3, 6)
    assert counts.sum() == pytest.approx(n)
    assert np.nanmax(out) == pytest.approx(1.0)
