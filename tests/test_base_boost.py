"""ME7.6.2 base boost: DPLPU / DPLPUR from the 0 % duty pull, and boost maps measured above plgru."""

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.core.logs import SplitLogs
from motronic_autotuner.families.bosch_me762 import BOSCH_ME762, DEFAULT_VARS, kfldimx_axis
from motronic_autotuner.generators.base_boost import ambient_per_row, fit_on_breakpoints, generate_base_boost_maps
from motronic_autotuner.generators.boost import generate_boost_maps

V = DEFAULT_VARS
PU = 985.0
DPLPU_AXIS = np.array([1000, 2320, 4000, 6400.0])
DPLPU_FILE = np.array([150, 610, 560, 370.0])
LEVELS = (0.0, 40.0, 60.0, 80.0)


def spring(rpm):
    """What the turbo makes above pu on the spring: piecewise linear on the DPLPU axis."""
    return np.interp(rpm, DPLPU_AXIS, [80.0, 380.0, 570.0, 410.0])


def astra_like(n_per_level=2500, seed=11):
    """Forced-duty WOT pulls with the ECU's plgru_w = pu + the file's DPLPU and a
    target plsol_w; boost = pu + spring + 9 hPa per duty percent above 30 %."""
    rng = np.random.default_rng(seed)
    frames = []
    for duty in LEVELS:
        rpm = rng.uniform(1200, 6300, n_per_level)
        boost = PU + spring(rpm) + 9.0 * np.clip(duty - 30, 0, None) + rng.normal(0, 3, n_per_level)
        frames.append(pd.DataFrame({
            V["rpm"]: rpm, V["wgdc"]: np.full(n_per_level, duty), V["boost"]: boost,
            V["plgru"]: PU + np.interp(rpm, DPLPU_AXIS, DPLPU_FILE), V["boost_target"]: np.full(n_per_level, 2180.0),
            V["pedal"]: np.full(n_per_level, 100.0)}))
    return pd.concat(frames, ignore_index=True)


def test_fit_on_breakpoints_finds_the_curve_the_ecu_would_interpolate():
    rng = np.random.default_rng(1)
    x = rng.uniform(900, 6500, 3000)
    values, weights = fit_on_breakpoints(x, spring(x), DPLPU_AXIS)
    assert values == pytest.approx([80, 380, 570, 410], abs=1.0)
    assert (weights > 0).all()
    values, _ = fit_on_breakpoints(x[x < 4000], spring(x[x < 4000]), DPLPU_AXIS, min_weight=1.0)
    assert values[:3] == pytest.approx([80, 380, 570], abs=1.0) and values[3] == pytest.approx(570, abs=1.0)


def test_pu_comes_from_plgru_minus_the_file_dplpu():
    data = astra_like()
    pu, from_logs = ambient_per_row(data, V, DPLPU_AXIS, DPLPU_FILE, fallback=1000.0)
    assert from_logs and pu == pytest.approx(PU)
    pu, from_logs = ambient_per_row(data.drop(columns=[V["plgru"]]), V, DPLPU_AXIS, DPLPU_FILE, fallback=1000.0)
    assert not from_logs and (pu == 1000.0).all()


def test_dplpu_and_dplpur_from_the_zero_duty_pull():
    data = astra_like()
    messages = []
    maps = generate_base_boost_maps(data, V, curves={"DPLPU": (DPLPU_AXIS, DPLPU_FILE),
                                                     "DPLPUR": (DPLPU_AXIS, DPLPU_FILE)},
                                    ambient_pressure=1000.0, messages=messages)
    by = {m.key: m for m in maps}
    assert np.ravel(by["dplpu"].values).tolist() == [80, 380, 570, 410]     # 10 hPa steps, as stored
    assert np.ravel(by["dplpur"].values).tolist() == [80, 380, 570, 410]
    assert "median 985 hPa" in messages[0] and "+610 -> +380" in messages[0]
    with pytest.raises(ValueError, match="0 % duty"):
        generate_base_boost_maps(data[data[V["wgdc"]] > 0], V, curves={"DPLPU": (DPLPU_AXIS, DPLPU_FILE)},
                                 ambient_pressure=1000.0)


