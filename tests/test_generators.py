"""Smoke and property tests for the ME7 generators on synthetic logs."""

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.core.logs import SplitLogs
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7, DEFAULT_VARS
from motronic_autotuner.generators.boost import generate_boost_maps
from motronic_autotuner.generators.handover import generate_kfvpdksd, generate_handover_maps
from motronic_autotuner.generators.ignition import generate_kfzw
from motronic_autotuner.generators.manifold import generate_manifold_maps, generate_pbrk_maps
from motronic_autotuner.generators.warmup import generate_warmup_maps

V = DEFAULT_VARS


def synthetic_log(n=3000, seed=0, temp=95.0):
    rng = np.random.default_rng(seed)
    rpm = rng.uniform(1000, 6500, n)
    ps = rng.uniform(300, 2200, n)
    load = 0.08 * (ps - 50) + rng.normal(0, 0.5, n)  # KFURL 0.08, KFPRG 50
    return pd.DataFrame({
        V["rpm"]: rpm,
        V["load"]: load,
        V["pedal"]: rng.uniform(80, 100, n),
        V["boost"]: ps + 50,
        V["ps_w"]: ps,
        V["wgdc"]: np.clip((ps - 1000) / 12, 0, 95),
        V["vvt"]: rng.choice([0.0, 22.0], n),
        V["inj"]: rng.uniform(1, 15, n),
        V["stft"]: rng.normal(1.03, 0.01, n),
        V["ltft"]: np.ones(n),
        V["tmot"]: np.full(n, temp) if temp is not None else rng.uniform(20, 100, n),
        V["pu"]: np.full(n, 1000.0),
        V["knock"]: rng.uniform(0, 3, n),
        V["time"]: np.arange(n) * 0.1,
    })


AXIS_RPM = np.array([1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500], dtype=float)


def test_boost_maps():
    data = synthetic_log()
    axis_boost = np.array([250, 500, 750, 1000, 1200], dtype=float)
    kfldrl_x = np.arange(0, 100, 10, dtype=float)
    maps = generate_boost_maps(data, V, cwldimx=True, ambient_pressure=1000, min_samples=1, fill_missing=True,
                               axis_rpm=AXIS_RPM, axis_boost=axis_boost, axis_kfldrl_x=kfldrl_x)
    by = {m.key: m for m in maps}
    np.testing.assert_allclose(by["kfldimx"].values[0], [0, 26.315789, 52.631579, 78.947368, 100], rtol=1e-6)
    kfldrl = by["kfldrl"].values
    assert kfldrl.shape == (12, 10)
    assert np.nanmax(kfldrl) <= 95 and np.nanmin(kfldrl) >= 0
    assert not np.isnan(kfldrl).any()  # fill_missing filled every cell
    assert by["kfldrl"].secondary_x is not None
    assert by["abs_wgdc"].x_axis.tolist() == (axis_boost + 1000).tolist()


def test_kfvpdksd_is_binary_then_smoothed():
    axis_rpm = np.array([1000, 2000, 3000, 4000], dtype=float)
    pratio = np.array([1.2, 1.5, 1.8, 2.1])
    curve = np.array([1400, np.nan, 1900, 2200], dtype=float)  # base boost mbar, one gap
    m = generate_kfvpdksd(curve, axis_rpm, pratio, 1000)
    assert m.shape == (4, 4)
    assert not np.isnan(m).any()
    assert 0.95 <= m.min() and m.max() <= 1.0
    # low base ratio at 1000 rpm (1.4): rows above 1.4 stay fully open
    assert m[3, 0] == pytest.approx(1.0)


def test_handover_maps_shapes():
    data = synthetic_log()
    pratio = np.array([1.4, 1.6, 1.8, 2.0, 2.2])
    maps = generate_handover_maps(data, V, min_samples_base_wg=1, ambient_pressure=1000,
                                  axis_rpm=AXIS_RPM, axis_pratio=pratio)
    by = {m.key: m for m in maps}
    assert by["base_press"].values.shape == (12,)
    assert by["base_press"].y_axis == ["Base Boost"]
    assert by["kfvp"].values.shape == (5, 12)


def test_warmup_maps():
    full = synthetic_log(temp=None, seed=1)
    warm = full[full[V["tmot"]] < 80]
    axis_tmot = np.array([-30, 0, 20, 40, 60, 80, 100], dtype=float)
    axis_load = np.array([10, 40, 80, 120, 160, 200], dtype=float)
    msgs = []
    maps = generate_warmup_maps(warm, full, V, min_samples=1, trim_format="lambda", axis_tmot=axis_tmot,
                                axis_load=axis_load, axis_rpm=AXIS_RPM, messages=msgs)
    by = {m.key: m for m in maps}
    kffwl = by["kffwl"].values
    assert kffwl.shape == (7,)
    hot_cells = kffwl[axis_tmot >= 80]
    assert (hot_cells[~np.isnan(hot_cells)] == 0.0).all() and not np.isnan(hot_cells[0])
    assert by["kffwlw"].values.shape == (12, 6)
    assert by["fkkvs_rl"].values.shape == (12, 6)
    assert msgs == []


