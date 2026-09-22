"""Siemens MS43 family: TunerPro log reading and the closed-loop VE correction."""

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
