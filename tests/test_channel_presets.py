"""Channel name presets on the profile tab: the 2.7 biturbo (ME7.1) set next to the ME7 defaults."""

import os

import pytest

from motronic_autotuner.families.bosch_me7 import BOSCH_ME7, CHANNEL_PRESETS
from test_logs import write_named_log

BITURBO = CHANNEL_PRESETS[0]


def test_the_biturbo_preset_keeps_the_defaults_it_does_not_name():
    mapping, columns = BITURBO.applied(BOSCH_ME7)
    assert {k: mapping[k] for k in ("rpm", "load", "boost", "pu", "tmot", "maf", "stft2", "ltft2")} == {
        "rpm": "nmot", "load": "rl", "boost": "pvdkds_w", "pu": "pus_w", "tmot": "tmot", "maf": "ml_w",
        "stft2": "frm2_w", "ltft2": "fra2_w"}
    assert mapping["pedal"] == "wdkba" and mapping["time"] == "TimeStamp" and mapping["iat"] == "tanslin"
    assert set(mapping) == set(BOSCH_ME7.default_vars)
    assert columns == ["pvdkds_w", "pus_w", "plsol", "plsolr_w", "ps_w"]


def test_biturbo_logs_ingest_cleanly_with_the_preset(tmp_path):
    write_named_log(tmp_path / "bt.csv", {"nmot": 3000, "rl": 120, "wdkba": 99, "tmot": 90, "pvdkds_w": 1800,
                                          "pus_w": 980, "frm_w": 0.98, "frm2_w": 0.94, "fra_w": 1.0, "fra2_w": 1.0})
    preset = BOSCH_ME7.default_preset()
    preset.vars, preset.prep["pressure_columns"] = BITURBO.applied(BOSCH_ME7)
    logs = BOSCH_ME7.ingest(tmp_path, preset)
    assert logs.warnings == [] and len(logs.full) == 29                # the last row goes, as in every log
    assert any("frm_w and frm2_w averaged" in m for m in logs.messages)
    assert any("[FILTER]" in m for m in logs.messages)          # the transient filter found rpm, pedal and time


def test_profile_tab_applies_a_channel_set_and_goes_back():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from motronic_autotuner.gui.state import AppState
    from motronic_autotuner.gui.tabs.profile import ProfileTab
    app = QApplication.instance() or QApplication([])
    state = AppState(family=BOSCH_ME7, preset=BOSCH_ME7.default_preset())
    tab = ProfileTab(BOSCH_ME7, state, sync_params=lambda: None)
    tab.channel_combo.setCurrentIndex(1)
    tab.on_apply_channels()
    assert state.preset.vars["rpm"] == "nmot" and state.preset.vars["stft2"] == "frm2_w"
    assert state.preset.prep["pressure_columns"] == list(BITURBO.pressure_columns)
    tab.channel_combo.setCurrentIndex(0)
    tab.on_apply_channels()
    assert state.preset.vars == BOSCH_ME7.default_vars
    # a name typed into a field counts once the field is left, without saving the profile
    tab._var_edits["maf"].setText("mshfm_w")
    tab._var_edits["maf"].editingFinished.emit()
    assert state.preset.vars["maf"] == "mshfm_w"
    assert app is not None
