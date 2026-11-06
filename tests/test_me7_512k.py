"""The 512 kB ME7.5 layout (06A906032S, SW 352760): LDRQ0DY / LDRQ1DY curves in place of
KFLDRQ0 / KFLDRQ1, KFLDRQ2 on an rpm axis of its own, URLNM / PRGNM curves in place of
KFURL / KFPRG, a placeholder KFPBRK and a KFKHFM that reads 0."""

import numpy as np
import pandas as pd

from motronic_autotuner.core.logs import SplitLogs
from motronic_autotuner.families.base import GeneratorSpec
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7, DEFAULT_VARS as V, real_points
from motronic_autotuner.generators.boost_pid import rom_step, snap_axis
from motronic_autotuner.generators.maf_check import generate_maf_check
from test_generators import AXIS_RPM, forced_duty_log, synthetic_log
from test_maf_check import LOAD, RPM, wot_log

PID_RPM = np.array([1000, 1240, 1520, 1760, 2000, 2240, 2520, 2760, 3000, 3520, 4000, 4520, 5000, 5520, 6000, 6520.0])
Q2_RPM = np.array([1000, 1720, 2000, 2520, 3520, 5000, 5520, 6520.0])
NM_RPM = np.r_[[700, 1000, 1520, 2000, 2520, 3000, 3520, 4000, 5000, 6000.0], 6000 + np.arange(1, 21.0)]


def test_the_pid_axis_snaps_to_the_byte_steps_of_the_file():
    assert rom_step(PID_RPM) == 40.0
    assert rom_step(np.array([1000, 1500, 2000.0])) is None             # multiples of 50: no evidence of a byte axis
    assert rom_step(np.array([1000, 1250, 1500.0])) is None
    snapped = snap_axis(AXIS_RPM, 40.0)
    assert np.all(snapped % 40 == 0) and np.all(np.diff(snapped) > 0) and np.all(np.abs(snapped - AXIS_RPM) <= 20)
    assert snap_axis(np.array([1000, 1010, 1020.0]), 40.0).tolist() == [1000, 1010, 1020]  # would not rise: kept


def test_readiness_takes_either_layout():
    spec = GeneratorSpec("x", "x", (), ("a", ("b", "c")), lambda ctx: [])
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"a": np.array([1.0])}
    assert spec.readiness(preset, SplitLogs(*(pd.DataFrame(),) * 4)) == "Missing axes in preset: b or c"
    preset.axes["c"] = np.array([1.0])
    assert spec.readiness(preset, SplitLogs(*(pd.DataFrame(),) * 4)) is None


def pid_512k_preset():
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"rpm_boost": AXIS_RPM, "boost": np.array([250, 500, 750, 1000, 1250.0]),
                   "kfldrl_x": np.arange(0, 100, 10.0), "rpm_kfldrq2": Q2_RPM, "x_kfldrq2": np.array([100, 200, 400, 700.0])}
    preset.base_maps = {"base_kfldrq2": np.tile(np.linspace(28, 18, Q2_RPM.size)[:, None], (1, 4))}
    for name, values in (("ldrq0dy", np.linspace(75, 19, 16)), ("ldrq1dy", np.linspace(0.5, 9.8, 16)),
                         ("ldrq1st", np.linspace(0.85, 0.3, 16))):
        preset.axes[f"rpm_{name}"], preset.axes[f"row_{name}"] = PID_RPM, np.array([0.0])
        preset.base_maps[f"base_{name}"] = values[None, :]
    return preset


def test_pid_on_the_512k_layout():
    preset = pid_512k_preset()
    data = forced_duty_log()
    result = BOSCH_ME7.run_all(preset, SplitLogs(full=data, wot=data, warmup=pd.DataFrame(), hot=data))
    assert not any(r.status.startswith("Skipped") for r in result.rows if r.name.startswith("Boost PID"))
    axis = result.map("rpm_axis_ldrq").values
    assert np.all(np.asarray(axis) % 40 == 0) and "LDRQ0DY / LDRQ1DY / LDRQ1ST" in result.map("rpm_axis_ldrq").title
    p = result.map("ldrq0dy_corrected")
    assert p.y_axis == ["LDRQ0DY"] and np.asarray(p.x_axis).tolist() == list(axis)
    np.testing.assert_allclose(np.asarray(p.values)[np.asarray(axis) >= 4000], 5.0, rtol=0.05)
    i = result.map("ldrq1dy_corrected")
    np.testing.assert_allclose(i.values, np.interp(axis, PID_RPM, np.linspace(0.5, 9.8, 16)))
    q2 = result.map("kfldrq2_corrected")                                 # its own 8-point axis, untouched
    assert q2.y_axis.tolist() == Q2_RPM.tolist() and "own rpm axis" in q2.title
    np.testing.assert_allclose(q2.values, preset.base_maps["base_kfldrq2"])
    assert any("rounded to them" in m for m in result.messages)
    assert any("LDRQ0S" in m for m in result.messages)
    assert not any("KFLDRQ0 not imported" in m for m in result.messages)