def test_kfzw_splits_on_vvt():
    data = synthetic_log()
    axis_load = np.array([20, 60, 100, 140, 180], dtype=float)
    maps = generate_kfzw(data, V, min_samples=1, axis_rpm=AXIS_RPM, axis_load=axis_load, vvt_split=18)
    assert [m.key for m in maps] == ["kfzw", "kfzw2"]
    assert not np.isnan(maps[0].values).any()
    no_vvt = data.drop(columns=[V["vvt"]])
    assert [m.key for m in generate_kfzw(no_vvt, V, min_samples=1, axis_rpm=AXIS_RPM, axis_load=axis_load)] == ["kfzw"]


def test_manifold_recovers_slope_and_intercept():
    data = synthetic_log(n=20000, seed=2)
    msgs = []
    maps = generate_manifold_maps(data, V, min_samples=5, vvt_enabled=True, vvt_threshold=18,
                                  axis_rpm=AXIS_RPM, messages=msgs)
    by = {m.key: m for m in maps}
    assert by["kfurl"].values.shape == (12, 2)
    assert by["kfurl"].x_axis.tolist() == [0.0, 18.0]
    np.testing.assert_allclose(by["kfurl"].values, 0.08, rtol=0.05)
    np.testing.assert_allclose(by["kfprg"].values, 50, atol=10)
    assert not any("REJECTED" in m for m in msgs)


def test_family_run_all_with_missing_axes_reports_skips():
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"rpm_boost": AXIS_RPM, "boost": np.array([250, 500, 750.0]), "kfldrl_x": np.arange(0, 100, 10.0)}
    data = synthetic_log()
    logs = SplitLogs(full=data, wot=data, warmup=pd.DataFrame(), hot=data)
    result = BOSCH_ME7.run_all(preset, logs)
    keys = [m.key for m in result.maps]
    assert keys == ["kfldimx", "kfldrl", "abs_wgdc"]
    skipped = [r for r in result.rows if r.status.startswith("Skipped")]
    assert len(skipped) == 5
    assert all("Missing axes" in r.status for r in skipped)
    # with axes present but no warmup rows, the subset check reports instead
    preset.axes.update({"rpm_kffwlw": AXIS_RPM, "load_kffwlw": np.array([10.0, 100.0]), "tmot": np.array([0.0, 80.0])})
    result = BOSCH_ME7.run_all(preset, logs)
    assert any("No WARMUP" in r.status for r in result.rows)


def test_5120_post_process_scales_manifold_maps():
    preset = BOSCH_ME7.default_preset()
    preset.prep["hack_5120"] = True
    preset.axes = {"rpm_url": AXIS_RPM}
    data = synthetic_log(n=20000)
    logs = SplitLogs(full=data, wot=data, warmup=data, hot=data)
    result = BOSCH_ME7.run_all(preset, logs)
    assert result.map("kfurl") is not None
    np.testing.assert_allclose(np.nanmean(result.map("kfurl").values), 0.16, rtol=0.05)
    assert any(r.name == "5120 Patch" for r in result.rows)


def test_near_gear_change_blanks_both_sides():
    from motronic_autotuner.generators import near_gear_change
    t = np.arange(20) * 0.1
    gear = np.r_[np.full(10, 3.0), np.full(10, 4.0)]      # change at row 10, t = 1.0
    near = near_gear_change(gear, t, 0.25)
    assert near.tolist() == [i in (8, 9, 10, 11, 12) for i in range(20)]
    assert not near_gear_change(gear, t, 0.0).any()


AXIS_LOAD_PBRK = np.array([50, 60, 65, 70, 75, 80, 90, 100, 120, 140.0])
AXIS_RPM_PBRK = np.array([1000, 1520, 2000, 2520, 3000, 3520, 4500, 6000, 6500.0])


def nonlinear_log(n=40000, seed=5, vvt_on=False):
    """The line holds up to 1300 hPa; above it the chamber sees 0.95 of the manifold
    pressure, so the load bends: rl = 0.08 * (ps * f - 50)."""
    rng = np.random.default_rng(seed + 100)        # not the stream synthetic_log drew rpm from
    d = synthetic_log(n, seed)
    ps = rng.uniform(300, 2200, n)
    f_true = np.where(ps > 1300, 0.95, 1.0)
    d[V["ps_w"]] = ps
    d[V["load"]] = 0.08 * (ps * f_true - 50) + rng.normal(0, 0.3, n)
    d[V["vvt"]] = rng.choice([0.0, 22.0], n) if vvt_on else 0.0
    return d


