"""MS43X warm-up enrichment: target lambda, steady rows, engine start, fade fit, and the family wiring."""
import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.core.logs import SplitLogs
from motronic_autotuner.ms43_turbo import warmup as wup
from motronic_autotuner.ms43_turbo.family import DEFAULT_VARS as V
from motronic_autotuner.ms43_turbo.family import MS43_TURBO, START_COOLANT
from motronic_autotuner.ms43_turbo.splat import lookup_values

BASE = np.full((2, 2), 0.5)            # rpm rows by load columns
BASE_RPM, BASE_LOAD = np.array([1000, 3000.0]), np.array([100, 300.0])
FADE = np.full((3, 2), 0.2)            # coolant rows by coolant-at-start columns
FADE_IS = np.full((3, 2), 0.3)
TCO, TCO_ST = np.array([0, 40, 80.0]), np.array([0, 60.0])
VE_RPM, VE_MAP = np.array([1000, 2000, 3000, 4000.0]), np.array([30, 60, 100, 150.0])


def test_default_target_table_is_the_agreed_line():
    np.testing.assert_allclose(wup.warmup_lambda([-10, 0, 30, 60, 90]), [0.9, 0.9, 0.95, 1.0, 1.0])
    np.testing.assert_allclose(wup.warmup_lambda([15, 45]), [0.925, 0.975], atol=1e-3)


def test_custom_target_table():
    x, y = wup.target_curve({"x": [-10, 20, 50], "y": [0.85, 0.95, 1.0]})
    np.testing.assert_allclose(wup.warmup_lambda([-30, 5, 35, 70], x, y), [0.85, 0.9, 0.975, 1.0])


@pytest.mark.parametrize("table, message", [
    ({"x": [0, 60], "y": [0.9]}, "same number of points"),
    ({"x": [0, 60, 40], "y": [0.9, 1.0, 1.0]}, "must rise"),
    ({"x": [0, 60], "y": [0.9, 2.0]}, "between 0.5 and 1.5"),
    ({"y": [0.9]}, "unreadable"),
])
def test_bad_target_tables_are_refused(table, message):
    with pytest.raises(ValueError, match=message):
        wup.target_curve(table)


def test_steady_rows_and_rate():
    t = np.arange(0, 4, 0.04)
    rpm = np.where(t < 2, 900.0, 900.0 + (t - 2) * 2000)       # flat, then +2000 rpm/s
    steady = wup.steady_rows(t, rpm, np.full(t.size, 200.0))
    assert steady[t < 1.7].all() and not steady[t > 2.3].any()
    assert wup.rate(t, rpm)[t > 2.5] == pytest.approx(2000.0)


def test_start_info():
    t = np.arange(10) * 0.5
    flag = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0.0])
    cool = np.linspace(20, 29, 10)
    t_ast, tco_st, found = wup.start_info(t, flag, cool)
    assert found and np.isnan(t_ast[:2]).all() and t_ast[2] == 0.0 and t_ast[-1] == pytest.approx(3.5)
    assert tco_st[2:] == pytest.approx(22.0)   # coolant where the start flag went off
    t_ast, tco_st, found = wup.start_info(t, None, cool)
    assert not found and np.isnan(t_ast).all() and (tco_st == 20.0).all()


def test_lookup_values_reads_like_the_splat():
    grid = np.array([[1.0, 2.0], [3.0, np.nan]])
    out = lookup_values(grid, [0, 10], [0, 10], [5, 0, 20, 5], [0, 5, -3, 5])
    np.testing.assert_allclose(out[:3], [1.5, 2.0, 2.0])
    assert np.isnan(out[3])


def frame(cold_afr, hot_afr=None, n=20, idle=0.0):
    """Cold rows at 40 C (start 0 C) and optional warm rows at 90 C, all in the same VE cell."""
    rows = [{V["tmot"]: 40.0, V["wideband_afr"]: cold_afr, V["idle"]: idle}] * n
    if hot_afr is not None:
        rows += [{V["tmot"]: 90.0, V["wideband_afr"]: hot_afr, V["idle"]: 0.0}] * n
    df = pd.DataFrame(rows)
    df[V["rpm"]], df[V["map"]], df[V["load"]], df[V["ve_table"]] = 2000.0, 60.0, 200.0, 1.0
    df[V["afr_target"]] = 14.7
    for k in ("stft_b1", "ltft_m_b1", "stft_b2", "ltft_m_b2"):
        df[V[k]] = 0.0
    df[START_COOLANT] = 0.0
    return df


def run(df, **kw):
    msgs = []
    maps = wup.generate_warmup(
        df, V, base=BASE, axis_base_load=BASE_LOAD, axis_base_rpm=BASE_RPM, fade=FADE, axis_fade_tco=TCO,
        axis_fade_tco_st=TCO_ST, fade_is=FADE_IS, axis_fade_is_tco=TCO, axis_fade_is_tco_st=TCO_ST,
        axis_ve_rpm=VE_RPM, axis_ve_map=VE_MAP, start_col=START_COOLANT, messages=msgs, **kw)
    return {m.key: m for m in maps}, msgs


LAM_40 = float(wup.warmup_lambda(40.0))    # the default table: 0.967 at 40 C
# applied enrichment base x fade = 0.1; a reading 1.2 / 1.1 lean of the target wants 0.2, a fade of 0.4
LEAN = 14.7 * LAM_40 * 1.2 / 1.1


