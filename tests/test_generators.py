"""Smoke and property tests for the ME7 generators on synthetic logs."""

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.core.logs import SplitLogs
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7, DEFAULT_VARS
from motronic_autotuner.generators.boost import detect_spool_rpm, generate_boost_maps, spool_rpm_axis
from motronic_autotuner.generators.boost_pid import duty_ratio, scale_rows
from motronic_autotuner.generators.handover import generate_kfvpdksd, generate_handover_maps, pratio_axis_from_curve
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
    assert len(skipped) == 6
    assert all("Missing axes" in r.status or "Missing base maps" in r.status for r in skipped)
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


def spool_log(n=20000, seed=7, spool=3300.0):
    """WOT rows of a turbo that holds the gate shut (95 %) until ``spool`` and
    reaches full boost there: 1200 hPa over ambient from 2500 rpm in 800 rpm."""
    rng = np.random.default_rng(seed)
    d = synthetic_log(n, seed)
    rpm = rng.uniform(1500, 6500, n)
    rel = np.clip((rpm - 2500) * 1200 / (spool - 2500), 0, 1200) + rng.normal(0, 15, n)
    d[V["rpm"]] = rpm
    d[V["boost"]] = 1000 + rel
    d[V["wgdc"]] = np.where(rpm < spool, 95.0, np.where(rpm > 5500, 5.0, 70.0))   # gate open past 5500: base-WG rows
    d[V["pedal"]] = 100.0
    return d


def test_spool_rpm_axis_layout():
    assert spool_rpm_axis(3300).tolist() == [2300, 2550, 2800, 3050, 3300, 3550, 3800, 4050, 4300, 4550,
                                             5000, 5500, 6000, 6500, 7000, 7500]
    assert spool_rpm_axis(3250).tolist()[10:] == [5000, 5500, 6000, 6500, 7000, 7500]
    assert spool_rpm_axis(3000).tolist()[-1] == 7000 and spool_rpm_axis(3000).size == 16


def test_detect_spool_rpm_from_the_wot_rows():
    d = spool_log()
    spool, info = detect_spool_rpm(d[V["rpm"]], d[V["boost"]] - 1000)
    # 90 % of 1200 over ambient is reached 80 rpm before full boost: 3300 - 0.1 * 800 = 3220
    assert 3150 <= spool <= 3300 and info["peak"] > 1100 and info["boost_at_spool"] >= info["target"]
    assert spool_rpm_axis(spool)[4] == spool
    none, info = detect_spool_rpm(d[V["rpm"]][:2], d[V["boost"]][:2])
    assert none is None


def test_pratio_axis_from_curve():
    axis = pratio_axis_from_curve(np.array([1200, 1500, np.nan, 1600.0]), 1000.0, 12)
    assert axis.size == 12 and axis[0] == 0.95 and axis[1] == 1.0 and axis[-1] == 1.92
    np.testing.assert_allclose(np.diff(axis[1:]), 0.092, atol=1e-4)
    assert pratio_axis_from_curve(np.array([np.nan]), 1000.0, 12) is None
    assert pratio_axis_from_curve(np.array([800.0]), 1000.0, 12) is None


def test_handover_auto_axis_keeps_the_stock_rows_under_1_2():
    data = synthetic_log()
    data.loc[data[V["wgdc"]] < 10, V["boost"]] = 1500.0                  # base-WG rows hold 1.5 bar absolute
    factory_axis = np.linspace(0.95, 1.5, 12)
    base = np.tile(np.linspace(0.90, 1.0, 12), (AXIS_RPM.size, 1))      # rows rpm, cols ratio: a ramp to recognise
    msgs = []
    maps = generate_handover_maps(data, V, min_samples_base_wg=1, ambient_pressure=1000, axis_rpm=AXIS_RPM,
                                  axis_pratio=factory_axis, auto_axis=True, base_map=base, base_axis_rpm=AXIS_RPM,
                                  base_axis_pratio=factory_axis, messages=msgs)
    by = {m.key: m for m in maps}
    axis = by["pratio_axis_kfvp"].values
    assert axis.size == 12 and axis[0] == 0.95 and axis[1] == 1.0 and axis[-1] == 1.8    # 1500 / 1000 x 1.2
    kfvp = by["kfvp"]
    assert kfvp.y_axis.tolist() == axis.tolist()
    under = axis < 1.2
    np.testing.assert_allclose(kfvp.values[under, 3], np.interp(axis[under], factory_axis, base[3]))
    assert np.all((kfvp.values[~under] >= 0.95) & (kfvp.values[~under] <= 1.0))
    assert any("kept at the imported values" in m for m in msgs)
    # without the tick nothing changes
    plain = {m.key: m for m in generate_handover_maps(data, V, min_samples_base_wg=1, ambient_pressure=1000,
                                                        axis_rpm=AXIS_RPM, axis_pratio=factory_axis)}
    assert "pratio_axis_kfvp" not in plain and plain["kfvp"].y_axis.tolist() == factory_axis.tolist()


