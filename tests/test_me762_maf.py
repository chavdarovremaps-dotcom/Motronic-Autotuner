"""ME7.6.2 MAF check: kg/h airflow from the vehicle logger, the charge temperature modelled from tans,
the throttle (wdk1) as the wide-open filter, 1998 cc."""

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.core.logs import SplitLogs, read_vehicle_logger_csv
from motronic_autotuner.families.bosch_me762 import BOSCH_ME762, DEFAULT_VARS
from motronic_autotuner.generators.maf_check import airflow_at_ve, charge_temperature

V = DEFAULT_VARS


def test_charge_temperature_from_the_intake_air():
    assert charge_temperature(15.0, 950.0, 985.0) == pytest.approx(15.0)          # no boost, no rise
    # 2.2 pressure ratio from 15 C: 104 K out of the compressor at 70 %, a quarter left after the intercooler
    assert charge_temperature(15.0, 2167.0, 985.0) == pytest.approx(41.0, abs=0.2)
    assert charge_temperature(15.0, 2167.0, 985.0, intercooler_eff=100.0) == pytest.approx(15.0)


def test_vehicle_logger_units_row_is_kept(tmp_path):
    path = tmp_path / "Log00001.csv"
    rows = "\n".join(f"{i * 50},{3000 + i},{360.0}" for i in range(5))
    path.write_text("﻿Time,nmot,ml_w\nElapsed time,Motordrehzahl,Luftmassenfluss\nms,Upm,kg/h\n" + rows + "\n",
                    encoding="utf-8")
    df = read_vehicle_logger_csv(path)
    assert df.attrs["units"]["ml_w"] == "kg/h" and df.attrs["units"]["Time"] == "s"


def wot_log(n=3000, seed=4, ve=0.9, pu=985.0, intake=15.0):
    """Wide-open rows whose ml_w matches ``ve`` at the modelled charge temperature; wdk1 at 100 %
    except a low-rpm stretch where the pedal is down but the throttle is held at 35 %."""
    rng = np.random.default_rng(seed)
    rpm = rng.uniform(1800, 6200, n)
    boost = pu + (rpm - 1800) * 0.25                    # up to about 2085 hPa, no plateau at a ceiling
    rl = 100.0 + (boost - pu) / 14.0
    t_charge = charge_temperature(intake, boost, pu)
    flow = airflow_at_ve(rpm, boost, t_charge, 1998.0, ve * 100.0)
    throttle = np.where(rpm < 2000, 35.0, 100.0)
    plgru = pu + np.interp(rpm, [1000, 2320, 4000, 6400], [150, 610, 560, 370])
    return pd.DataFrame({V["rpm"]: rpm, V["boost"]: boost, V["load"]: rl, V["maf"]: flow, V["iat"]: intake,
                         V["pedal"]: 100.0, V["throttle"]: throttle, V["plgru"]: plgru, V["wgdc"]: 50.0})


def preset():
    p = BOSCH_ME762.default_preset()
    p.axes.update({"rpm_kfkhfm": np.array([2000, 3000, 4000, 5000, 6000.0]),
                   "load_kfkhfm": np.array([100, 120, 140, 160, 180.0]),
                   "rpm_dplpu": np.array([1000, 2320, 4000, 6400.0]), "row_dplpu": np.array([0.0])})
    p.base_maps["base_dplpu"] = np.array([[150, 610, 560, 370.0]])
    return p


def test_me762_maf_check_models_the_charge_temperature():
    p = preset()
    data = wot_log()
    res = BOSCH_ME762.run_all(p, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data))
    msg = [m for m in res.messages if m.startswith("MAF check")]
    assert "modelled from tans" in msg[0] and "pu 985 hPa from plgru_w - DPLPU" in msg[0]
    assert "rows with wdk1 >= 95 %" in msg[1]                         # the throttle, not the pedal
    ve = res.map("maf_ve").values
    assert np.nanmedian(ve) == pytest.approx(90.0, abs=0.3)          # the model the data was made with
    assert np.nanmax(np.abs(res.map("maf_error").values)) < 0.5


def test_me762_maf_check_logged_temperature_reads_low_under_boost():
    p = preset()
    p.params["maf_charge_temp"] = "logged"
    data = wot_log()
    res = BOSCH_ME762.run_all(p, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data))
    ve = res.map("maf_ve").values
    # tans before the turbo is colder than the charge: the density is overestimated, more so with more boost
    assert np.nanmedian(ve) < 89.0
    rows = [np.nanmean(r) for r in ve if np.isfinite(r).any()]
    assert rows[-1] < rows[0] - 2.0                      # 6000 rpm (most boost) reads lowest
