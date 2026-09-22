import json

import numpy as np

from motronic_autotuner.core.preset import Preset, normalize_trim_format
from motronic_autotuner.families.bosch_me7 import BOSCH_ME7

MATLAB_STYLE = {
    "files": {"excel_filename": "ME_Tuning_Maps.xlsx"},
    "vars": {"rpm": "nmot_w", "time": "TimeStamp"},
    "prep": {"ALIGN_TIMESTAMPS": 1, "HACK_5120": 0, "pressure_columns": "pvdks_w, pu, ps_w", "wot_min": 70, "temp_max": 80},
    "params": {"min_samples": 2, "trim_format": "Percent,", "CWLDIMX": 1, "FILL_MISSING_DATA": 0, "VVT_ENABLED": True},
    "axes": {"rpm_boost": [1000, 2000, 3000], "boost": [250, 500]},
    "base_maps": {"base_kfldimx": [[0, 100], [0, 100], [0, 100]]},
}


def test_matlab_spellings_are_normalised():
    p = Preset.from_dict(MATLAB_STYLE)
    assert p.family == "bosch_me7"
    assert p.prep["align_timestamps"] is True
    assert p.prep["hack_5120"] is False
    assert p.prep["pressure_columns"] == ["pvdks_w", "pu", "ps_w"]
    assert p.params["wot_min"] == 70 and p.params["temp_max"] == 80
    assert p.params["cwldimx"] is True and p.params["fill_missing_data"] is False and p.params["vvt_enabled"] is True
    assert p.params["trim_format"] == "percent"
    assert p.axis("rpm_boost").tolist() == [1000, 2000, 3000]
    assert p.base_map("base_kfldimx").shape == (3, 2)
    assert p.axis("nope") is None


def test_round_trip_keeps_matlab_spellings(tmp_path):
    p = Preset.from_dict(MATLAB_STYLE)
    path = tmp_path / "p.json"
    p.save(path)
    raw = json.loads(path.read_text())
    assert raw["prep"]["ALIGN_TIMESTAMPS"] == 1
    assert raw["params"]["CWLDIMX"] == 1
    assert raw["params"]["trim_format"] == "Percent"
    assert raw["family"] == "bosch_me7"
    again = Preset.load(path)
    assert again.params == p.params
    np.testing.assert_array_equal(again.base_map("base_kfldimx"), p.base_map("base_kfldimx"))


def test_trim_format_spellings():
    assert normalize_trim_format(0) == "lambda"
    assert normalize_trim_format(1) == "percent"
    assert normalize_trim_format("Lambda") == "lambda"
    assert normalize_trim_format("Percent,") == "percent"


def test_family_default_preset_and_fill():
    p = BOSCH_ME7.default_preset()
    assert p.vars["rpm"] == "nmot_w"
    assert p.params["wot_min"] == 70.0
    old = Preset.from_dict({"vars": {"rpm": "x"}})
    BOSCH_ME7.fill_defaults(old)
    assert old.vars["rpm"] == "x" and old.vars["load"] == "rl_w"
    assert old.params["min_samples"] == 1