def test_me7_auto_axes_land_in_the_result():
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"rpm_boost": AXIS_RPM, "boost": np.array([250, 500, 750, 1000, 1250.0]),
                   "kfldrl_x": np.arange(0, 100, 10.0), "rpm_kfvp": AXIS_RPM, "pratio_kfvp": np.linspace(0.95, 1.5, 12)}
    preset.params.update({"auto_axis_kfldrl": True, "auto_axis_kfvp": True})
    data = spool_log()
    logs = SplitLogs(full=data, wot=data, warmup=pd.DataFrame(), hot=data)
    result = BOSCH_ME7.run_all(preset, logs)
    keys = [m.key for m in result.maps]
    assert keys[:4] == ["rpm_axis_boost", "kfldimx", "kfldrl", "abs_wgdc"] and "pratio_axis_kfvp" in keys
    axis = result.map("rpm_axis_boost").values
    assert 3150 <= axis[4] <= 3300 and axis.tolist() == spool_rpm_axis(axis[4]).tolist() and axis[-1] % 500 == 0
    assert result.map("kfldrl").y_axis.tolist() == axis.tolist() == result.map("kfldimx").y_axis.tolist()
    assert any("Auto axis KFLDRL / KFLDIMX: spool at" in m for m in result.messages)


def test_duty_ratio_reads_the_sensitivity_from_kfldrl():
    axis_x = np.array([0, 25, 50, 75, 95.0])
    factory = np.array([[0, 20, 40, 60, 80.0], [0, 30, 50, 70, 90.0], [0, 10, 15, 20, 25.0]])   # rows: 3 rpm points
    new = factory * 0.25
    new[0, 1] = np.nan                                                 # one cell without data
    ratio = duty_ratio(new, AXIS_RPM[:3], axis_x, factory, AXIS_RPM[:3], axis_x, min_file_duty=20)
    np.testing.assert_allclose(ratio["per_rpm"][:2], 0.25)
    assert ratio["cells"].tolist() == [3, 4, 1]                        # file duty >= 20 and data present
    np.testing.assert_allclose(ratio["overall"], 0.25)
    # a different ratio per rpm lands per row, or as one number
    new[2] = factory[2] * 0.5
    ratio = duty_ratio(new, AXIS_RPM[:3], axis_x, factory, AXIS_RPM[:3], axis_x, min_file_duty=20)
    np.testing.assert_allclose(ratio["per_rpm"], [0.25, 0.25, 0.5])
    base = np.ones((3, 4)) * 10
    scaled, factor = scale_rows(base, AXIS_RPM[:3], ratio, "per_rpm")
    np.testing.assert_allclose(scaled[:, 0], [2.5, 2.5, 5.0])
    scaled, factor = scale_rows(base, AXIS_RPM[:3], ratio, "overall")
    assert np.allclose(scaled, 10 * ratio["overall"]) and 0.25 < ratio["overall"] < 0.5
    # a map on another rpm axis gets the per-rpm factor interpolated and clamped
    scaled, factor = scale_rows(np.ones((2, 2)), np.array([500.0, 9000.0]), ratio, "per_rpm")
    np.testing.assert_allclose(factor, [0.25, 0.5])


def test_me7_pid_scaling_follows_kfldrl():
    preset = BOSCH_ME7.default_preset()
    axis_boost = np.array([250, 500, 750, 1000, 1250.0])
    kfldrl_x = np.arange(0, 100, 10.0)
    preset.axes = {"rpm_boost": AXIS_RPM, "boost": axis_boost, "kfldrl_x": kfldrl_x,
                   "rpm_kfldrq0": np.array([1000, 3000, 6000.0]), "x_kfldrq0": np.array([100, 400.0]),
                   "rpm_kfldrapp": np.array([1000, 6000.0]), "x_kfldrapp": np.array([0, 100.0])}
    preset.base_maps = {"base_kfldrq0": np.full((3, 2), 40.0), "base_kfldrapp": np.full((2, 2), 10.0)}
    data = synthetic_log(n=20000)
    logs = SplitLogs(full=data, wot=data, warmup=pd.DataFrame(), hot=data)
    # without the file's KFLDRL the PID generator is skipped
    result = BOSCH_ME7.run_all(preset, logs)
    assert any("Boost PID" in r.name and "Missing base maps" in r.status for r in result.rows)
    # with a file whose KFLDRL asks four times the duty the logs show, the gains come down to a quarter
    kfldrl = result.map("kfldrl").values
    preset.base_maps["base_kfldrl"] = np.nan_to_num(kfldrl * 4.0, nan=50.0)
    result = BOSCH_ME7.run_all(preset, logs)
    scale = result.map("ldr_scale")
    assert scale is not None and 0.24 < float(scale.title.split("overall ")[1].rstrip(")")) < 0.26
    q0 = result.map("kfldrq0_corrected")
    np.testing.assert_allclose(q0.values, 10.0, rtol=0.05)
    assert q0.y_axis.tolist() == [1000, 3000, 6000] and result.map("kfldrapp_corrected") is not None
    assert any("Boost PID scaling: the logs need 0.25" in m for m in result.messages)
    assert any("KFLDRQ1 not imported" in m for m in result.messages)