def test_reference_column_measures_the_boost_from_it_and_keeps_the_spool_on_ambient():
    data = astra_like()
    data["ref"] = PU + spring(data[V["rpm"]])
    axis_rpm = np.array([1500, 2500, 3500, 4500, 5500, 6300.0])
    common = dict(cwldimx=False, ambient_pressure=PU, min_samples=1, fill_missing=False, axis_rpm=axis_rpm,
                  axis_boost=np.array([0.0, 450.0]), axis_kfldrl_x=np.array([0, 25, 50, 75, 100.0]), method="rows")
    messages = []
    k = next(m for m in generate_boost_maps(data, V, finish=True, reference_column="ref",
                                            reference_label="Target above base boost plgru (hPa)",
                                            messages=messages, **common) if m.key == "kfldrl")
    assert k.secondary_x_label == "Target above base boost plgru (hPa)"
    r = list(axis_rpm).index(4500)
    # above the spring: 40 % -> +90, 60 % -> +270, 80 % -> +450 hPa; the 225 hPa column is 55 %
    assert k.values[r, 2] == pytest.approx(55.0, abs=1.0) and k.values[r, 0] == 0.0
    finish = next(m for m in messages if m.startswith("KFLDRL finish"))
    assert "spooled from 3500 rpm" in finish                  # judged on the boost above ambient, not above ref


def test_kfldimx_axis_runs_from_zero_to_the_highest_target_above_base():
    axis = kfldimx_axis(np.array([600.0, 700.0, 760.0, np.nan]), 8)
    assert axis[0] == 0 and axis[-1] == 800 and axis.size == 8 and (np.diff(axis) > 0).all()
    assert kfldimx_axis(np.array([np.nan]), 8) is None


def test_me762_run_all_moves_plgru_to_the_new_dplpu():
    p = BOSCH_ME762.default_preset()
    p.axes.update({"rpm_boost": np.array([1500, 2500, 3500, 4500, 5500, 6300.0]), "boost": np.linspace(0, 1000, 8),
                   "kfldrl_x": np.array([0, 25, 50, 75, 100.0]), "rpm_dplpu": DPLPU_AXIS, "row_dplpu": np.array([0.0]),
                   "rpm_dplpur": DPLPU_AXIS, "row_dplpur": np.array([0.0])})
    p.base_maps["base_dplpu"] = DPLPU_FILE[None, :]
    p.base_maps["base_dplpur"] = DPLPU_FILE[None, :]
    data = astra_like()
    res = BOSCH_ME762.run_all(p, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data))
    assert np.ravel(res.map("dplpu").values).tolist() == [80, 380, 570, 410]
    axis = res.map("boost_axis_kfldimx")
    assert axis is not None and np.ravel(axis.values)[0] == 0
    # target 2180 sits at 2180 - (985 + 570) = 625 hPa above the new base boost at 4000 rpm
    assert np.ravel(axis.values)[-1] >= 650
    assert any("moved to the new DPLPU" in m for m in res.messages)
    k = res.map("kfldrl")
    assert k.secondary_x_label.startswith("Target above base boost")
    assert np.asarray(res.map("kfldimx").x_axis).tolist() == np.ravel(axis.values).tolist()


def test_me762_settings_measure_boost_from_plgru_by_default():
    keys = {p.key: p for p in BOSCH_ME762.params}
    assert keys["boost_reference"].default == "plgru" and "cwldimx" not in keys
    assert keys["auto_axis_kfldimx"].default is True
    names = [t.winols_name for t in BOSCH_ME762.target_maps]
    assert "DPLPU" in names and "DPLPUR" in names
    assert [g.key for g in BOSCH_ME762.generators][:2] == ["base_boost", "boost"]
