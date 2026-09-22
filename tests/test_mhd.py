import numpy as np
import pytest

from motronic_autotuner.core.mhd import is_mhd_log, read_mhd_csv, split_unit

HEAD = "﻿#Encoding: UTF-8\n#Ecu CALID: 00007931465A39\n#Ecu PRGID: 00005D55465A09\n#VIN: XXX\n"


def test_split_unit():
    assert split_unit("Boost (Bar)") == ("Boost", "Bar")
    assert split_unit("Timing Cyl. 1") == ("Timing Cyl. 1", "")
    assert split_unit("Throttle Pos. Req (*)") == ("Throttle Pos. Req", "*")
    assert split_unit("Lambda 1 (AFR)") == ("Lambda 1", "AFR")


def test_metric_log_reads_unchanged(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text(HEAD + "Time,Boost (Bar),Coolant (*C),RPM (rpm),Gear (-)\n0.0,0.5,90,2000,3\n0.1,0.6,91,2100,3\n", encoding="utf-8")
    assert is_mhd_log(p)
    df = read_mhd_csv(p)
    assert list(df.columns) == ["Time", "Boost", "Coolant", "RPM", "Gear"]
    assert df["Boost"].tolist() == [0.5, 0.6]
    assert df.attrs["units"]["Boost"] == "bar" and df.attrs["units"]["Coolant"] == "c"


def test_imperial_log_is_converted(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text(HEAD + "Time,Boost (PSI),Coolant (*F),Speed (mph)\n0.0,14.5037738,212,62.137119\n", encoding="utf-8")
    df = read_mhd_csv(p)
    assert df["Boost"].iloc[0] == pytest.approx(1.0)
    assert df["Coolant"].iloc[0] == pytest.approx(100.0)
    assert df["Speed"].iloc[0] == pytest.approx(100.0)
    assert df.attrs["units"] == {"Time": "", "Boost": "bar", "Coolant": "c", "Speed": "km/h"}


def test_not_mhd(tmp_path):
    p = tmp_path / "c.csv"
    p.write_text("TimeStamp,nmot_w\n0,1000\n")
    assert not is_mhd_log(p)
