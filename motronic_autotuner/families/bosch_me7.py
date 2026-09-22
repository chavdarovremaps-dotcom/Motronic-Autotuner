"""Bosch ME7.x family (1.8T, Volvo, Opel ME7): the defaults, target maps and
generator set of the MATLAB MotronicTuner_GUI, minus its MED9.1 tab."""

from __future__ import annotations

import numpy as np

from ..core.logs import hack_5120
from ..core.winols import TargetMap
from ..generators.boost import generate_boost_maps
from ..generators.fuel import generate_fkkvs
from ..generators.handover import generate_handover_maps
from ..generators.ignition import generate_kfzw
from ..generators.manifold import generate_manifold_maps
from ..generators.warmup import generate_warmup_maps
from .base import Family, GeneratorSpec, LogSource, ParamSpec, RunContext, RunResult, StatusRow

DEFAULT_VARS = {
    "rpm": "nmot_w",
    "load": "rl_w",
    "pedal": "wdkba",
    "boost": "pvdks_w",
    "ps_w": "ps_w",
    "wgdc": "ldtvm",
    "vvt": "wnwi_w",
    "inj": "tevfakge_w",
    "stft": "frm_w",
    "ltft": "fra_w",
    "tmot": "tmotlin",
    "pu": "pu",
    "knock": "wkrm",
    "time": "TimeStamp",
}

VAR_LABELS = {
    "rpm": "RPM",
    "load": "Load",
    "pedal": "Pedal / throttle",
    "boost": "Boost pressure",
    "ps_w": "Manifold pressure",
    "wgdc": "Wastegate duty",
    "vvt": "VVT position",
    "inj": "Injector on-time",
    "stft": "Short term trim",
    "ltft": "Long term trim",
    "tmot": "Coolant temp",
    "pu": "Ambient pressure",
    "knock": "Knock retard",
    "time": "Time",
}

DEFAULT_PREP = {
    "align_timestamps": True,
    "hack_5120": False,
    "pressure_columns": ["pvdks_w", "pu", "pssol_w", "pvdk_w", "plgru_w", "ps_w"],
}

PARAMS = [
    ParamSpec("vvt_enabled", "VVT system", "bool", False, group="VVT Settings"),
    ParamSpec("vvt_threshold", "VVT threshold (deg)", "float", 18.0, group="VVT Settings"),
    ParamSpec("cwldimx", "CWLDIMX (relative to logged ambient)", "bool", False, group="Boost & Wastegate Settings"),
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
]

TARGET_MAPS = [
    TargetMap("KFLDIMX", "rpm_boost", "boost", "base_kfldimx", "Boost Control"),
    TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "Boost Control"),
    TargetMap("KFVPDKSD", "rpm_kfvp", "pratio_kfvp", "base_kfvp", "Throttle Handover", direct=True),
    TargetMap("FKKVS", "rpm_fuel", "te", "base_fkkvs", "Fueling"),
    TargetMap("KFFWLW", "rpm_kffwlw", "load_kffwlw", "base_kffwlw", "Warmup Enrichment"),
    TargetMap("KFFWL", "tmot", "kffwl_trim", "base_kffwl", "Warmup Enrichment"),
    TargetMap("KFZW", "rpm_ign", "load_ign", "base_kfzw", "Ignition Timing"),
    TargetMap("KFPBRK", "rpm_pbrk", "load_pbrk", "base_kfpbrk", "Saugrohrmodell"),
    TargetMap("KFPBRKNW", "rpm_pbrknw", "load_pbrknw", "base_kfpbrknw", "Saugrohrmodell"),
    TargetMap("KFPRG", "rpm_prg", "vvt_prg", "base_kfprg", "Saugrohrmodell"),
    TargetMap("KFURL", "rpm_url", "vvt_url", "base_kfurl", "Saugrohrmodell"),
]


# ---- generator wrappers: read the preset, call the pure math ------------------


def _boost(ctx: RunContext):
    p = ctx.preset
    return generate_boost_maps(
        ctx.logs.wot, p.vars,
        cwldimx=bool(ctx.p("cwldimx", False)),
        ambient_pressure=float(ctx.p("ambient_pressure", 1000)),
        min_samples=float(ctx.p("min_samples_base_wg", 1)),
        fill_missing=bool(ctx.p("fill_missing_data", False)),
        axis_rpm=p.axis("rpm_boost"), axis_boost=p.axis("boost"), axis_kfldrl_x=p.axis("kfldrl_x"),
        safety_margin=float(ctx.p("safety_margin", 0)),
    )


