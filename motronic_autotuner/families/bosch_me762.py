"""Bosch ME7.6.2 (Opel Z20LET / Z20LEH, no VVT), logged with the vehicle logger.

The log is a CSV with a header row of RAM variable names, a row of German
descriptions, a units row and then data, with the elapsed time in
milliseconds. The RAM names are close to the ME7 ones (nmot, rl_w, frm_w,
fra_w, ldtvm, ps_w, wkrm) with a few Opel spellings: wped for the pedal,
pvdkds_w for the pressure before the throttle, tmot for coolant and tevfa_w
for the injection time before the FKKVS fine correction.

Same generator set as Bosch ME7 (boost, handover, warmup, fuel, ignition,
manifold model) on the ME7 map names, plus two things the Opel logs need:
the time column is converted to seconds, and overrun rows are dropped
because the HFM keeps measuring the blow-off flow while the throttle is
shut, which inflates rl_w, ml_w and the modelled ps_w.

OP-COM logs are the second log source for this family and are not wired yet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.logs import SplitLogs, hack_5120, read_vehicle_logger_csv
from ..core.preset import Preset
from ..core.winols import TargetMap
from . import bosch_me7 as me7
from .base import Family, GeneratorSpec, LogSource, ParamSpec

DEFAULT_VARS = {
    "rpm": "nmot",
    "load": "rl_w",
    "pedal": "wped",
    "throttle": "wdk1",
    "boost": "pvdkds_w",
    "boost_target": "plsol_w",
    "ps_w": "ps_w",
    "wgdc": "ldtvm",
    "vvt": "",
    "inj": "tevfa_w",
    "stft": "frm_w",
    "ltft": "fra_w",
    "tmot": "tmot",
    "pu": "",
    "knock": "wkrm",
    "time": "Time",
}

VAR_LABELS = {
    "rpm": "RPM",
    "load": "Load (rl_w)",
    "pedal": "Pedal (wped), used for the WOT split",
    "throttle": "Throttle angle (wdk1), optional",
    "boost": "Pressure before throttle",
    "boost_target": "Boost target (plsol_w), optional",
    "ps_w": "Manifold pressure",
    "wgdc": "Wastegate duty",
    "vvt": "VVT position (none on ME7.6.2)",
    "inj": "Injection time before FKKVS",
    "stft": "Short term trim",
    "ltft": "Long term trim",
    "tmot": "Coolant temp",
    "pu": "Ambient pressure (log pu to use CWLDIMX)",
    "knock": "Knock retard (wkrm)",
    "time": "Time (ms in the file, seconds after import)",
}

DEFAULT_PREP = {
    "align_timestamps": True,
    "hack_5120": False,
    "pressure_columns": ["pvdkds_w", "ps_w", "plsol_w", "plgru_w", "plsolr_w"],
}

PARAMS = [
    ParamSpec("cwldimx", "CWLDIMX (relative to logged ambient; needs pu logged)", "bool", False,
              group="Boost & Wastegate Settings"),
    ParamSpec("min_samples_base_wg", "Min samples (base WG)", "int", 1, group="Boost & Wastegate Settings", minimum=0),
    ParamSpec("safety_margin", "WGDC safety margin", "float", 1.0, group="Boost & Wastegate Settings"),
    ParamSpec("min_samples", "Min samples per cell", "int", 1, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("trim_format", "Fuel trim format", "choice", "lambda", group="General Math & Fuel Settings",
              choices=(("Lambda (factor, e.g. 1.05)", "lambda"), ("Percent (e.g. 5)", "percent"))),
    ParamSpec("fill_missing_data", "Fill missing data (KFLDRL)", "bool", False, group="General Math & Fuel Settings"),
    ParamSpec("max_rpm_roc", "Max RPM ROC (RPM/s)", "float", 1000.0, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("max_throttle_roc", "Max pedal ROC (%/s)", "float", 33.0, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("ambient_pressure", "Ambient pressure (hPa)", "float", 1000.0, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("temp_max", "Warmup max temp (C)", "float", 80.0, group="General Math & Fuel Settings"),
    ParamSpec("wot_min", "WOT minimum pedal (%)", "float", 70.0, group="General Math & Fuel Settings", minimum=0, maximum=100),
    ParamSpec("overrun_pedal", "Overrun filter: drop rows with pedal below (%) (0 = off)", "float", 2.0,
              group="Overrun Filter", decimals=1, minimum=0),
    ParamSpec("overrun_rpm", "Overrun filter: ... and RPM above", "float", 1200.0, group="Overrun Filter", minimum=0),
]

# The ME7 set without the VVT-only KFPBRKNW. Names are the ME7 ones until a
# WinOLS export of an ME7.6.2 file shows otherwise; a map that is not in the
# export is reported as missing and its generator skips.
TARGET_MAPS = [
    TargetMap("KFLDIMX", "rpm_boost", "boost", "base_kfldimx", "Boost Control"),
    TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "Boost Control"),
    TargetMap("KFVPDKSD", "rpm_kfvp", "pratio_kfvp", "base_kfvp", "Throttle Handover", direct=True),
    TargetMap("FKKVS", "rpm_fuel", "te", "base_fkkvs", "Fueling"),
    TargetMap("KFFWLW", "rpm_kffwlw", "load_kffwlw", "base_kffwlw", "Warmup Enrichment"),
    TargetMap("KFFWL", "tmot", "kffwl_trim", "base_kffwl", "Warmup Enrichment"),
    TargetMap("KFZW", "rpm_ign", "load_ign", "base_kfzw", "Ignition Timing"),
    TargetMap("KFPBRK", "rpm_pbrk", "load_pbrk", "base_kfpbrk", "Saugrohrmodell"),
    TargetMap("KFPRG", "rpm_prg", "vvt_prg", "base_kfprg", "Saugrohrmodell"),
    TargetMap("KFURL", "rpm_url", "vvt_url", "base_kfurl", "Saugrohrmodell"),
]

PS_ABOVE_BOOST_HPA = 50.0
"""A manifold pressure this far above the pre-throttle pressure cannot come from a sensor."""


def drop_overrun(df: pd.DataFrame, preset: Preset, messages: list[str]) -> pd.DataFrame:
    """Ingest hook: drop coasting rows (pedal released above an rpm floor).

    With an atmospheric blow-off valve the HFM measures air that leaves
    through the valve while the throttle is shut, so rl_w, ml_w and the
    modelled ps_w are inflated on overrun and the trims chase it.
    """
    pedal_max = float(preset.params.get("overrun_pedal", 0) or 0)
    rpm_min = float(preset.params.get("overrun_rpm", 0) or 0)
    pedal, rpm = preset.var("pedal"), preset.var("rpm")
    if pedal_max <= 0 or pedal not in df.columns or rpm not in df.columns:
        return df
    over = (df[pedal] < pedal_max) & (df[rpm] > rpm_min)
    if over.any():
        messages.append(f"  -> [FILTER] Removed {int(over.sum())} overrun rows "
                        f"(pedal below {pedal_max:g} % above {rpm_min:g} rpm).")
        df = df[~over].reset_index(drop=True)
    return df


def modelled_manifold_pressure(logs: SplitLogs, preset: Preset) -> list[str]:
    """Ingest check: a ps_w that sits above the pre-throttle pressure is a model output."""
    v = preset.vars
    d = logs.full
    ps, boost = v.get("ps_w", ""), v.get("boost", "")
    if len(d) == 0 or ps not in d.columns or boost not in d.columns:
        return []
    share = float((d[ps] > d[boost] + PS_ABOVE_BOOST_HPA).mean())
    if share < 0.02:
        return []
    return [
        f"{ps} is more than {PS_ABOVE_BOOST_HPA:g} hPa above {boost} in {share * 100:.0f} % of the rows, so it is "
        "a modelled manifold pressure, not a sensor reading. KFURL and KFPRG computed from it only reproduce the "
        "model already in the file."
    ]


GENERATORS = [
    GeneratorSpec("boost", "Boost Control (KFLDIMX / KFLDRL)", ("wot",), ("rpm_boost", "boost", "kfldrl_x"), me7._boost),
    GeneratorSpec("handover", "Throttle Handover (KFVPDKSD)", ("wot",), ("rpm_kfvp", "pratio_kfvp"), me7._handover),
    GeneratorSpec("warmup", "Warmup Enrichment (KFFWL / KFFWLW)", ("warmup", "full"),
                  ("rpm_kffwlw", "load_kffwlw", "tmot"), me7._warmup),
    GeneratorSpec("fuel", "Fuel Trim (FKKVS)", ("hot",), ("rpm_fuel", "te"), me7._fuel),
    GeneratorSpec("ignition", "Ignition Timing (KFZW)", ("full",), ("rpm_ign", "load_ign"), me7._ignition),
    GeneratorSpec("manifold", "Intake Manifold Model (KFURL / KFPRG)", ("full",), ("rpm_url",), me7._manifold),
]

VEHICLE_LOGS = LogSource(
    "vehicle", "Vehicle logger CSV (RAM names, descriptions, units, time in ms)",
    reader=read_vehicle_logger_csv, hooks=(hack_5120, drop_overrun),
)

BOSCH_ME762 = Family(
    key="bosch_me762",
    display_name="Bosch ME7.6.2 Opel (vehicle logs)",
    default_vars=DEFAULT_VARS,
    var_labels=VAR_LABELS,
    params=PARAMS,
    target_maps=TARGET_MAPS,
    log_sources=[VEHICLE_LOGS],
    generators=GENERATORS,
    post_process=[me7._apply_5120_scaling],
    ingest_checks=[modelled_manifold_pressure],
    default_prep=DEFAULT_PREP,
    excel_sheet="Boost",
    excel_default_name="ME762_Tuning_Maps.xlsx",
)