def test_fade_fit_with_the_ve_right():
    by, msgs = run(frame(LEAN, hot_afr=14.7))
    assert by["wup_fade_wanted"].values[1, 0] == pytest.approx(0.4)
    new = by["wup_fade_new"].values
    assert new[1, 0] == pytest.approx(0.4) and new[0, 0] == 0.2 and new[1, 1] == 0.2
    assert any("20 rows corrected for the hot VE error" in m for m in msgs)
    assert "wup_fade_is_new" not in by


def test_hot_ve_error_is_taken_out():
    # warm rows 10 % lean at the same cell: that part is VE, not warm-up
    by, _ = run(frame(LEAN, hot_afr=14.7 * 1.1))
    assert by["wup_fade_wanted"].values[1, 0] == pytest.approx((1.1 * 1.2 / 1.1 / 1.1 - 1) / 0.5)


def test_without_warm_data_skip_or_assume():
    with pytest.raises(ValueError, match="No warm-up row has hot VE data"):
        run(frame(LEAN))
    by, msgs = run(frame(LEAN), without_hot=wup.ASSUME)
    assert by["wup_fade_new"].values[1, 0] == pytest.approx(0.4)
    assert any("taken as if the VE were right" in m for m in msgs)


def test_too_rich_clips_to_zero_and_warns():
    by, msgs = run(frame(14.7 * LAM_40 * 0.8, hot_afr=14.7))
    assert by["wup_fade_wanted"].values[1, 0] < 0
    assert by["wup_fade_new"].values[1, 0] == 0.0
    assert any("[WARNING]" in m and "want a negative fade" in m for m in msgs)


def test_idle_rows_fit_the_idle_table():
    # idle fade 0.3: applied 0.15; lean 1.3 / 1.15 wants 0.3, a fade of 0.6
    by, _ = run(frame(14.7 * LAM_40 * 1.3 / 1.15, hot_afr=14.7, idle=1.0))
    assert by["wup_fade_is_new"].values[1, 0] == pytest.approx(0.6)
    assert "wup_fade_new" not in by


def test_family_keeps_cold_rows_out_of_ve_and_fits_warmup():
    df = frame(LEAN, hot_afr=14.7, n=30)
    df[V["time"]] = np.arange(len(df)) * 0.04
    preset = MS43_TURBO.default_preset()
    preset.axes = {"rpm_ve": VE_RPM, "map_ve": VE_MAP, "rpm_wup": BASE_RPM, "load_wup": BASE_LOAD,
                   "tco_fade": TCO, "tco_st_fade": TCO_ST, "tco_fade_is": TCO, "tco_st_fade_is": TCO_ST}
    preset.base_maps = {"base_wup": BASE, "base_fade": FADE, "base_fade_is": FADE_IS}
    result = MS43_TURBO.run_all(preset, SplitLogs(full=df))
    assert result.map("ve1_corr").counts.sum() == pytest.approx(30.0)          # the 30 warm rows only
    assert any("VE: 30 rows with coolant below 80 C left out" in m for m in result.messages)
    assert result.map("wup_fade_new").values[1, 0] == pytest.approx(0.4)
    assert result.map("wup_fade_new").sheet == "Warm-up"


def test_custom_table_changes_the_target_and_is_reported():
    # 40 C at lambda 1.0 instead of 0.967: the same reading is now leaner against the target, so more fade
    by, msgs = run(frame(LEAN, hot_afr=14.7), target_tco=[0, 40], target_lambda=[1.0, 1.0])
    expected = ((1.1 * LEAN / 14.7) - 1) / 0.5
    assert by["wup_fade_wanted"].values[1, 0] == pytest.approx(expected)
    assert by["wup_target"].values.tolist() == [1.0, 1.0]
    assert any("Target lambda by coolant: 0 C 1.000, 40 C 1.000." in m for m in msgs)


def test_family_reads_the_table_setting_and_saves_it(tmp_path):
    from motronic_autotuner.core.preset import Preset
    preset = MS43_TURBO.default_preset()
    assert preset.params["wup_target"] == wup.DEFAULT_TARGET
    assert preset.params["wup_target"] is not wup.DEFAULT_TARGET        # a copy, not the shared default
    preset.params["wup_target"] = {"x": [0, 30, 60], "y": [0.88, 0.94, 1.0]}
    preset.save(tmp_path / "p.json")
    again = MS43_TURBO.fill_defaults(Preset.load(tmp_path / "p.json"))
    assert again.params["wup_target"] == {"x": [0, 30, 60], "y": [0.88, 0.94, 1.0]}


def test_curve_editor_round_trip():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("motronic_autotuner.gui.widgets")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    spec = next(p for p in MS43_TURBO.params if p.key == "wup_target")
    form = widgets.ParamForm([spec])
    assert form.values()["wup_target"] == wup.DEFAULT_TARGET
    form.set_values({"wup_target": {"x": [0, 50], "y": [0.9, 1.0]}})
    editor = form._widgets["wup_target"][1]
    editor.item(1, 0).setText("0.92")             # a valid edit is taken
    editor.item(1, 1).setText("rich")             # not a number: back to the last value
    assert form.values()["wup_target"] == {"x": [0.0, 50.0], "y": [0.92, 1.0]}
    assert editor.item(1, 1).text() == "1.000"
    app.processEvents()
