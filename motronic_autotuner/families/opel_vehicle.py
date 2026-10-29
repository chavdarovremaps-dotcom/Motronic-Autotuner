"""Shared pieces of the Opel families logged with the vehicle logger
(Bosch ME1.5.5 and ME7.6.2, Z20LET / Z20LEH, no VVT).

The logger (OpenPort J2534, "Opel ME1.5.5/ME7.6.x/ME9.6" profile) writes a
CSV with a header row of RAM variable names, a row of German descriptions,
a units row and then data, with the elapsed time in milliseconds. Both
ECUs expose the same RAM names, close to the ME7 ones: nmot, rl_w, frm_w,
fra_w, ldtvm, ps_w, wkrm, with the Opel spellings wped for the pedal,
pvdkds_w for the pressure before the throttle, tmot for coolant and
tevfa_w for the injection time before the FKKVS fine correction. Knock is
logged with a negative sign for retard, as the average wkrm and per
cylinder (dwkrz_0_A.. on ME1.5.5, dwkrz[0].. on ME7.6.2).

The ME7 generators run unchanged on these names. On top: the time column
is converted to seconds, overrun rows are dropped (with an atmospheric
blow-off valve the HFM measures air leaving through the valve while the
throttle is shut, inflating rl_w, ml_w and the modelled ps_w), a modelled
ps_w is flagged, and the knock signal can be switched to the worst
cylinder. Map names are the ME7 ones until a WinOLS export of each file
shows otherwise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.logs import SplitLogs, hack_5120, read_vehicle_logger_csv
from ..core.preset import Preset
from ..core.winols import TargetMap
from . import bosch_me7 as me7
from .base import Family, GeneratorSpec, LogSource, ParamSpec

CYLINDERS = 4

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
    "vvt": "VVT position (none on these engines)",
    "inj": "Injection time before FKKVS",
    "stft": "Short term trim",
    "ltft": "Long term trim",
    "tmot": "Coolant temp",
    "pu": "Ambient pressure (log pu to use CWLDIMX)",
    "knock": "Knock retard, average (wkrm, negative = retard)",
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
    ParamSpec("auto_axis_kfldrl", "Auto axis KFLDRL / KFLDIMX RPM (5th point at the spool rpm)", "bool", False,
              group="Boost & Wastegate Settings"),
    ParamSpec("spool_boost_share", "Spool point: share of the peak boost (%)", "float", 90.0,
              group="Boost & Wastegate Settings", minimum=50, maximum=100),
    ParamSpec("auto_axis_kfvp", "Auto axis KFVPDKSD (0.95, 1.0, even to 1.2 x base-WG peak ratio; rows under 1.2 stock)",
              "bool", False, group="Boost & Wastegate Settings"),
    ParamSpec("min_samples", "Min samples per cell", "int", 1, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("trim_format", "Fuel trim format", "choice", "lambda", group="General Math & Fuel Settings",
              choices=(("Lambda (factor, e.g. 1.05)", "lambda"), ("Percent (e.g. 5)", "percent"))),
    ParamSpec("fill_missing_data", "Fill missing data (KFLDRL)", "bool", False, group="General Math & Fuel Settings"),
    ParamSpec("max_rpm_roc", "Max RPM ROC (RPM/s)", "float", 1000.0, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("max_throttle_roc", "Max pedal ROC (%/s)", "float", 33.0, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("ambient_pressure", "Ambient pressure (hPa)", "float", 1000.0, group="General Math & Fuel Settings", minimum=0),
    ParamSpec("temp_max", "Warmup max temp (C)", "float", 80.0, group="General Math & Fuel Settings"),
    ParamSpec("wot_min", "WOT minimum pedal (%)", "float", 70.0, group="General Math & Fuel Settings", minimum=0, maximum=100),
    ParamSpec("fit_load_max", "Fit KFURL / KFPRG on loads up to (%) (0 = all loads)", "float", 0.0,
              group="Intake Manifold Model", minimum=0, maximum=400),
    ParamSpec("pbrk_apply", "KFPBRK factor acts on", "choice", "pressure", group="Intake Manifold Model",
              choices=(("Manifold pressure before residual gas: rl = (ps x f - KFPRG) x KFURL", "pressure"),
                       ("Load: rl = (ps - KFPRG) x KFURL x f", "load"))),
    ParamSpec("knock_source", "Knock signal", "choice", "average", group="Ignition Knock",
              choices=(("Average of all cylinders (wkrm)", "average"), ("Worst cylinder (dwkrz per cylinder)", "worst"))),
    ParamSpec("overrun_pedal", "Overrun filter: drop rows with pedal below (%) (0 = off)", "float", 2.0,
              group="Overrun Filter", decimals=1, minimum=0),
    ParamSpec("overrun_rpm", "Overrun filter: ... and RPM above", "float", 1200.0, group="Overrun Filter", minimum=0),
]

# The ME7 set without the VVT-only KFPBRKNW. A map that is not in the WinOLS
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
    """Ingest hook: drop coasting rows (pedal released above an rpm floor)."""
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


def knock_from_cylinders(df: pd.DataFrame, preset: Preset, messages: list[str]) -> pd.DataFrame:
    """Ingest hook: with the worst-cylinder option, replace the average knock
    column by the per-row cylinder value of largest magnitude, sign kept."""
    if str(preset.params.get("knock_source", "average")) != "worst":
        return df
    v = preset.vars
    cols = [v.get(f"knock_cyl{i}", "") for i in range(1, CYLINDERS + 1)]
    cols = [c for c in cols if c and c in df.columns]
    knock = v.get("knock", "")
    if not cols or not knock:
        messages.append("  -> [WARNING] Worst-cylinder knock selected but no cylinder channels in this log; "
                        "the average is used.")
        return df
    stack = df[cols].to_numpy(dtype=float)
    worst = stack[np.arange(len(df)), np.argmax(np.abs(stack), axis=1)]
    df[knock] = worst
    messages.append(f"  -> Knock signal: worst of {', '.join(cols)} written to {knock}.")
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


def wastegate_never_driven(logs: SplitLogs, preset: Preset) -> list[str]:
    """Ingest check: a wastegate duty that never leaves zero means no boost control was active."""
    v = preset.vars
    d = logs.full
    wgdc = v.get("wgdc", "")
    if len(d) == 0 or wgdc not in d.columns:
        return []
    if float(d[wgdc].abs().max()) > 0:
        return []
    return [f"{wgdc} is zero in every row: the boost controller did not drive the wastegate in these logs, "
            "so KFLDIMX / KFLDRL from them are meaningless (spring pressure only)."]


GENERATORS = [
    GeneratorSpec("boost", "Boost Control (KFLDIMX / KFLDRL)", ("wot",), ("rpm_boost", "boost", "kfldrl_x"), me7._boost),
    GeneratorSpec("handover", "Throttle Handover (KFVPDKSD)", ("wot",), ("rpm_kfvp", "pratio_kfvp"), me7._handover),
    GeneratorSpec("warmup", "Warmup Enrichment (KFFWL / KFFWLW)", ("warmup", "full"),
                  ("rpm_kffwlw", "load_kffwlw", "tmot"), me7._warmup),
    GeneratorSpec("fuel", "Fuel Trim (FKKVS)", ("hot",), ("rpm_fuel", "te"), me7._fuel),
    GeneratorSpec("ignition", "Ignition Timing (KFZW)", ("full",), ("rpm_ign", "load_ign"), me7._ignition),
    GeneratorSpec("manifold", "Intake Manifold Model (KFURL / KFPRG / KFPBRK)", ("full",), ("rpm_url",), me7._manifold),
]

VEHICLE_LOGS = LogSource(
    "vehicle", "Vehicle logger CSV (RAM names, descriptions, units, time in ms)",
    reader=read_vehicle_logger_csv, hooks=(hack_5120, drop_overrun, knock_from_cylinders),
)


def opel_vehicle_family(*, key: str, display_name: str, excel_default_name: str,
                        knock_cylinders: tuple[str, ...]) -> Family:
    """Build one Opel family: the shared declaration plus its per-cylinder knock channel names."""
    default_vars = dict(DEFAULT_VARS)
    labels = dict(VAR_LABELS)
    for i, name in enumerate(knock_cylinders, start=1):
        default_vars[f"knock_cyl{i}"] = name
        labels[f"knock_cyl{i}"] = f"Knock retard cylinder {i} (worst-cylinder option)"
    # keep "time" last on the profile tab, as in the other families
    default_vars["time"] = default_vars.pop("time")
    labels["time"] = labels.pop("time")
    return Family(
        key=key,
        display_name=display_name,
        default_vars=default_vars,
        var_labels=labels,
        params=PARAMS,
        target_maps=list(TARGET_MAPS),
        log_sources=[VEHICLE_LOGS],
        generators=GENERATORS,
        post_process=[me7._apply_5120_scaling],
        ingest_checks=[modelled_manifold_pressure, wastegate_never_driven],
        default_prep=DEFAULT_PREP,
        excel_sheet="Boost",
        excel_default_name=excel_default_name,
    )