def test_pid_ratio_mode_scales_the_curves_and_the_own_axis_map():
    preset = pid_512k_preset()
    preset.params["ldr_mode"] = "overall"
    data = forced_duty_log(n=20000)
    logs = SplitLogs(full=data, wot=data, warmup=pd.DataFrame(), hot=data)
    first = BOSCH_ME7.run_all(preset, logs)
    preset.base_maps["base_kfldrl"] = np.nan_to_num(first.map("kfldrl").values * 4.0, nan=50.0)
    result = BOSCH_ME7.run_all(preset, logs)
    assert any("the logs need 0.25" in m for m in result.messages)
    np.testing.assert_allclose(result.map("kfldrq2_corrected").values, preset.base_maps["base_kfldrq2"] * 0.25, rtol=0.03)
    axis = result.map("rpm_axis_ldrq").values
    np.testing.assert_allclose(result.map("ldrq0dy_corrected").values,
                               np.interp(axis, PID_RPM, np.linspace(75, 19, 16)) * 0.25, rtol=0.03)
    assert any("multiply it by 0.25" in m for m in result.messages)


def manifold_512k_preset():
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"rpm_urlnm": NM_RPM, "row_urlnm": np.array([0.0]), "rpm_prgnm": NM_RPM * 0.4,
                   "row_prgnm": np.array([0.0]), "rpm_pbrk": np.arange(0, 10000, 1000.0),
                   "load_pbrk": np.arange(10) * 93.75}
    preset.base_maps = {"base_urlnm": np.full((1, 30), 0.0919), "base_prgnm": np.full((1, 30), 95.0),
                        "base_kfpbrk": np.ones((10, 10))}
    return preset


def test_padding_after_the_real_points():
    assert real_points(NM_RPM) == 10
    assert real_points(np.array([1000, 2000, 3000.0])) == 3


def test_manifold_model_on_urlnm_and_prgnm():
    preset = manifold_512k_preset()
    data = synthetic_log(6000, temp=95.0)                                 # load = 0.08 * (ps - 50)
    result = BOSCH_ME7.run_all(preset, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data))
    assert not any(r.status.startswith("Skipped") for r in result.rows if r.name.startswith("Intake Manifold"))
    url, prg = result.map("urlnm"), result.map("prgnm")
    assert url.y_axis == ["URLNM"] and np.asarray(url.x_axis).tolist() == NM_RPM.tolist()
    np.testing.assert_allclose(np.asarray(url.values)[1:10], 0.08, rtol=0.03)
    assert np.asarray(url.values)[0] == 0.0919                            # 700 rpm: no rows there, the file's value
    assert (np.asarray(url.values)[10:] == np.asarray(url.values)[9]).all()   # padding holds the last real point
    np.testing.assert_allclose(np.asarray(prg.values)[1:10], 50.0, atol=6.0)
    assert np.asarray(prg.x_axis).tolist() == (NM_RPM * 0.4).tolist()       # the export's own (mis-scaled) axis
    assert any("x 0.40 of URLNM's rpm axis" in m for m in result.messages)
    assert any("unused default" in m for m in result.messages)
    assert result.map("kfpbrk_corrected") is not None

    preset.prep["hack_5120"] = True
    doubled = BOSCH_ME7.run_all(preset, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data))
    np.testing.assert_allclose(doubled.map("urlnm").values, np.asarray(url.values) * 2)
    assert any(r.name == "5120 Patch" and "URLNM*2" in r.size for r in doubled.rows)


def test_a_kfkhfm_of_zeros_gives_no_information_block():
    msgs = []
    maps = {m.key: m for m in generate_maf_check(wot_log(), V, axis_rpm=RPM, axis_load=LOAD,
                                                   base_map=np.zeros((RPM.size, LOAD.size)), min_samples=5,
                                                   messages=msgs)}
    assert "kfkhfm_info" not in maps and "maf_error" in maps
    assert any("KFKHFM is 0 in every cell" in m for m in msgs)
