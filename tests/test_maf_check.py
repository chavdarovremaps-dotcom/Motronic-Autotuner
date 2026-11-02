"""MAF check: ml_w against the airflow at a reference VE on the KFKHFM grid."""

import numpy as np
import pandas as pd

from motronic_autotuner.core.logs import SplitLogs, read_logger_csv
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7, DEFAULT_VARS as V
from motronic_autotuner.generators.maf_check import airflow_at_ve, generate_maf_check

RPM = np.array([2000, 3000, 4000, 5000, 6000.0])
LOAD = np.array([60, 90, 120, 150, 180.0])


def test_airflow_at_ve():
    # 1781 cc, 6000 rpm, 2000 hPa, 30 C, 90 %: rho 2.2984 kg/m3, 0.9 * 2.2984 * 0.001781 * 50 = 0.18421 kg/s
    assert abs(airflow_at_ve(6000, 2000, 30, 1781, 90) - 184.21) < 0.05


def wot_log(n=6000, seed=4):
    """Wide-open rows at 90 % VE, except loads above 135 % where the MAF reads 10 % high.
    Plus part-throttle rows with nonsense airflow and a pressure plateau at the sensor ceiling."""
    rng = np.random.default_rng(seed)
    rpm = rng.uniform(2000, 6000, n)
    pressure = rng.uniform(1000, 2400, n)
    temp = rng.uniform(25, 45, n)
    load = pressure / 13.0
    flow = airflow_at_ve(rpm, pressure, temp, 1781, 90) * np.where(load > 135, 1.10, 1.0)
    throttle = np.where(np.arange(n) % 10 == 0, 30.0, 99.0)
    flow = np.where(throttle < 95, flow * 3, flow)
    pressure[:40] = 2550.0                                         # the sensor at its ceiling
    flow[:40] *= 0.5                                               # with nonsense airflow there
    throttle[:40] = 99.0
    return pd.DataFrame({V["rpm"]: rpm, V["load"]: load, V["maf"]: flow, V["boost"]: pressure,
                         V["iat"]: temp, V["pedal"]: throttle})


def test_maf_error_on_the_kfkhfm_grid():
    msgs = []
    base = np.ones((RPM.size, LOAD.size))
    maps = {m.key: m for m in generate_maf_check(wot_log(), V, axis_rpm=RPM, axis_load=LOAD, base_map=base,
                                                   min_samples=5, messages=msgs)}
    err = maps["maf_error"].values                                 # rows rpm, cols load
    assert maps["maf_error"].x_axis.tolist() == LOAD.tolist() and maps["maf_error"].y_axis.tolist() == RPM.tolist()
    np.testing.assert_allclose(err[:, LOAD <= 90][~np.isnan(err[:, LOAD <= 90])], 0.0, atol=0.5)
    np.testing.assert_allclose(err[:, LOAD == 180][~np.isnan(err[:, LOAD == 180])], 10.0, atol=0.5)
    ve = maps["maf_ve"].values
    np.testing.assert_allclose(ve[:, LOAD <= 90][~np.isnan(ve[:, LOAD <= 90])], 90.0, atol=0.5)
    info = maps["kfkhfm_info"].values
    np.testing.assert_allclose(info[:, LOAD == 180][~np.isnan(info[:, LOAD == 180])], 1 / 1.1, atol=0.005)
    assert "INFORMATION ONLY" in maps["kfkhfm_info"].title
    assert any("40 with pvdks_w at its ceiling left out" in m for m in msgs)


def write_me7_logger(path, unit):
    lines = ["Logfile created by ME7-Logger v1.20", "",
             "TimeStamp, nmot_w    , ml_w      , wdkba     ,",
             "  sec.ms , rpm       , " + unit + "      , %         ,",
             '"TIME","EngineSpeed","MassAirFlow","Throttle",']
    for i in range(30):
        lines.append(f"{i * 0.1:.3f},{3000 + i},{360.0},{99.0},")
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def test_units_row_is_read_and_kg_per_hour_is_converted(tmp_path):
    write_me7_logger(tmp_path / "a.csv", "kg/h")
    df = read_logger_csv(tmp_path / "a.csv")
    assert df.attrs["units"]["ml_w"] == "kg/h" and df.attrs["units"]["nmot_w"] == "rpm"
    p = BOSCH_ME7.default_preset()
    logs = BOSCH_ME7.ingest(tmp_path, p)
    assert np.allclose(logs.full["ml_w"], 100.0)                   # 360 kg/h = 100 g/s
    assert any("ml_w logged in kg/h, converted to g/s" in m for m in logs.messages)
    write_me7_logger(tmp_path / "a.csv", "g/s")
    assert np.allclose(BOSCH_ME7.ingest(tmp_path, p).full["ml_w"], 360.0)


def test_me7_run_all_includes_the_maf_check():
    preset = BOSCH_ME7.default_preset()
    preset.axes = {"rpm_kfkhfm": RPM, "load_kfkhfm": LOAD}
    data = wot_log()
    result = BOSCH_ME7.run_all(preset, SplitLogs(full=data, wot=data, warmup=pd.DataFrame(), hot=data))
    keys = [m.key for m in result.maps]
    assert keys == ["maf_error", "maf_ve"] and all(m.sheet == "Airflow" for m in result.maps)
    assert any(m.startswith("MAF check:") and "Information only." in m for m in result.messages)
