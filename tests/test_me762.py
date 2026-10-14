"""Bosch ME7.6.2 Opel family: the vehicle-logger CSV (BOM, description and
units rows, time in ms), the overrun filter and the ME7 generators on it."""

import numpy as np

from motronic_autotuner.core.logs import read_vehicle_logger_csv
from motronic_autotuner.families.bosch_me762 import BOSCH_ME762

COLS = ["Time", "nmot", "tmot", "rl_w", "wped", "wdk1", "pvdkds_w", "ps_w", "ldtvm", "frm_w", "fra_w", "wkrm", "tevfa_w"]
DESC = ["Elapsed time", "Motordrehzahl", "Motor-Temperatur", "Relative Luftfüllung (Word)", "Normierter Fahrpedalwinkel",
        "Drosselklappenwinkel aus Poti 1", "Druck vor Drosselklappe von Drucksensor (word)", "Saugrohr-Absolutdruck (Word)",
        '"LDR Tastverhältnis , moduliert (Endergebnis)"', "schneller Mittelwert des Lambdaregelfaktors (Word)",
        "multiplikative Gemischkorrektur der Gemischadaption (Word)",
        "Mittelwert der zylinderindividuellen ZW-Spätverstellungen durch KR", "effektive Einspritzzeit vor Feinabgleich (word)"]
UNITS = ["ms", "Upm", "Grad C", "%", "% PED", "% DK", "hPa", "hPa", "%", "-", "-", "grad KW", "ms"]
RPM_AXIS = np.array([1000, 2000, 3000, 4000, 5000, 6000.0])


def write_vehicle_log(path, n=400, ps_above_boost=False):
    """50 ms samples, rpm ramping 240 rpm/s. Pedal 20 % cruising, 100 % from
    row 100 to 299, released on rows 300..319 (overrun), 20 % again after.
    Knock of 2.25 deg between 2500 and 3500 rpm at full pedal."""
    rows = []
    for i in range(n):
        rpm = 1000 + i * 12
        pedal = 100.0 if 100 <= i < 300 else (0.0 if 300 <= i < 320 else 20.0)
        overrun = 300 <= i < 320
        wot = pedal >= 70
        throttle = 6.0 if overrun else pedal
        rl = 180.0 if wot else (90.0 if overrun else 30.0)          # the overrun load is the HFM artefact
        boost = 1900.0 if wot else 980.0
        ps = (boost + 100.0) if ps_above_boost else (1850.0 if wot else (1050.0 if overrun else 400.0))
        frm = 1.05 if wot else 0.98
        knock = -2.25 if (wot and 2500 <= rpm <= 3500) else 0.0
        te = 12.0 if wot else 3.0
        rows.append(f"{i * 50},{rpm},90.0,{rl:.3f},{pedal},{throttle},{boost:.3f},{ps:.3f},"
                    f"{60.0 if wot else 0.0:.2f},{frm:.6f},1.000000,{knock:.2f},{te:.4f}")
    text = "﻿" + ",".join(COLS) + "\n" + ",".join(DESC) + "\n" + ",".join(UNITS) + "\n" + "\n".join(rows) + "\n"
    path.write_text(text, encoding="utf-8")


def make_preset():
    p = BOSCH_ME762.default_preset()
    p.axes["rpm_boost"], p.axes["boost"], p.axes["kfldrl_x"] = RPM_AXIS, np.array([1000, 1500, 2000, 2500.0]), np.array([50, 100, 150, 200.0])
    p.axes["rpm_fuel"], p.axes["te"] = RPM_AXIS, np.array([1, 3, 6, 9, 12, 15.0])
    p.axes["rpm_ign"], p.axes["load_ign"] = RPM_AXIS, np.array([20, 60, 100, 140, 180, 220.0])
    return p


def test_reader_strips_bom_and_converts_ms_to_seconds(tmp_path):
    write_vehicle_log(tmp_path / "Log00001.csv", n=50)
    df = read_vehicle_logger_csv(tmp_path / "Log00001.csv")
    assert list(df.columns) == COLS
    d = df.dropna()
    assert len(d) == 50 and d["Time"].iloc[-1] == 49 * 0.05 and d["nmot"].iloc[0] == 1000


def test_ingest_filters_and_splits(tmp_path):
    write_vehicle_log(tmp_path / "Log00001.csv")
    p = make_preset()
    logs = BOSCH_ME762.ingest(tmp_path, p)
    # 400 rows: incomplete-tail rule drops the last; pedal steps at rows 100, 300 and 320 fail the
    # 33 %/s pedal rate only because the time is in seconds now; rows 301..319 are overrun
    assert any("Removed 3 transient rows" in m for m in logs.messages)
    assert any("Removed 19 overrun rows" in m for m in logs.messages)
    assert logs.counts() == {"full": 377, "wot": 199, "warmup": 0, "hot": 377}
    assert logs.warnings == []
    assert logs.full["Time"].max() < 20.0


def test_modelled_manifold_pressure_is_flagged(tmp_path):
    write_vehicle_log(tmp_path / "Log00001.csv", ps_above_boost=True)
    logs = BOSCH_ME762.ingest(tmp_path, make_preset())
    assert len(logs.warnings) == 1 and "modelled manifold pressure" in logs.warnings[0]


def test_me7_generators_run_on_opel_names(tmp_path):
    write_vehicle_log(tmp_path / "Log00001.csv")
    p = make_preset()
    res = BOSCH_ME762.run_all(p, BOSCH_ME762.ingest(tmp_path, p))
    keys = [m.key for m in res.maps]
    assert "kfldimx" in keys and "fkkvs" in keys and "kfzw" in keys
    skipped = [r for r in res.rows if r.status.startswith("Skipped")]
    assert {r.name.split(" (")[0] for r in skipped} == {"Throttle Handover", "Warmup Enrichment", "Intake Manifold Model"}

    fk = res.map("fkkvs")                                      # x = te, y = rpm; WOT rows ran lambda trim 1.05 at te 12
    te_i, rpm_i = list(fk.x_axis).index(12.0), list(fk.y_axis).index(3000.0)
    assert abs(fk.values[rpm_i, te_i] - 5.0) < 1e-9

    zw = res.map("kfzw")                                       # x = load, y = rpm; knock sits at load 180, 2500..3500 rpm
    load_i = list(zw.x_axis).index(180.0)
    assert zw.values[list(zw.y_axis).index(3000.0), load_i] < -1.0
    assert zw.values[list(zw.y_axis).index(5000.0), load_i] == 0.0