def _handover(ctx: RunContext):
    p = ctx.preset
    return generate_handover_maps(
        ctx.logs.wot, p.vars,
        min_samples_base_wg=float(ctx.p("min_samples_base_wg", 1)),
        ambient_pressure=float(ctx.p("ambient_pressure", 1000)),
        axis_rpm=p.axis("rpm_kfvp"), axis_pratio=p.axis("pratio_kfvp"),
    )


def _warmup(ctx: RunContext):
    p = ctx.preset
    return generate_warmup_maps(
        ctx.logs.warmup, ctx.logs.full, p.vars,
        min_samples=float(ctx.p("min_samples", 1)),
        trim_format=str(ctx.p("trim_format", "lambda")),
        axis_tmot=p.axis("tmot"), axis_load=p.axis("load_kffwlw"), axis_rpm=p.axis("rpm_kffwlw"),
        hot_temp=float(ctx.p("temp_max", 80)),
        messages=ctx.messages,
    )


def _fuel(ctx: RunContext):
    p = ctx.preset
    return generate_fkkvs(
        ctx.logs.hot, p.vars,
        min_samples=float(ctx.p("min_samples", 1)),
        trim_format=str(ctx.p("trim_format", "lambda")),
        axis_rpm=p.axis("rpm_fuel"), axis_te=p.axis("te"),
    )


def _ignition(ctx: RunContext):
    p = ctx.preset
    return generate_kfzw(
        ctx.logs.full, p.vars,
        min_samples=float(ctx.p("min_samples", 1)),
        axis_rpm=p.axis("rpm_ign"), axis_load=p.axis("load_ign"),
        vvt_split=float(ctx.p("vvt_threshold", 18)),
    )


def _manifold(ctx: RunContext):
    p = ctx.preset
    return generate_manifold_maps(
        ctx.logs.full, p.vars,
        min_samples=float(ctx.p("min_samples", 1)),
        vvt_enabled=bool(ctx.p("vvt_enabled", False)),
        vvt_threshold=float(ctx.p("vvt_threshold", 18)),
        axis_rpm=p.axis("rpm_url"),
        messages=ctx.messages,
    )


def _apply_5120_scaling(ctx: RunContext, result: RunResult) -> None:
    """With the 5120 hack on, logged pressures were doubled: KFURL doubles and KFPRG halves."""
    if not ctx.preset.prep.get("hack_5120", False):
        return
    kfurl, kfprg = result.map("kfurl"), result.map("kfprg")
    if kfurl is None or kfprg is None:
        return
    kfurl.values = np.asarray(kfurl.values) * 2.0
    kfprg.values = np.asarray(kfprg.values) / 2.0
    ctx.messages.append("  [INFO] 5120 Hack Enabled: KFURL multiplied by 2, KFPRG divided by 2.")
    idx = next(i for i, r in enumerate(result.rows) if r.map_key == "kfurl")
    result.rows.insert(idx, StatusRow("5120 Patch", "Applied", "KFURL*2, KFPRG/2"))


GENERATORS = [
    GeneratorSpec("boost", "Boost Control (KFLDIMX / KFLDRL)", ("wot",), ("rpm_boost", "boost", "kfldrl_x"), _boost),
    GeneratorSpec("handover", "Throttle Handover (KFVPDKSD)", ("wot",), ("rpm_kfvp", "pratio_kfvp"), _handover),
    GeneratorSpec("warmup", "Warmup Enrichment (KFFWL / KFFWLW)", ("warmup", "full"),
                  ("rpm_kffwlw", "load_kffwlw", "tmot"), _warmup),
    GeneratorSpec("fuel", "Fuel Trim (FKKVS)", ("hot",), ("rpm_fuel", "te"), _fuel),
    GeneratorSpec("ignition", "Ignition Timing (KFZW)", ("full",), ("rpm_ign", "load_ign"), _ignition),
    GeneratorSpec("manifold", "Intake Manifold Model (KFURL / KFPRG)", ("full",), ("rpm_url",), _manifold),
]

BOSCH_ME7 = Family(
    key="bosch_me7",
    display_name="Bosch ME7",
    default_vars=DEFAULT_VARS,
    var_labels=VAR_LABELS,
    params=PARAMS,
    target_maps=TARGET_MAPS,
    log_sources=[LogSource("me7_logger", "ME7-Logger / TunerPro CSV", hooks=(hack_5120,))],
    generators=GENERATORS,
    post_process=[_apply_5120_scaling],
    default_prep=DEFAULT_PREP,
)
