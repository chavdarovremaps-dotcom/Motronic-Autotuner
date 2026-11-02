"""MS43 turbo, ground up: the TunerPro reader and the 4-cell splat."""
import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.ms43_turbo import read_log, read_logs, splat

X = np.array([1000, 2000, 3000.0])
Y = np.array([50, 100, 150.0])


def test_row_between_breakpoints_is_shared_by_four_cells():
    log = pd.DataFrame({"rpm": [2500.0], "map": [125.0], "v": [8.0]})
    s = splat(log, "rpm", "map", "v", X, Y, min_weight=0.1)
    np.testing.assert_allclose(s.weights[1:3, 1:3], 0.25)
    assert s.weights.sum() == pytest.approx(1.0)
    np.testing.assert_allclose(s.values[1:3, 1:3], 8.0)
    assert np.isnan(s.values[0, 0])


def test_weights_follow_the_distance():
    log = pd.DataFrame({"rpm": [1250.0], "map": [50.0], "v": [1.0]})
    s = splat(log, "rpm", "map", "v", X, Y, min_weight=0.0)
    assert s.weights[0, 0] == pytest.approx(0.75) and s.weights[0, 1] == pytest.approx(0.25)
    assert s.weights[1:].sum() == 0


def test_cell_value_is_the_weighted_average():
    log = pd.DataFrame({"rpm": [1000.0, 1500.0], "map": [50.0, 50.0], "v": [10.0, 20.0]})
    s = splat(log, "rpm", "map", "v", X, Y, min_weight=0.0)
    # cell (50, 1000): weight 1 at 10 and weight 0.5 at 20
    assert s.values[0, 0] == pytest.approx((10 + 0.5 * 20) / 1.5)
    assert s.values[0, 1] == pytest.approx(20.0)


def test_outside_the_axis_holds_the_edge_and_missing_rows_skip():
    log = pd.DataFrame({"rpm": [500.0, 9000.0, np.nan], "map": [200.0, 10.0, 100.0], "v": [1.0, 2.0, 3.0]})
    s = splat(log, "rpm", "map", "v", X, Y, min_weight=1.0)
    assert s.values[2, 0] == 1.0 and s.values[0, 2] == 2.0
    assert s.weights.sum() == pytest.approx(2.0)


def test_min_weight_leaves_thin_cells_empty():
    log = pd.DataFrame({"rpm": [1250.0], "map": [50.0], "v": [1.0]})
    s = splat(log, "rpm", "map", "v", X, Y, min_weight=0.5)
    assert s.values[0, 0] == 1.0 and np.isnan(s.values[0, 1])


def test_unknown_channel_is_named():
    with pytest.raises(KeyError, match="boost"):
        splat(pd.DataFrame({"rpm": [1.0]}), "rpm", "boost", "rpm", X, Y)