def fit_and_correct(data, *, vvt_enabled=False, fit_load_max=90.0, apply_to="pressure", nw=False):
    msgs = []
    fit = generate_manifold_maps(data, V, min_samples=5, vvt_enabled=vvt_enabled, vvt_threshold=18,
                                 axis_rpm=AXIS_RPM, fit_load_max=fit_load_max, messages=msgs)
    by = {m.key: m for m in fit}
    maps = generate_pbrk_maps(data, V, kfurl=by["kfurl"].values, kfprg=by["kfprg"].values, axis_rpm_fit=AXIS_RPM,
                              vvt_enabled=vvt_enabled, vvt_threshold=18, axis_rpm=AXIS_RPM_PBRK, axis_load=AXIS_LOAD_PBRK,
                              base_map=np.ones((AXIS_RPM_PBRK.size, AXIS_LOAD_PBRK.size)),
                              axis_rpm_nw=AXIS_RPM_PBRK if nw else None, axis_load_nw=AXIS_LOAD_PBRK if nw else None,
                              base_map_nw=None, min_samples=3, apply_to=apply_to, messages=msgs)
    return by, {m.key: m for m in maps}, msgs


def test_pbrk_factor_recovers_the_bend():
    by, out, msgs = fit_and_correct(nonlinear_log())
    # the line fitted below 90 % load is the true one
    np.testing.assert_allclose(by["kfurl"].values[:, 0], 0.08, rtol=0.03)
    np.testing.assert_allclose(by["kfprg"].values[:, 0], 50, atol=15)
    f = out["kfpbrk"].values                                   # rows = rpm, cols = load
    low = f[:, AXIS_LOAD_PBRK <= 80]
    high = f[:, AXIS_LOAD_PBRK >= 120]
    np.testing.assert_allclose(low[~np.isnan(low)], 1.0, atol=0.01)
    np.testing.assert_allclose(high[~np.isnan(high)], 0.95, atol=0.01)
    assert out["kfpbrk"].counts is not None and out["kfpbrk"].x_axis.tolist() == AXIS_LOAD_PBRK.tolist()
    # the paste-ready map keeps the factory value (1.0) where there is no data, and the check improves
    corrected = out["kfpbrk_corrected"].values
    assert not np.isnan(corrected).any() and (corrected[np.isnan(f)] == 1.0).all()
    check = out["pbrk_check"].values
    assert out["pbrk_check"].y_axis == ["VVT OFF: before KFPBRK (hPa RMS)", "VVT OFF: after KFPBRK (hPa RMS)"]
    ok = ~np.isnan(check[0])
    assert (check[1][ok] < check[0][ok]).all() and check[0][ok].max() > 20
    assert "kfpbrknw" not in out and any("KFPBRK: " in m and "cells from" in m for m in msgs)


def test_pbrk_load_mode_and_the_vvt_on_map():
    data = nonlinear_log(vvt_on=True)
    by, out, msgs = fit_and_correct(data, vvt_enabled=True, apply_to="load", nw=True)
    assert by["kfurl"].values.shape == (12, 2)
    for key in ("kfpbrk", "kfpbrknw"):
        f = out[key].values
        high = f[:, AXIS_LOAD_PBRK >= 120]
        # on the load the same bend reads as a factor below one as well, a little further from 0.95
        assert np.nanmean(high) < 0.97 and np.nanmean(f[:, AXIS_LOAD_PBRK <= 80]) > 0.99
    assert out["pbrk_check"].values.shape == (4, 12)
    # without the NW axes the VVT-on rows are skipped with a message
    _, out2, msgs2 = fit_and_correct(data, vvt_enabled=True, nw=False)
    assert "kfpbrknw" not in out2 and any("KFPBRKNW: axes not imported" in m for m in msgs2)


def test_fit_load_max_falls_back_when_a_bin_has_no_low_loads():
    data = nonlinear_log()
    data = data[~((data[V["rpm"]] > 6250) & (data[V["load"]] <= 90))]
    msgs = []
    fit = generate_manifold_maps(data, V, min_samples=5, vvt_enabled=False, vvt_threshold=18,
                                 axis_rpm=AXIS_RPM, fit_load_max=90.0, messages=msgs)
    kfurl = fit[0].values[:, 0]
    assert any("[FIT] RPM: 6500" in m and "fitted on all loads" in m for m in msgs)
    assert not np.isnan(kfurl[-1]) and kfurl[-1] < 0.08          # the bend pulls the all-loads slope down


def test_me7_run_all_adds_pbrk_when_its_axes_are_present():
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"rpm_url": AXIS_RPM}
    data = nonlinear_log(n=20000)
    logs = SplitLogs(full=data, wot=data, warmup=pd.DataFrame(), hot=data)
    result = BOSCH_ME7.run_all(preset, logs)
    assert [m.key for m in result.maps] == ["kfurl", "kfprg"]
    assert any("correction maps skipped" in m for m in result.messages)
    preset.axes.update({"rpm_pbrk": AXIS_RPM_PBRK, "load_pbrk": AXIS_LOAD_PBRK})
    preset.base_maps["base_kfpbrk"] = np.ones((AXIS_RPM_PBRK.size, AXIS_LOAD_PBRK.size))
    result = BOSCH_ME7.run_all(preset, logs)
    keys = [m.key for m in result.maps]
    assert keys == ["kfurl", "kfprg", "kfpbrk", "kfpbrk_corrected", "pbrk_check"]
    assert all(m.sheet == "Airflow" for m in result.maps)
