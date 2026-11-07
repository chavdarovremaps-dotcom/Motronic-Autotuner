import numpy as np
import pandas as pd

from motronic_autotuner.core.logs import IngestSettings, process_raw_logs, read_logger_csv, transient_mask
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7


ME7_LOGGER_PREAMBLE = [
    "", "#" * 83, "Logfile created by ME7-Logger v1.20 (c) mki, 12/2010-07/2013", "",
    "Used EcuDefinition file: WinOLS (Audi A3 (Version 5) - 362287).ecu", "",
    "ECU identified with following data:",
    "HWNumber    = 0261207436       (requested was 0261207436)",
    "SWNumber    = 1037362287       (requested was 1037362287)",
    "PartNumber  = 06A906032HJ      (requested was 06A906032HJ)",
    "SWVersion   = 0002             (requested was 0002)",
    "EngineId    = 1.8L R4/5VT      (requested was 1.8L R4/5VT)",
    "VAGHWNumber = ", "ModelId     = ", "",
    "Log packet size: 80 bytes", "Logging with:    30 samples/second", "Used speed is:   56000 baud",
    "Used mode is:    HM0", "Log started at:  27.10.2026 11:03:16.316", "",
]


def write_me7_log(path, n=40, start_time=0.0, pedal=90.0, temp=95.0, incomplete_tail=True, preamble=False):
    header = "TimeStamp, nmot_w    , wdkba     , tmotlin   , pvdks_w   , ldtvm     ,"
    units = "  sec.ms , rpm       , DK        , \xb0C        , mbar      , -         ,"
    alias = "TIME,EngineSpeed,Throttle,CoolantTemp,Boost,WGDC,"
    rows = (list(ME7_LOGGER_PREAMBLE) if preamble else []) + [header, units, alias]
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


def test_raw_me7_logger_preamble_is_skipped(tmp_path):
    p = tmp_path / "log_4cyl_basic.csv"
    write_me7_log(p, n=5, preamble=True)
    df = read_logger_csv(p)
    assert list(df.columns) == ["TimeStamp", "nmot_w", "wdkba", "tmotlin", "pvdks_w", "ldtvm"]
    assert len(df.dropna()) == 5


def test_foreign_csv_in_the_folder_is_reported_not_fatal(tmp_path):
    write_me7_log(tmp_path / "a.csv", n=30, preamble=True)
    (tmp_path / "WinOLS(Audi A3).bin.csv").write_text("a;b\n1;2\n3;4;5;6;7;8\n", encoding="latin-1")
    logs = process_raw_logs(tmp_path, BOSCH_ME7.default_preset(), IngestSettings())
    assert logs.counts()["full"] == 30
    assert any("[SKIP] WinOLS(Audi A3).bin.csv" in m for m in logs.messages)


def write_named_log(path, columns: dict[str, float], n=30):
    """An ME7-Logger file with the given channels held at fixed values (time and rpm ramp)."""
    names = ["TimeStamp"] + list(columns)
    rows = [", ".join(names), ", ".join(["sec.ms"] + ["-"] * len(columns))]
    for i in range(n):
        vals = [f"{i * 0.1:.3f}"] + [f"{(v + i * 10) if k in ('nmot', 'nmot_w') else v}" for k, v in columns.items()]
        rows.append(",".join(vals))
    path.write_text("\n".join(rows) + "\n", encoding="latin-1")


def test_missing_channels_are_named_with_the_closest_log_column(tmp_path):
    # the 2.7 biturbo (ME7.1) logs nmot, rl, pvdkds_w, pus_w and tmot where the 1.8T has nmot_w, rl_w, pvdks_w, pu, tmotlin
    write_named_log(tmp_path / "bt.csv", {"nmot": 3000, "rl": 120, "wdkba": 99, "tmot": 90, "pvdkds_w": 1800,
                                          "pus_w": 980, "ldtvm": 45})
    preset = BOSCH_ME7.default_preset()
    logs = BOSCH_ME7.ingest(tmp_path, preset)
    text = " ".join(logs.warnings)
    for expected in ("rpm = nmot_w (the logs have nmot)", "load = rl_w (the logs have rl)",
                     "boost = pvdks_w (the logs have pvdkds_w)", "pu = pu (the logs have pus_w)",
                     "tmot = tmotlin (the logs have tmot)"):
        assert expected in text
    assert any("nmot_w not in this log, transient filter skipped" in m for m in logs.messages)


def test_missing_optional_channels_are_reported_without_a_pop_up(tmp_path):
    write_me7_log(tmp_path / "log1.csv", n=30)
    logs = BOSCH_ME7.ingest(tmp_path, BOSCH_ME7.default_preset())
    assert logs.warnings == [] and any("knock = wkrm" in m for m in logs.messages)


def test_trims_of_both_banks_are_averaged(tmp_path):
    write_named_log(tmp_path / "bt.csv", {"nmot_w": 3000, "wdkba": 99, "tmotlin": 90, "frm_w": 0.98, "frm2_w": 0.94,
                                          "fra_w": 1.0, "fra2_w": 1.04})
    preset = BOSCH_ME7.default_preset()
    preset.vars.update({"stft2": "frm2_w", "ltft2": "fra2_w"})
    logs = BOSCH_ME7.ingest(tmp_path, preset)
    np.testing.assert_allclose(logs.full["frm_w"], 0.96)
    np.testing.assert_allclose(logs.full["fra_w"], 1.02)
    assert any("frm_w and frm2_w averaged" in m for m in logs.messages)
    preset.vars["stft2"] = ""
    np.testing.assert_allclose(BOSCH_ME7.ingest(tmp_path, preset).full["frm_w"], 0.98)   # one bank: untouched
