"""Smoke and property tests for the ME7 generators on synthetic logs."""

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.core.logs import SplitLogs
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7, DEFAULT_VARS
from motronic_autotuner.generators.boost import generate_boost_maps
from motronic_autotuner.generators.handover import generate_kfvpdksd, generate_handover_maps
from motronic_autotuner.generators.ignition import generate_kfzw
from motronic_autotuner.generators.manifold import generate_manifold_maps
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
