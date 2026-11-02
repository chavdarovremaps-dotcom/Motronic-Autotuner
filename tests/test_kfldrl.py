"""KFLDRL by rows between the logged duty levels, and the hand finishing by spool region."""

import os

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.core.logs import SplitLogs
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7, DEFAULT_VARS
from motronic_autotuner.families.bosch_me155 import BOSCH_ME155
from motronic_autotuner.generators.boost import (
    duty_level_points, finish_kfldrl, generate_boost_maps, kfldrl_by_rows, rising_points,
)

V = DEFAULT_VARS
AXIS_RPM = np.array([1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000], dtype=float)
LEVELS = (0.0, 59.765625, 69.921875, 79.6875)  # forced KFLDRAPP levels, n/256
COLUMNS = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 95], dtype=float)


def boost_at(rpm, duty):
    """Relative boost of a turbo that spools at 3000 rpm: 300 hPa on the spring,
    then 12 hPa per duty percent above 50 %, scaled by the spool."""
    spool = np.clip((rpm - 1800) / 1200, 0.15, 1.0)
    return 300 * spool + spool * 12 * np.clip(duty - 50, 0, None)


def forced_level_log(n_per_level=3000, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for duty in LEVELS:
        rpm = rng.uniform(1500, 6000, n_per_level)
        rows.append(pd.DataFrame({V["rpm"]: rpm, V["wgdc"]: np.full(n_per_level, duty),
                                  V["boost"]: 1000 + boost_at(rpm, duty) + rng.normal(0, 5, n_per_level),
                                  V["pu"]: np.full(n_per_level, 1000.0)}))
    return pd.concat(rows, ignore_index=True)


def kfldrl(data, **kw):
    maps = generate_boost_maps(data, V, cwldimx=False, ambient_pressure=1000, min_samples=1, fill_missing=False,
                               axis_rpm=AXIS_RPM, axis_boost=np.array([300.0, 1200.0]), axis_kfldrl_x=COLUMNS, **kw)
    return next(m for m in maps if m.key == "kfldrl")


def test_rows_interpolate_between_the_levels_instead_of_treads():
    data = forced_level_log()
    rows = kfldrl(data, method="rows").values
    splat = kfldrl(data, method="splat").values
    columns_boost = 300 + COLUMNS / 100 * 900
    r = int(np.flatnonzero(AXIS_RPM == 4000)[0])
    # 60 % makes 417 hPa, 70 % 539, 80 % 656 at 4000 rpm: the 480 hPa column lies between 60 and 70
    expected = np.interp(columns_boost, [boost_at(4000, d) for d in LEVELS], LEVELS,
                         left=np.nan, right=np.nan)
    inside = np.isfinite(expected)
    inside[0] = False  # 300 hPa is the 0 % level itself, inside or not by the noise
    assert np.allclose(rows[r, inside], expected[inside], atol=0.8)
    # the splat writes one level into the neighbouring columns of a level: a flat tread
    seg = splat[r][np.isfinite(splat[r])]
    assert (np.abs(np.diff(seg)) < 0.05).any()
    seg = rows[r][np.isfinite(rows[r])]
    assert (np.diff(seg) > 0.5).all()


def test_a_stray_level_is_pooled_not_hiding_the_levels_above_it():
    # 11 % logged twice while the boost still sat at 1289 hPa: the old envelope dropped every level up to 80 %
    boost = np.array([312.0, 1289.0, 317.0, 444.0, 634.0, 891.0, 1297.0])
    duty = np.array([0.0, 11.0, 15.0, 45.0, 60.0, 70.0, 80.0])
    weight = np.array([60.0, 1.5, 50.0, 37.0, 37.0, 38.0, 70.0])
    b, d, _ = rising_points(boost, duty, weight)
    assert (np.diff(b) > 0).all()
    assert d.tolist()[-4:] == [45.0, 60.0, 70.0, 80.0]
    assert b[-1] == pytest.approx(1297.0)
    # more duty, no more boost (a turbo at its limit): the lower duty is kept for the pooled boost
    b, d, _ = rising_points(np.array([844.0, 940.0, 938.0]), np.array([75.0, 80.0, 90.0]), np.array([50.0, 45.0, 51.0]))
    assert d.tolist() == [75.0, 80.0] and b[-1] == pytest.approx(938.9, abs=0.1)


def test_a_column_a_hair_above_the_top_counts_as_reached():
    b = np.array([[300.0], [939.0]])
    d = np.array([[0.0], [80.0]])
    w = np.ones_like(b)
    values, *_ = kfldrl_by_rows(b, d, w, np.array([400.0, 850.0, 940.0, 1030.0]))
    assert values[0, 2] == 80.0 and np.isnan(values[0, 3])


def test_finish_by_spool_region():
    columns = np.array([400.0, 500, 600, 700, 800])
    axis = np.array([1500.0, 2000, 2500, 3000, 3500, 4000])
    nan = np.nan
    values = np.array([
        [nan, nan, nan, nan, nan],      # no data, below the spool
        [40.0, 60.0, nan, nan, nan],    # below the spool, reached 500 hPa
        [30.0, 50.0, 70.0, nan, nan],   # just below the spool
        [20.0, 45.0, 60.0, 72.0, 78.0],  # first spooled row
        [20.0, 45.0, nan, 65.0, nan],   # spooled, a hole and a top it did not reach
        [nan, nan, nan, nan, nan],      # spooled, no data
    ])
    row_top = np.array([nan, 500.0, 610.0, 800.0, 760.0, nan])
    row_duty = np.array([nan, 75.0, 75.0, 80.0, 86.0, nan])
    messages = []
    out = finish_kfldrl(values, row_top, row_duty, columns, axis, share=90, out_of_reach=95, messages=messages)
    assert (out[:, 0] == 0).all()
    assert out[0].tolist() == [0, 95, 95, 95, 95]
    assert out[1].tolist() == [0, 60, 78, 95, 95]                  # first empty cell bridged at the spool duty
    assert out[2].tolist() == [0, 50, 70, 72, 78]                  # takes the 3000 rpm duties
    assert out[3].tolist() == [0, 45, 60, 72, 78]
    assert out[4].tolist() == pytest.approx([0, 45, 55, 65, 86])  # hole linear in boost, top at the logged ceiling
    assert out[5].tolist() == out[4].tolist()                      # no data above the spool: the row under it
    assert (np.diff(out[:, 1:], axis=1) >= 0).all()
    assert "spooled from 3000 rpm" in messages[0] and "86.0 %" in messages[0]


def test_finish_without_data_leaves_the_map_and_says_so():
    messages = []
    out = finish_kfldrl(np.full((2, 3), np.nan), np.full(2, np.nan), np.full(2, np.nan), np.array([1.0, 2, 3]),
                        np.array([1000.0, 2000]), messages=messages)
    assert (out[:, 0] == 0).all() and np.isnan(out[:, 1:]).all()
    assert "no row has data" in messages[0]


def test_finish_fills_the_rows_map_like_the_hand_finish():
    data = forced_level_log()
    messages = []
    k = kfldrl(data, method="rows", finish=True, messages=messages).values
    assert not np.isnan(k).any() and (k[:, 0] == 0).all() and k.max() <= 95
    assert (np.diff(k[:, 1:], axis=1) >= 0).all()
    assert (k[0, 1:] == 95).all()                                  # 1500 rpm: nothing reached, gate shut
    assert k[-1, 1:].max() == pytest.approx(LEVELS[-1], abs=0.01)  # above the spool never past the logged 79.7 %
    assert any(m.startswith("KFLDRL finish: spooled from") for m in messages)


def test_me7_and_opel_run_the_rows_and_the_finish_by_default():
    for family in (BOSCH_ME7, BOSCH_ME155):
        preset = family.default_preset()
        assert preset.params["kfldrl_method"] == "rows" and preset.params["kfldrl_finish"] is True
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"rpm_boost": AXIS_RPM, "boost": np.array([300.0, 1200.0]), "kfldrl_x": COLUMNS}
    data = forced_level_log()
    data[V["pedal"]] = 100.0
    result = BOSCH_ME7.run_all(preset, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data))
    k = result.map("kfldrl").values
    assert not np.isnan(k).any() and (k[:, 0] == 0).all()
    preset.params["kfldrl_finish"] = False
    preset.params["kfldrl_method"] = "splat"
    k = BOSCH_ME7.run_all(preset, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data)).map("kfldrl").values
    assert np.isnan(k).any()


