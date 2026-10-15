"""Bosch ME1.5.5 Opel family: same vehicle-logger shape as ME7.6.2, its own
per-cylinder knock channels, the worst-cylinder option and the zero-WGDC check."""

import numpy as np

from motronic_autotuner.families import get_family
from motronic_autotuner.families.bosch_me155 import BOSCH_ME155, KNOCK_CYLINDERS

COLS = ["Time", "nmot", "tmot", "rl_w", "wped", "wdk1", "pvdkds_w", "ps_w", "ldtvm", "frm_w", "fra_w", "wkrm",
        "dwkrz", "tevfa_w", "dwkrz_0_A", "dwkrz_1_A", "dwkrz_2_A", "dwkrz_3_A"]
UNITS = ["ms", "Upm", "Grad C", "%", "% PED", "% DK", "hPa", "hPa", "%", "-", "-", "grad KW", "", "ms",
         "grad KW", "grad KW", "grad KW", "grad KW"]
RPM_AXIS = np.array([1000, 2000, 3000, 4000, 5000, 6000.0])
LOAD_AXIS = np.array([20, 60, 100, 140, 180, 220.0])


def write_me155_log(path, n=400, wgdc=60.0):
    """50 ms samples, rpm ramping 240 rpm/s, full pedal from row 100 to 299.
    Between 2500 and 3500 rpm cylinder 1 pulls 6 deg and the others 1.5, so the
    average wkrm is 2.625 and the worst cylinder 6 (both negative, the Opel sign)."""
    rows = []
    for i in range(n):
        rpm = 1000 + i * 12
        wot = 100 <= i < 300
        pedal = 100.0 if wot else 20.0
        knocking = wot and 2500 <= rpm <= 3500
        cyl = (-6.0, -1.5, -1.5, -1.5) if knocking else (0.0, 0.0, 0.0, 0.0)
        rows.append(",".join(map(str, [
            i * 50, rpm, 95.0, 180.0 if wot else 30.0, pedal, pedal, 1900.0 if wot else 980.0,
            1850.0 if wot else 400.0, wgdc if wot else 0.0, 1.02, 1.0, round(sum(cyl) / 4, 4), 255, 12.0 if wot else 3.0, *cyl,
        ])))
    desc = ",".join("x" for _ in COLS)
    path.write_text("﻿" + ",".join(COLS) + "\n" + desc + "\n" + ",".join(UNITS) + "\n" + "\n".join(rows) + "\n",
                    encoding="utf-8")


def make_preset(knock_source="average"):
    p = BOSCH_ME155.default_preset()
    p.params["knock_source"] = knock_source
    p.axes["rpm_ign"], p.axes["load_ign"] = RPM_AXIS, LOAD_AXIS
    return p


def test_family_is_registered_with_its_cylinder_channels():
    f = get_family("bosch_me155")
    assert f is BOSCH_ME155 and f.default_vars["knock_cyl1"] == KNOCK_CYLINDERS[0]
    assert list(f.default_vars)[-1] == "time"
    assert get_family("bosch_me762").default_vars["knock_cyl1"] == "dwkrz[0]"


def knock_at(res, rpm, load):
    zw = res.map("kfzw")                                   # x = load, y = rpm
    return zw.values[list(zw.y_axis).index(rpm), list(zw.x_axis).index(load)]


def test_average_and_worst_cylinder_knock(tmp_path):
    write_me155_log(tmp_path / "Log00004.csv")
    p = make_preset()
    logs = BOSCH_ME155.ingest(tmp_path, p)
    assert logs.warnings == []
    res = BOSCH_ME155.run_all(p, logs)
    avg = knock_at(res, 3000, 180)
    assert -2.625 <= avg < -1.0 and knock_at(res, 5000, 180) == 0.0

    p = make_preset("worst")
    logs = BOSCH_ME155.ingest(tmp_path, p)
    assert any("worst of dwkrz_0_A" in m for m in logs.messages)
    worst = knock_at(BOSCH_ME155.run_all(p, logs), 3000, 180)
    assert worst < avg and worst >= -6.0 and abs(worst / avg - 6.0 / 2.625) < 1e-6


def test_zero_wastegate_duty_is_flagged(tmp_path):
    write_me155_log(tmp_path / "Log00004.csv", wgdc=0.0)
    logs = BOSCH_ME155.ingest(tmp_path, make_preset())
    assert len(logs.warnings) == 1 and "did not drive the wastegate" in logs.warnings[0]