def write_tunerpro(path, rows):
    lines = ["TunerPro Engine data log recorded on 10/29/2026 20:00:00",
             ",Time,Engine Speed,Manifold Pressure,Lambda Control 1",
             "Sample #,Seconds,Engine Speed (rpm),Manifold Air Pressure (kPa),"]
    lines += [",".join(map(str, r)) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def test_reader_drops_the_units_row_and_maps_flags(tmp_path):
    write_tunerpro(tmp_path / "a.csv", [(1, 0.0, 900, 35.5, "OFF"), (2, 0.05, 2500, 140.2, "ON")])
    df = read_log(tmp_path / "a.csv")
    assert list(df.columns) == ["Sample", "Time", "Engine Speed", "Manifold Pressure", "Lambda Control 1"]
    assert len(df) == 2 and df["Lambda Control 1"].tolist() == [0.0, 1.0]
    assert df["Manifold Pressure"].iloc[1] == pytest.approx(140.2)


def test_folder_of_logs_is_one_frame(tmp_path):
    write_tunerpro(tmp_path / "a.csv", [(1, 0.0, 900, 35.5, "OFF")])
    write_tunerpro(tmp_path / "b.csv", [(1, 0.0, 3000, 150.0, "ON"), (2, 0.05, 3100, 152.0, "ON")])
    df = read_logs(tmp_path)
    assert df["File"].tolist() == ["a.csv", "b.csv", "b.csv"]
    assert df["Engine Speed"].tolist() == [900, 3000, 3100]


# ---- VE correction -------------------------------------------------------------

from motronic_autotuner.ms43_turbo.family import FUEL_CUT_WINDOW, MS43_TURBO
from motronic_autotuner.ms43_turbo.family import DEFAULT_VARS as V
from motronic_autotuner.ms43_turbo.ve import (
    fuel_cut_window, generate_ve_correction, table_shares, wideband_factor, wideband_lag,
)

RPM_AXIS = np.array([1000, 2000, 3000, 4000.0])
MAP_AXIS = np.array([30, 60, 100, 150.0])


def test_wideband_lean_raises_ve_and_trims_add():
    # lean 16.17 against 14.7 is +10 %, a +2 % trim on top gives 1.12
    assert wideband_factor(16.17, 14.7, 2.0) == pytest.approx(1.12)
    # rich 13.23 against 14.7 is -10 %
    assert wideband_factor(13.23, 14.7, 0.0) == pytest.approx(0.90)
    assert wideband_factor(14.7, 14.7, -3.0) == pytest.approx(0.97)


def test_blended_tables_share_the_row():
    np.testing.assert_allclose(table_shares([2.5])[0, :3], [0, 0.5, 0.5])


def test_fuel_cut_window_and_lag():
    t = np.arange(0, 3, 0.1)
    cut = ((t >= 1.0) & (t < 1.5)).astype(float)
    win = fuel_cut_window(t, cut, 0.5)
    assert win[np.isclose(t, 0.9)].sum() == 0 and win[np.isclose(t, 1.2)].all() and win[np.isclose(t, 1.9)].all()
    assert not win[np.isclose(t, 2.0)].any()
    afr = np.where((t >= 1.4) & (t < 2.2), 18.0, 12.0)
    assert wideband_lag(t, cut, afr) == [pytest.approx(0.4)]


def frame(rows):
    defaults = {V[k]: 0.0 for k in ("stft_b1", "ltft_m_b1", "stft_b2", "ltft_m_b2", "lambda1", "lambda2")}
    defaults[V["ve_table"]] = 1.0
    return pd.DataFrame({**defaults, **rows})


def test_ve_from_wideband_on_the_grid():
    df = frame({V["rpm"]: [2000.0] * 4, V["map"]: [60.0] * 4, V["afr_target"]: 14.7,
                V["wideband_afr"]: [16.17, 16.17, 16.17, 30.0], FUEL_CUT_WINDOW: [0, 0, 0, 1.0]})
    base = np.full((4, 4), 0.8)
    msgs = []
    maps = {m.key: m for m in generate_ve_correction(
        df, V, wideband=True, both_banks=False, axis_rpm=RPM_AXIS, axis_map=MAP_AXIS, base_maps={1: base},
        min_weight=1, skip_col=FUEL_CUT_WINDOW, messages=msgs)}
    assert maps["ve1_corr"].values[1, 1] == pytest.approx(10.0)       # the fuel-cut row is out
    assert maps["ve1_new"].values[1, 1] == pytest.approx(0.88)
    assert maps["ve1_new"].values[0, 0] == 0.8                         # no data: unchanged
    assert maps["ve1_corr"].counts[1, 1] == pytest.approx(3.0)
    assert any("3 of 4 rows used" in m for m in msgs)


def test_ve_wideband_rail_rows_dropped():
    df = frame({V["rpm"]: [2000.0, 2000.0], V["map"]: [60.0, 60.0], V["afr_target"]: 14.7,
                V["wideband_afr"]: [9.40, 13.23], V["wideband_v"]: [0.0, 2.0]})
    maps = generate_ve_correction(df, V, wideband=True, both_banks=False, axis_rpm=RPM_AXIS, axis_map=MAP_AXIS,
                                  min_weight=1)
    assert maps[0].values[1, 1] == pytest.approx(-10.0)


def test_ve_trims_only_uses_closed_loop_and_both_banks():
    df = frame({V["rpm"]: [3000.0] * 3, V["map"]: [100.0] * 3,
                V["stft_b1"]: [4.0, 4.0, 50.0], V["ltft_m_b1"]: [2.0, 2.0, 0.0],
                V["stft_b2"]: [0.0, 0.0, 0.0], V["ltft_m_b2"]: [2.0, 2.0, 0.0],
                V["lambda1"]: [1.0, 1.0, 0.0], V["lambda2"]: [1.0, 1.0, 0.0]})
    one = generate_ve_correction(df, V, wideband=False, both_banks=False, axis_rpm=RPM_AXIS, axis_map=MAP_AXIS, min_weight=1)
    both = generate_ve_correction(df, V, wideband=False, both_banks=True, axis_rpm=RPM_AXIS, axis_map=MAP_AXIS, min_weight=1)
    assert one[0].values[2, 2] == pytest.approx(6.0)
    assert both[0].values[2, 2] == pytest.approx(4.0)
    no_closed = df.assign(**{V["lambda1"]: 0.0})
    with pytest.raises(ValueError, match="closed loop was never on"):
        generate_ve_correction(no_closed, V, wideband=False, both_banks=False, axis_rpm=RPM_AXIS, axis_map=MAP_AXIS)


def test_ve_blend_goes_to_both_tables():
    df = frame({V["rpm"]: [2000.0] * 2, V["map"]: [60.0] * 2, V["afr_target"]: 14.7,
                V["wideband_afr"]: [16.17, 16.17], V["ve_table"]: [1.5, 1.5]})
    maps = {m.key: m for m in generate_ve_correction(df, V, wideband=True, both_banks=False, axis_rpm=RPM_AXIS,
                                                     axis_map=MAP_AXIS, min_weight=0.5)}
    assert maps["ve1_corr"].counts[1, 1] == pytest.approx(1.0) and maps["ve2_corr"].counts[1, 1] == pytest.approx(1.0)
    assert maps["ve2_corr"].values[1, 1] == pytest.approx(10.0)


def write_turbo_log(path):
    names = ["Time", "Engine Speed", "Manifold Pressure", "Active VE Table", "Air Fuel Ratio Target",
             "Short Term Fuel Trim Bank 1", "Long Term Fuel Trim Multiplicative Bank 1",
             "Short Term Fuel Trim Bank 2", "Long Term Fuel Trim Multiplicative Bank 2",
             "Lambda Control 1", "Lambda Control 2", "Trailing Throttle Fuel Cut",
             "Accelerator Pedal Position", "Coolant Temperature", "Wideband AFR",
             "Engine Load Injection", "Throttle Body Position"]
    lines = ["TunerPro Engine data log recorded on 10/29/2026 18:59:24", "," + ",".join(names),
             "Sample #,Seconds" + "," * (len(names) - 1)]
    for i in range(200):
        t = i * 0.04
        cut = "ON" if 100 <= i < 120 else "OFF"
        afr = 18.0 if 100 <= i < 140 else 13.23
        lines.append(",".join(map(str, [i + 1, round(t, 3), 2000, 60.0, 1.0, 14.7, 0.0, 0.0, 0.0, 0.0,
                                        "OFF", "OFF", cut, 20.0, 88.0, afr, 500.0, 20.0])))
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def test_turbo_app_end_to_end(tmp_path):
    write_turbo_log(tmp_path / "log3.csv")
    preset = MS43_TURBO.default_preset()
    assert preset.params["wideband"] is True and preset.params["both_banks"] is False
    preset.axes = {"rpm_ve": RPM_AXIS, "map_ve": MAP_AXIS}
    preset.base_maps = {"base_ve_1": np.full((4, 4), 0.8)}
    logs = MS43_TURBO.ingest(tmp_path, preset)
    assert any("Wideband reads lean" in m for m in logs.messages)
    result = MS43_TURBO.run_all(preset, logs)
    assert [m.key for m in result.maps] == ["ve1_corr", "ve1_new"]
    # the cut (0.8 s) and the 1 s after it are out, so only the rich rows remain
    assert result.map("ve1_corr").values[1, 1] == pytest.approx(-10.0)
    assert result.map("ve1_new").values[1, 1] == pytest.approx(0.72)
    assert result.map("ve1_new").sheet == "Fueling"


# ---- ip_maf_1_diag from the scaled load ------------------------------------------

from motronic_autotuner.ms43_turbo.maf_diag import generate_maf_diag

TPS_AXIS = np.array([0, 10, 20, 40.0])


def test_maf_diag_puts_the_scaled_load():
    # rich 11.76 against 14.7: the ECU over-estimates the air by 25 %, the table gets 500 x 0.8
    df = frame({V["rpm"]: [2000.0] * 3, V["tps"]: [20.0] * 3, V["load"]: [500.0] * 3, V["afr_target"]: 14.7,
                V["wideband_afr"]: [11.76, 11.76, 18.0], FUEL_CUT_WINDOW: [0, 0, 1.0]})
    base = np.full((4, 4), 300.0)
    msgs = []
    maps = {m.key: m for m in generate_maf_diag(
        df, V, wideband=True, both_banks=False, axis_tps=TPS_AXIS, axis_rpm=RPM_AXIS, base_map=base,
        min_weight=1, skip_col=FUEL_CUT_WINDOW, messages=msgs)}
    assert maps["maf_diag_logs"].values[1, 2] == pytest.approx(400.0)
    assert maps["maf_diag_logs"].counts[1, 2] == pytest.approx(2.0)
    assert maps["maf_diag_new"].values[1, 2] == pytest.approx(400.0)
    assert maps["maf_diag_new"].values[0, 0] == 300.0
    assert any("1.33 x the factory value" in m for m in msgs)
    assert any(m.startswith("ip_maf_1_diag__n__tps_av factor from the wideband") for m in msgs)


def test_maf_diag_without_wideband_uses_closed_loop_trims():
    df = frame({V["rpm"]: [3000.0] * 2, V["tps"]: [10.0] * 2, V["load"]: [200.0, 600.0],
                V["stft_b1"]: [5.0, 0.0], V["lambda1"]: [1.0, 0.0]})
    maps = generate_maf_diag(df, V, wideband=False, both_banks=False, axis_tps=TPS_AXIS, axis_rpm=RPM_AXIS,
                             min_weight=1)
    assert [m.key for m in maps] == ["maf_diag_logs"]
    assert maps[0].values[2, 1] == pytest.approx(210.0)
    assert np.isfinite(maps[0].values).sum() == 1


def test_turbo_app_builds_the_maf_diag_table(tmp_path):
    write_turbo_log(tmp_path / "log3.csv")
    preset = MS43_TURBO.default_preset()
    preset.axes = {"rpm_ve": RPM_AXIS, "map_ve": MAP_AXIS, "rpm_maf_diag": RPM_AXIS, "tps_maf_diag": TPS_AXIS}
    preset.base_maps = {"base_maf_diag": np.full((4, 4), 300.0)}
    result = MS43_TURBO.run_all(preset, MS43_TURBO.ingest(tmp_path, preset))
    assert [m.key for m in result.maps] == ["ve1_corr", "maf_diag_logs", "maf_diag_new"]
    # rich rows at 13.23 against 14.7: 500 x 0.9
    assert result.map("maf_diag_new").values[1, 2] == pytest.approx(450.0)
    assert result.map("maf_diag_new").sheet == "Load"


# ---- ignition: knock pull and advance on ip_iga_ron98_pl -------------------------

from motronic_autotuner.ms43_turbo.ignition import generate_ignition

LOAD_AXIS = np.array([100, 300, 500.0])
IGA_RPM_AXIS = np.array([2000, 3000, 4000.0])


def ign_frame(cells):
    """cells: (rpm, load, knock, rows, part_load) on breakpoints."""
    rows = []
    for rpm, load, knock, n, pl in cells:
        rows += [{V["rpm"]: rpm, V["load_ign"]: load, V["knock"]: knock, V["part_load"]: pl,
                  V["full_load"]: 0.0}] * n
    return pd.DataFrame(rows)


def test_ignition_pulls_advances_and_leaves_thin_cells():
    df = ign_frame([
        (3000, 500, -0.4, 10, 1.0),   # steady 0.4 retard: pull 0.75
        (2000, 100, 0.0, 10, 1.0),    # no retard, 10 samples: +0.7
        (2000, 300, 0.0, 2, 1.0),     # no retard, 2 samples: too thin to add
        (4000, 100, 0.0, 50, 0.0),    # idle or fuel cut: not on this map
    ])
    df = pd.concat([df, ign_frame([(4000, 500, -0.05, 10, 1.0)])], ignore_index=True)  # under the 0.1 floor
    base = np.full((3, 3), 20.0)
    msgs = []
    by = {m.key: m for m in generate_ignition(df, V, base_map=base, axis_load=LOAD_AXIS, axis_rpm=IGA_RPM_AXIS,
                                              messages=msgs)}
    new, change = by["iga_new"].values, by["iga_change"].values
    assert new[1, 2] == pytest.approx(19.25) and change[1, 2] == pytest.approx(-0.75)
    assert new[0, 0] == pytest.approx(20.7)
    assert new[0, 1] == 20.0 and change[0, 1] == 0.0
    assert new[2, 0] == 20.0 and np.isnan(change[2, 0])          # only non-map rows there
    assert new[2, 2] == 20.0                                      # sliver under the floor
    assert by["iga_knock_avg"].values[1, 2] == pytest.approx(0.4)
    assert any("32 of 82 rows with Part Load or Full Load on" in m for m in msgs)
    assert any("1 cells pulled" in m and "1 cells without retard advanced" in m for m in msgs)
    assert any("lands as +0.75 deg" in m for m in msgs)


def test_ignition_knock_between_cells_is_shared():
    # one knock row halfway between two load breakpoints pulls both cells by its half-weight average
    df = pd.DataFrame([{V["rpm"]: 3000.0, V["load_ign"]: 200.0, V["knock"]: -0.5, V["part_load"]: 1.0, V["full_load"]: 0.0}] * 4)
    by = {m.key: m for m in generate_ignition(df, V, base_map=np.full((3, 3), 20.0), axis_load=LOAD_AXIS,
                                              axis_rpm=IGA_RPM_AXIS)}
    assert by["iga_knock_avg"].counts[1, 0] == pytest.approx(2.0) and by["iga_knock_avg"].counts[1, 1] == pytest.approx(2.0)
    assert by["iga_change"].values[1, 0] == pytest.approx(-0.75) and by["iga_change"].values[1, 1] == pytest.approx(-0.75)


def test_ignition_without_load_flags_drops_fuel_cut_and_idle():
    df = pd.DataFrame([{V["rpm"]: 2000.0, V["load_ign"]: 100.0, V["knock"]: 0.0, V["fuel_cut"]: 1.0, V["idle"]: 0.0}] * 10)
    msgs = []
    with pytest.raises(ValueError, match="No rows on"):
        generate_ignition(df, V, base_map=np.full((3, 3), 20.0), axis_load=LOAD_AXIS, axis_rpm=IGA_RPM_AXIS, messages=msgs)
    assert any("load range flags not logged" in m for m in msgs)
