import numpy as np
import pandas as pd

from motronic_autotuner.core.logs import IngestSettings, process_raw_logs, read_logger_csv, transient_mask
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7


def write_me7_log(path, n=40, start_time=0.0, pedal=90.0, temp=95.0, incomplete_tail=True):
    header = "TimeStamp, nmot_w    , wdkba     , tmotlin   , pvdks_w   , ldtvm     ,"
    units = "  sec.ms , rpm       , DK        , \xb0C        , mbar      , -         ,"
    alias = "TIME,EngineSpeed,Throttle,CoolantTemp,Boost,WGDC,"
    rows = [header, units, alias]
    for i in range(n):
        t = start_time + i * 0.1
        rows.append(f"{t:.3f},{2000 + i * 10},{pedal},{temp},{1500 + i},{50},")
    if incomplete_tail:
        rows.append(f"{start_time + n * 0.1:.3f},2500,,,,,")
    path.write_text("\n".join(rows) + "\n", encoding="latin-1")


def test_read_logger_csv_cleans_units_and_alias_rows(tmp_path):
    p = tmp_path / "a.csv"
    write_me7_log(p, n=5)
    df = read_logger_csv(p)
    assert list(df.columns) == ["TimeStamp", "nmot_w", "wdkba", "tmotlin", "pvdks_w", "ldtvm"]
    assert df["nmot_w"].dtype.kind == "f"
    assert len(df) == 8  # units row, alias row, 5 data rows, incomplete tail
    assert len(df.dropna()) == 5  # units, alias and the incomplete tail are all-or-partly NaN


def test_tunerpro_title_line_is_skipped(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("TunerPro Data Log v5\nTimeStamp,nmot_w\n0,1000\n0.1,1100\n0.2,1200\n")
    df = read_logger_csv(p)
    assert list(df.columns) == ["TimeStamp", "nmot_w"] and len(df) == 3


def test_transient_mask():
    t = np.array([0, 0.1, 0.2, 0.3, 0.3])
    rpm = np.array([1000, 1050, 1500, 1520, 1530])
    pedal = np.array([10, 12, 13, 60, 61])
    m = transient_mask(t, rpm, pedal, max_rpm_roc=1000, max_pedal_roc=33)
    # row 2: rpm jumps 450 in 0.1 s = 4500 rpm/s; row 3: pedal jumps 47 %/0.1 s
    # row 4: dt = 0 -> 0.001 s, both rates explode
    assert m.tolist() == [True, True, False, False, False]


def test_process_raw_logs_splits_and_aligns(tmp_path):
    write_me7_log(tmp_path / "log1.csv", n=30, pedal=90, temp=95)
    write_me7_log(tmp_path / "log2.csv", n=20, start_time=0.0, pedal=20, temp=40)
    preset = BOSCH_ME7.default_preset()
    preset.prep["hack_5120"] = True
    preset.prep["pressure_columns"] = ["pvdks_w"]
    settings = IngestSettings(max_rpm_roc=1000, max_pedal_roc=33, wot_min=70, temp_max=80)
    logs = process_raw_logs(tmp_path, preset, settings, hooks=BOSCH_ME7.log_sources[0].hooks)
    assert logs.counts() == {"full": 50, "wot": 30, "warmup": 20, "hot": 30}
    # timestamps of the second file continue after the first
    t = logs.full["TimeStamp"].to_numpy()
    assert np.all(np.diff(t) >= 0)
    # the 5120 hack doubled the boost column
    assert logs.full["pvdks_w"].iloc[0] == 3000
    assert any("[FILTER]" in m for m in logs.messages)


def test_process_raw_logs_no_files(tmp_path):
    preset = BOSCH_ME7.default_preset()
    try:
        process_raw_logs(tmp_path, preset, IngestSettings())
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_required_columns_keep_rows_with_other_nans(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("TunerPro log\nTimeStamp,nmot_w,wdkba,tmotlin,extra\n0,1000,10,90,\n0.1,1100,10,90,5\n0.2,1200,10,90,\n0.3,,10,90,1\n0.4,1300,10,90,2\n")
    preset = BOSCH_ME7.default_preset()
    logs = process_raw_logs(tmp_path, preset, IngestSettings(max_rpm_roc=float("inf"), max_pedal_roc=float("inf")),
                            required_columns=["nmot_w"])
    # last row dropped as incomplete tail, one row dropped for NaN rpm, NaN in 'extra' kept
    assert logs.counts()["full"] == 3