def test_duty_levels_are_whole_percent_with_their_mean_duty():
    rpm = np.full(6, 3000.0)
    b, d, w = duty_level_points(rpm, np.array([400.0, 410, 900, 910, 905, 1]), np.array([59.77, 59.77, 69.92,
                                                                                         69.92, 70.3, np.nan]),
                                np.array([2000.0, 3000, 4000]))
    assert b.shape == (2, 3) and w[:, 1].tolist() == [2.0, 3.0]
    assert d[0, 1] == pytest.approx(59.77) and d[1, 1] == pytest.approx((69.92 * 2 + 70.3) / 3)


def test_settings_form_greys_out_what_is_not_used():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("motronic_autotuner.gui.widgets")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    form = widgets.ParamForm(BOSCH_ME7.params)
    assert form.tabs is not None and [form.tabs.tabText(i) for i in range(form.tabs.count())] == \
        ["General", "Boost", "Airflow"]
    on = lambda key: form._widgets[key][1].isEnabled()  # noqa: E731
    assert on("kfldrl_out_of_reach") and not on("fill_missing_data")
    form.set_values({"kfldrl_finish": False, "ldr_mode": "overall"})
    assert not on("kfldrl_out_of_reach") and on("fill_missing_data")
    assert on("ldr_min_file_duty") and not on("ldr_min_samples")
    assert form.values()["kfldrl_finish"] is False
    assert app is not None
