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

from dataclasses import replace

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
    "plgru": "plgru_w",
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
    "plgru": "Base boost (plgru_w = pu + DPLPU), the LDR's reference",
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
    *me7.LOG_SPLIT,
    *me7.TRANSIENTS,
    ParamSpec("overrun_pedal", "Overrun: pedal below", "float", 2.0, section=me7.GENERAL, group="Overrun filter",
              unit="%", decimals=1, minimum=0,
              tip="Drop rows with the pedal below this and the rpm above the next setting (0 = off)."),
    ParamSpec("overrun_rpm", "Overrun: and RPM above", "float", 1200.0, section=me7.GENERAL, group="Overrun filter",
              unit="rpm", decimals=0, minimum=0),
    *me7.MAPS,
    ParamSpec("knock_source", "Knock signal", "choice", "average", section=me7.GENERAL, group="Ignition knock",
              choices=(("Average of all cylinders (wkrm)", "average"), ("Worst cylinder (dwkrz per cylinder)", "worst"))),
    replace(me7.PRESSURE_REFERENCE[0], tip="Relative boost = pressure before the throttle - pu (pu must be logged). "
                                           "Off: minus the ambient pressure below."),
    *me7.PRESSURE_REFERENCE[1:],
    *me7.KFLDRL,
    *me7.KFVPDKSD,
    *me7.PID,
    *me7.MANIFOLD,
]

# The ME7 set without the VVT-only KFPBRKNW. A map that is not in the WinOLS
# export is reported as missing and its generator skips.
TARGET_MAPS = [
    TargetMap("KFLDIMX", "rpm_boost", "boost", "base_kfldimx", "Boost Control"),
    TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "Boost Control"),
    TargetMap("KFVPDKSD", "rpm_kfvp", "pratio_kfvp", "base_kfvp", "Throttle Handover", direct=True),
    TargetMap("KFLDRQ0", "rpm_kfldrq0", "x_kfldrq0", "base_kfldrq0", "Boost PID"),
    TargetMap("KFLDRQ1", "rpm_kfldrq1", "x_kfldrq1", "base_kfldrq1", "Boost PID"),
    TargetMap("KFLDRQ2", "rpm_kfldrq2", "x_kfldrq2", "base_kfldrq2", "Boost PID"),
    TargetMap("LDRQ1ST", "row_ldrq1st", "rpm_ldrq1st", "base_ldrq1st", "Boost PID"),
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
    above = d[ps] > d[boost] + PS_ABOVE_BOOST_HPA
    share = float(above.mean())
    if share < 0.02:
        return []
    excess = (d.loc[above, ps] - d.loc[above, boost]).median()
    return [
        f"{ps} is more than {PS_ABOVE_BOOST_HPA:g} hPa above {boost} in {share * 100:.0f} % of the rows (median "
        f"{excess:.0f} hPa), so it is a modelled manifold pressure, not a sensor reading: the manifold cannot hold "
        f"more pressure than there is before the throttle. The ECU computes {ps} from the HFM load through its own "
        "KFURL / KFPRG, so the KFURL / KFPRG blocks fitted to it give the file's values back and are not a "
        "calibration."
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
    GeneratorSpec("pid", "Boost PID (KFLDRQ0 / Q1 / Q2 / LDRQ1ST on the KFLDRL axis)", ("wot",),
                  ("rpm_boost", "kfldrl_x", "rpm_kfldrq0", "x_kfldrq0"), me7._pid, required_base_maps=("base_kfldrq0",)),
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
                        knock_cylinders: tuple[str, ...], target_maps: list[TargetMap] | None = None,
                        params: list[ParamSpec] | None = None,
                        generators: list[GeneratorSpec] | None = None) -> Family:
    """Build one Opel family: the shared declaration plus its per-cylinder knock channel names
    and, once its damos is known, its own map names, settings and generators (default: the ME7 set)."""
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
        params=PARAMS if params is None else params,
        target_maps=list(TARGET_MAPS if target_maps is None else target_maps),
        log_sources=[VEHICLE_LOGS],
        generators=GENERATORS if generators is None else generators,
        post_process=[me7._apply_5120_scaling],
        ingest_checks=[modelled_manifold_pressure, wastegate_never_driven],
        default_prep=DEFAULT_PREP,
        excel_sheet="Boost",
        excel_default_name=excel_default_name,
    )
