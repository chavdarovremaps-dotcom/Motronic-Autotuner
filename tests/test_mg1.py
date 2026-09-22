"""Bosch MG1CS201 family: MHD logs, timing removal on four maps, fuel scalar from STFT."""

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.families.bosch_mg1cs201 import BOSCH_MG1CS201, DEFAULT_VARS as V, TIMING_MAPS, knock_signal

RPM = np.array([500, 750, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 7000.0])
LOAD = np.array([12, 20, 40, 60, 80, 100, 120, 150, 200.0])
LOAD2 = np.array([12, 19, 40, 60, 80, 100, 120, 150, 200.0])  # main 2 / cold use a slightly different axis


def write_mhd_log(path, n=1500, seed=0):
    rng = np.random.default_rng(seed)
    rpm = rng.uniform(600, 6900, n)
    load = rng.uniform(15, 195, n)
    knock = np.zeros((n, 6))
    hot = (rpm > 2000) & (rpm < 4000) & (load > 100) & (load < 150)     # every sample feeding cell (3000, 120) knocks
    knock[hot, 0] = -3.0                                                # cylinder 1 pulls 3 deg
    knock[hot, 3] = -1.5                                                # cylinder 4 pulls 1.5 deg
    stft = np.where(load > 100, 4.0, -2.0)                              # lean up top, rich below
    cols = {"Time": np.arange(n) * 0.08, "RPM (rpm)": rpm, "Load actual RAM": load, "STFT 1 (-)": stft,
            "Boost (PSI)": rng.uniform(0, 25, n), "Accel Ped. Pos. (%)": np.where(load > 150, 100.0, 30.0),
            "Coolant (*F)": 194.0, "Gear (-)": 4}
    for i in range(6):
        cols[f"Cyl{i + 1} Timing Cor (*)"] = knock[:, i]
    df = pd.DataFrame(cols)
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("#Encoding: UTF-8\n#Ecu CALID: 00007931465A39\n#Ecu PRGID: 00005D55465A09\n#VIN: TEST\n")
        df.to_csv(f, index=False, lineterminator="\n")


def make_preset():
    p = BOSCH_MG1CS201.default_preset()
    for key in TIMING_MAPS:
        p.axes[f"rpm_{key}"] = RPM
        p.axes[f"load_{key}"] = LOAD if key == "timing_main" else LOAD2
        p.base_maps[f"base_{key}"] = np.full((LOAD.size, RPM.size), 30.0)
    p.axes["rpm_fuel"], p.axes["load_fuel"] = RPM, LOAD
    p.base_maps["base_fuel"] = np.ones((LOAD.size, RPM.size))
    return p


def test_knock_signal_average_and_worst():
    d = pd.DataFrame({f"Cyl{i} Timing Cor": [0.0, -3.0] for i in range(1, 7)})
    d["Cyl1 Timing Cor"] = [-6.0, -3.0]
    np.testing.assert_allclose(knock_signal(d, V, "average"), [1.0, 3.0])
    np.testing.assert_allclose(knock_signal(d, V, "worst"), [6.0, 3.0])


def test_pipeline_on_imperial_mhd_log(tmp_path):
    write_mhd_log(tmp_path / "a.csv")
    p = make_preset()
    logs = BOSCH_MG1CS201.ingest(tmp_path, p)
    assert logs.counts()["full"] == 1499            # last row dropped as incomplete tail, nothing else
    assert logs.full["Boost"].max() < 2.0            # PSI converted to bar
    assert logs.counts()["wot"] > 0
    res = BOSCH_MG1CS201.run_all(p, logs)
    keys = [m.key for m in res.maps]
    for key in TIMING_MAPS:
        assert f"{key}_corrected" in keys and f"{key}_removal" in keys
    assert "fuel_corrected" in keys

    # average of 6 cylinders at the knocking cell: (3 + 1.5) / 6 = 0.75 -> whole 0.5 steps rounded up -> 1.0
    rem = res.map("timing_main_removal").values
    ri, ci = LOAD.tolist().index(120), RPM.tolist().index(3000)
    assert rem[ri, ci] == pytest.approx(1.0) and rem.max() == pytest.approx(1.0)
    assert rem[:, RPM.tolist().index(1000)].max() == 0.0          # far from the knock: untouched
    assert res.map("timing_main_corrected").values[ri, ci] == 29.0
    # the maps with the other load axis got their own splat, same rpm column
    rem2 = res.map("timing_cold_removal").values
    assert rem2.max() == pytest.approx(1.0) and rem2.shape == (LOAD2.size, RPM.size)

    fuel = res.map("fuel_corrected").values
    err = res.map("fuel_error").values
    has = ~np.isnan(err)
    assert has.any()
    np.testing.assert_allclose(fuel[has & (np.asarray(LOAD)[:, None] > 110)], 1.04)
    np.testing.assert_allclose(fuel[has & (np.asarray(LOAD)[:, None] < 90)], 0.98)


def test_worst_cylinder_pulls_more(tmp_path):
    write_mhd_log(tmp_path / "a.csv")
    p = make_preset()
    p.params["knock_source"] = "worst"
    res = BOSCH_MG1CS201.run_all(p, BOSCH_MG1CS201.ingest(tmp_path, p))
    assert res.map("timing_main_removal").values.max() == pytest.approx(3.0)
