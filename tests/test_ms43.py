"""Siemens MS43 family: TunerPro log reading and the closed-loop VE correction."""
import pytest

import numpy as np
import pandas as pd

from motronic_autotuner.core.logs import read_logger_csv, resolve_columns
from motronic_autotuner.families.siemens_ms43 import DEFAULT_VARS as V
from motronic_autotuner.families.siemens_ms43 import SIEMENS_MS43

AXIS_RPM = np.array([192, 448, 704, 992, 1504, 2016, 2496, 3008, 3488, 4000, 4512, 4992, 5500, 6016, 6200, 6496.0])
AXIS_MAP = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 93, 110, 130.0])


def write_tunerpro_log(path, n=400, single_bank=False, ve_table=1.0):
    rng = np.random.default_rng(0)
    cols = ["", "Time", "Engine Speed", "Manifold Pressure", "Active VE Table", "Engine Load Injection",
            "Injection Time Average", "Short Term Fuel Trim Bank 1", "Long Term Fuel Trim Multiplicative Bank 1",
            "Short Term Fuel Trim Bank 2", "Long Term Fuel Trim Multiplicative Bank 2", "Lambda Control 1",
            "Lambda Control 2", "Full Load", "Accelerator Pedal Position", "Coolant Temperature"]
    lines = ["TunerPro Engine data log recorded on 09/22/2026 14:34:25", ",".join(cols),
             "Sample #,Seconds,Engine Speed (rpm),Manifold Air Pressure (kPa),,mg/stk,ms,STFT Bank 1 (%),%,%,%,,,,,\xb0C"]
    for i in range(n):
        rpm = rng.uniform(700, 6500)
        mp = rng.uniform(15, 130)
        cl = "ON" if i % 4 else "OFF"
        cl2 = "OFF" if single_bank else cl
        lines.append(",".join(map(str, [
            i, round(i * 0.05, 3), round(rpm), round(mp, 2), ve_table, 100, 2.0,
            5.0, 1.0, 3.0, 1.0, cl, cl2, "OFF", 10.0, 80.0,
        ])))
    lines.append(f"{n},{n * 0.05},,,,,,,,,,,,,,")  # incomplete tail
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def test_tunerpro_reader_maps_on_off_flags(tmp_path):
    p = tmp_path / "log.csv"
    write_tunerpro_log(p, n=10)
    df = read_logger_csv(p)
    assert "Lambda Control 1" in df.columns and df["Lambda Control 1"].dtype.kind == "f"
    assert set(df["Lambda Control 1"].dropna().unique()) <= {0.0, 1.0}
    assert df["Engine Speed"].dtype.kind == "f"


def test_resolve_columns_is_case_insensitive_and_substring():
    df = pd.DataFrame({"engine speed (rpm)": [1], "Manifold Pressure": [2]})
    out = resolve_columns(df, ["Engine Speed", "Manifold Pressure", "Nope"])
    assert list(out.columns) == ["Engine Speed", "Manifold Pressure"]


def test_ms43_pipeline_dual_bank(tmp_path):
    write_tunerpro_log(tmp_path / "a.csv", n=600)
    preset = SIEMENS_MS43.default_preset()
    preset.axes = {"rpm_ve": AXIS_RPM, "map_ve": AXIS_MAP}
    logs = SIEMENS_MS43.ingest(tmp_path, preset)
    assert logs.counts()["full"] == 600  # no transient filter for MS43, ON/OFF rows survive
    result = SIEMENS_MS43.run_all(preset, logs)
    assert [m.key for m in result.maps] == [f"ve{i}" for i in range(1, 9)]
    ve1 = result.map("ve1")
    assert ve1.values.shape == (16, 16)
    # dual bank: trims (5+1) and (3+1) average to 5 everywhere data exists
    np.testing.assert_allclose(ve1.values[~np.isnan(ve1.values)], 5.0)
    assert result.map("ve2").all_nan
    assert any("Dual Bank" in m for m in result.messages)
    assert any("Extracted 450 Closed-Loop rows" in m for m in result.messages)
    assert [r.status for r in result.rows][:2] == ["Calculated", "No data"]


def test_ms43_pipeline_single_bank(tmp_path):
    write_tunerpro_log(tmp_path / "a.csv", n=300, single_bank=True, ve_table=3.0)
    preset = SIEMENS_MS43.default_preset()
    preset.axes = {"rpm_ve": AXIS_RPM, "map_ve": AXIS_MAP}
    result = SIEMENS_MS43.run_all(preset, SIEMENS_MS43.ingest(tmp_path, preset))
    ve3 = result.map("ve3").values
    np.testing.assert_allclose(ve3[~np.isnan(ve3)], 6.0)  # bank 1 only: 5 + 1
    assert result.map("ve1").all_nan
    assert any("Single Bank" in m for m in result.messages)


