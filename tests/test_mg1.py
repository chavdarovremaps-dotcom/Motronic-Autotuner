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
    gear = np.full(n, 4.0); gear[700:] = 5.0                             # one shift at row 700 (t = 56.0 s)
    afr = np.full(n, 12.0); afr[900:911] = 22.0                          # a fuel cut at rows 900..910
    stft[694:707] = 50.0; stft[900:911] = 50.0                           # garbage in the shift and cut rows
    cols = {"Time": np.arange(n) * 0.08, "RPM (rpm)": rpm, "Load actual RAM": load, "STFT 1 (-)": stft,
            "LTFT 1 (-)": 2.0, "Lambda 1 (AFR)": afr,
            "Boost (PSI)": rng.uniform(0, 25, n), "Accel Ped. Pos. (%)": np.where(load > 150, 100.0, 30.0),
            "Coolant (*F)": 194.0, "Gear (-)": gear}
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
    # STFT + LTFT: +4 + 2 up top, -2 + 2 below; the shift and fuel-cut rows (STFT 50) never reach the cells
    np.testing.assert_allclose(fuel[has & (np.asarray(LOAD)[:, None] > 110)], 1.06)
    np.testing.assert_allclose(fuel[has & (np.asarray(LOAD)[:, None] < 90)], 1.00)
    assert any("13 of 1499 rows within 0.5 s of a shift" in m for m in res.messages)
    assert any("11 fuel-cut rows" in m for m in res.messages)


def test_worst_cylinder_pulls_more(tmp_path):
    write_mhd_log(tmp_path / "a.csv")
    p = make_preset()
    p.params["knock_source"] = "worst"
    res = BOSCH_MG1CS201.run_all(p, BOSCH_MG1CS201.ingest(tmp_path, p))
    assert res.map("timing_main_removal").values.max() == pytest.approx(3.0)


def test_compressor_feedforward_and_p_chain(tmp_path):
    from motronic_autotuner.generators.boost_feedforward import generate_compressor_feedforward, map_lookup, p_chain_check
    rng = np.random.default_rng(3)
    n = 600
    ratio_axis = np.array([1.0, 1.5, 2.0, 2.5, 3.0])
    flow_axis = np.array([100, 200, 300, 400, 500.0])
    base = np.outer(flow_axis, ratio_axis) / 20.0                       # some kW surface
    ratio = rng.uniform(2.0, 3.0, n); flow = rng.uniform(300, 500, n)
    effort = 2.0 + 0.01 * (flow - 400)                                   # what P and I had to add, kW
    dev = np.where(np.arange(n) % 5 == 0, rng.uniform(-0.4, 0.4, n), 0.01)   # every 5th row is transient
    target = np.where(np.arange(n) % 7 == 0, 0.05, 1.2)                      # every 7th row: no boost requested
    data = pd.DataFrame({
        "RPM": rng.uniform(3500, 6500, n), "Accel Ped. Pos.": 100.0, "Boost deviation": dev, "Boost target": target,
        "Boost setpoint factor": ratio, "MAF req. WGDC": flow, "MAF REQ (P corr.)": flow,
        "Compressor base": map_lookup(base, ratio_axis, flow_axis, ratio, flow),
        "Gear": 4, "WGDC I-factor": -1.0, "WGDC P-factor": 0.0,
    })
    data["Compressor after P-D"] = data["Compressor base"] + effort
    msgs = []
    maps = generate_compressor_feedforward(data, V, base_map=base, base_title="comp", axis_ratio=ratio_axis,
                                           axis_flow=flow_axis, min_samples=1, min_target=0.2, max_dev_bar=0.05,
                                           messages=msgs)
    by = {m.key: m for m in maps}
    err = by["comp_effort"].values
    has = ~np.isnan(err)
    assert has.sum() > 0 and np.all(err[has] > 0)
    # the corrected map moved by exactly the averaged effort; untouched elsewhere
    np.testing.assert_allclose(by["comp_corrected"].values[has], base[has] + err[has])
    np.testing.assert_allclose(by["comp_corrected"].values[~has], base[~has])
    assert any("steady rows of 600" in m for m in msgs) and any("gear 4" in m for m in msgs)
    expected = int(((np.abs(dev) <= 0.05) & (target >= 0.2)).sum())      # settled and requesting boost
    assert expected < 500 and any(f"{expected} steady rows" in m for m in msgs)

    # P chain: make the logged P exactly the product of two tables and check the tool reproduces it
    pfac = np.full((5, 5), 20.0)                                          # kW per bar, flat
    pcorr_dev = np.array([-500, -100, 0, 100, 500.0]); pcorr_flow = np.array([100, 300, 500.0])
    pcorr = np.tile(pcorr_dev * 2.0, (3, 1))                              # shaping = 2 x deviation in hPa
    data["WGDC P-factor"] = 20.0 * (2.0 * dev * 1000.0) / 1000.0
    out = p_chain_check(data, V, pfac=pfac, pfac_ratio=ratio_axis, pfac_flow=flow_axis, pcorr=pcorr,
                        pcorr_dev_hpa=pcorr_dev, pcorr_flow=pcorr_flow, messages=msgs)
    assert out["r"] > 0.999 and abs(out["ratio"] - 1.0) < 1e-6


def test_missing_deviation_is_derived_from_target_and_boost(tmp_path):
    """The 'timing pull' logs of 2026-09-23 had no deviation channel at all."""
    write_mhd_log(tmp_path / "a.csv")
    df = pd.read_csv(tmp_path / "a.csv", comment="#")
    df["Boost target RAM (Bar)"] = df["Boost (PSI)"] / 14.5038 + 0.1    # target = boost + 0.1 bar everywhere
    with open(tmp_path / "a.csv", "w", encoding="utf-8-sig") as f:
        f.write("#Ecu PRGID: 00005D55465A09\n")
        df.to_csv(f, index=False, lineterminator="\n")
    p = make_preset()
    logs = BOSCH_MG1CS201.ingest(tmp_path, p)
    assert "Boost deviation" in logs.full.columns
    np.testing.assert_allclose(logs.full["Boost deviation"], 0.1, atol=1e-4)
    assert any("not logged: calculated as" in m for m in logs.messages)