def test_ve_corrected_tables_are_paste_ready(tmp_path):
    write_tunerpro_log(tmp_path / "a.csv", n=600)
    preset = SIEMENS_MS43.default_preset()
    preset.axes = {"rpm_ve": AXIS_RPM, "map_ve": AXIS_MAP}
    preset.base_maps = {"base_ve_1": np.full((16, 16), 0.5), "base_ve_2": np.full((16, 16), 0.7)}
    result = SIEMENS_MS43.run_all(preset, SIEMENS_MS43.ingest(tmp_path, preset))
    keys = [m.key for m in result.maps]
    assert "ve1_corrected" in keys and "ve2_corrected" not in keys  # table 2 had no data
    corr, fixed = result.map("ve1").values, result.map("ve1_corrected").values
    has = ~np.isnan(corr)
    np.testing.assert_allclose(fixed[has], 0.5 * 1.05)   # +5 % trim
    np.testing.assert_allclose(fixed[~has], 0.5)         # untouched where no data
    assert not result.map("ve1_corrected").skip_if_empty


def test_timing_removal_steps():
    from motronic_autotuner.generators.ignition_knock import timing_removal
    pull = np.array([[np.nan, 0.0, 0.1, 0.375, 0.4, 0.75, 0.76, 1.5]])
    np.testing.assert_allclose(timing_removal(pull, 0.375), [[0, 0, 0.375, 0.375, 0.75, 0.75, 1.125, 1.5]])
    # a floor leaves leaked slivers alone
    np.testing.assert_allclose(timing_removal(np.array([0.001, 0.1, 0.2]), 0.375, min_pull=0.1), [0, 0.375, 0.375])


def test_knock_removal_on_ignition_map(tmp_path):
    from motronic_autotuner.generators.ignition_knock import generate_knock_removal
    rng = np.random.default_rng(1)
    n = 2000
    axis_rpm = np.array([1000, 2000, 3000, 4000.0])
    axis_load = np.array([100, 200, 300.0])
    rpm = rng.choice(axis_rpm, n)
    load = rng.choice(axis_load, n)
    knock = np.zeros(n)
    knock[(rpm == 3000) & (load == 300)] = -0.4          # steady 0.4 pull in one cell
    knock[(rpm == 1000) & (load == 100)] = -1.0          # exactly on the grid
    # one lone event just off a breakpoint leaks a sliver into (2000, 200): must not pull a step
    rpm = np.append(rpm, 2050.0); load = np.append(load, 200.0); knock = np.append(knock, -1.5)
    data = pd.DataFrame({"Engine Speed": rpm, "Engine Load Ignition": load, "Knock Correction Average": knock})
    base = np.full((4, 3), 20.0)
    maps = generate_knock_removal(data, V, base_map=base, base_title="iga", axis_rpm=axis_rpm, axis_load=axis_load,
                                  min_samples=1)
    by = {m.key: m for m in maps}
    removal = by["iga_removal"].values
    assert removal[2, 2] == pytest.approx(0.75) and removal[0, 0] == pytest.approx(1.125)
    assert removal[1, 1] == 0.0 and 0 < by["knock_avg"].values[1, 1] < 0.1
    assert by["iga_corrected"].values[2, 2] == 19.25
    assert by["iga_corrected"].values[1, 1] == 20.0
    assert by["knock_avg"].values[2, 2] == pytest.approx(0.4)


def test_wideband_ve_error(tmp_path):
    from motronic_autotuner.generators.ve_3d import generate_ve_corrections, wideband_afr
    rng = np.random.default_rng(4)
    n = 800
    volts = np.full(n, (15.0 - 7.35) * 5 / 15.04)      # controller reads AFR 15.0
    volts[:20] = 0.0                                    # sensor not ready: at the rail
    data = pd.DataFrame({
        V["rpm"]: rng.uniform(1000, 6000, n), V["map"]: rng.uniform(20, 120, n), V["ve_table"]: 1.0,
        V["wideband_v"]: volts, V["afr_target"]: 14.7,
        V["lambda1"]: 0.0, V["lambda2"]: 0.0,          # open loop the whole time: trims would give nothing
    })
    msgs = []
    maps = generate_ve_corrections(data, V, min_samples=1, axis_rpm=AXIS_RPM, axis_map=AXIS_MAP,
                                   base_maps={1: np.full((16, 16), 0.6)}, source="wideband", messages=msgs)
    by = {m.key: m for m in maps}
    err = by["ve1"].values
    assert by["ve1"].title == "VE Table 1 VE Error from Wideband (%)"
    np.testing.assert_allclose(err[~np.isnan(err)], (15.0 / 14.7 - 1) * 100)   # lean -> positive
    fixed = by["ve1_corrected"].values
    np.testing.assert_allclose(fixed[~np.isnan(err)], 0.6 * 15.0 / 14.7)
    assert any("Using 780 rows" in m for m in msgs)
    np.testing.assert_allclose(wideband_afr(np.array([0.0, 5.0])), [7.35, 22.39])


def test_vanos_limp_home_warning(tmp_path):
    write_tunerpro_log(tmp_path / "a.csv", n=100)
    text = (tmp_path / "a.csv").read_text(encoding="latin-1").splitlines()
    text[1] += ",VANOS Limp Home"
    text[2] += ","
    for i in range(3, len(text)):
        text[i] += ",ON" if 10 <= i < 15 else ",OFF"
    (tmp_path / "a.csv").write_text("\n".join(text) + "\n", encoding="latin-1")
    preset = SIEMENS_MS43.default_preset()
    logs = SIEMENS_MS43.ingest(tmp_path, preset)
    assert len(logs.warnings) == 1 and "VANOS Limp Home was ON in 5 of 100 rows" in logs.warnings[0]
    assert any("[WARNING]" in m for m in logs.messages)
