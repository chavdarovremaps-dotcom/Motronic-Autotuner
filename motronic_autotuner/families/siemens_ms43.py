"""Siemens MS43 with the MS4X custom firmware, tuned in TunerPro RT.

Maps come from the TunerPro XDF plus the car's binary instead of a WinOLS
export. Logs are TunerPro RT CSVs with ON/OFF flag columns. Two
generators: the closed-loop VE correction from Scripts/MS43_Tune_helper.m,
with paste-ready corrected VE tables, and knock-based timing removal on the
RON98 part/full load ignition map.
"""

from __future__ import annotations

from ..core.winols import TargetMap
from ..generators import column
from ..generators.ignition_knock import DEFAULT_MIN_PULL, DEFAULT_STEP, generate_knock_removal
from ..generators.ve_3d import (
    SOURCE_TRIMS, SOURCE_WIDEBAND, WIDEBAND_GAIN, WIDEBAND_OFFSET, generate_ve_corrections,
)
from .base import XDF_IMPORTER, Family, GeneratorSpec, LogSource, ParamSpec, RunContext, flag_was_on

VE_TABLES = 8
IGNITION_MAP = "ip_iga_ron98_pl__n__maf"

DEFAULT_VARS = {
    "rpm": "Engine Speed",
    "map": "Manifold Pressure",
    "ve_table": "Active VE Table",
    "load": "Engine Load Injection",
    "load_ign": "Engine Load Ignition",
    "knock": "Knock Correction Average",
    "inj": "Injection Time Average",
    "stft_b1": "Short Term Fuel Trim Bank 1",
    "ltft_m_b1": "Long Term Fuel Trim Multiplicative Bank 1",
    "stft_b2": "Short Term Fuel Trim Bank 2",
    "ltft_m_b2": "Long Term Fuel Trim Multiplicative Bank 2",
    "lambda1": "Lambda Control 1",
    "lambda2": "Lambda Control 2",
    "wideband_v": "Downstream Lambda Sensor Input Bank 1",
    "afr_target": "Air Fuel Ratio Target",
    "vanos_limp": "VANOS Limp Home",
    "full_load": "Full Load",
    "pedal": "Accelerator Pedal Position",
    "tmot": "Coolant Temperature",
    "time": "Time",
}

VAR_LABELS = {
    "rpm": "Engine speed",
    "map": "Manifold pressure",
    "ve_table": "Active VE table",
    "load": "Load (injection)",
    "load_ign": "Load (ignition)",
    "knock": "Knock correction average",
    "inj": "Injection time",
    "stft_b1": "STFT bank 1",
    "ltft_m_b1": "LTFT multiplicative bank 1",
    "stft_b2": "STFT bank 2",
    "ltft_m_b2": "LTFT multiplicative bank 2",
    "lambda1": "Lambda control bank 1",
    "lambda2": "Lambda control bank 2",
    "wideband_v": "Wideband analog input (V)",
    "afr_target": "AFR target",
    "vanos_limp": "VANOS limp home flag",
    "full_load": "Full load flag",
    "pedal": "Pedal position",
    "tmot": "Coolant temp",
    "time": "Time",
}

DEFAULT_PREP = {"align_timestamps": True, "hack_5120": False, "pressure_columns": []}

PARAMS = [
    ParamSpec("min_samples", "Min samples per cell", "int", 2, group="VE Correction", minimum=0),
    ParamSpec("use_wideband", "VE error from wideband AFR on the analog input (instead of STFT + LTFT)", "bool",
              False, group="VE Correction"),
    ParamSpec("wideband_gain", "Wideband AFR = V x gain + offset:  gain", "float", WIDEBAND_GAIN,
              group="VE Correction", decimals=3, minimum=0),
    ParamSpec("wideband_offset", "Wideband offset", "float", WIDEBAND_OFFSET, group="VE Correction", decimals=3),
    ParamSpec("knock_min_samples", "Min samples per cell", "int", 1, group="Ignition Knock Removal", minimum=0),
    ParamSpec("knock_step", "Timing step (deg)", "float", DEFAULT_STEP, group="Ignition Knock Removal",
              decimals=3, minimum=0.001),
    ParamSpec("knock_min_pull", "Ignore average pull below (deg)", "float", DEFAULT_MIN_PULL,
              group="Ignition Knock Removal", decimals=3, minimum=0),
]

TARGET_MAPS = [
    TargetMap(f"ip_map_ve_{i}__map__n", "map_ve", "rpm_ve", f"base_ve_{i}", "Volumetric Efficiency", direct=True)
    for i in range(1, VE_TABLES + 1)
] + [
    TargetMap(IGNITION_MAP, "rpm_iga", "maf_iga", "base_iga", "Ignition Timing", direct=True),
]


def _on_sheet(maps, sheet: str):
    for m in maps:
        m.sheet = sheet
    return maps


def _ve(ctx: RunContext):
    p = ctx.preset
    bases = {i: p.base_map(f"base_ve_{i}") for i in range(1, VE_TABLES + 1)}
    return _on_sheet(generate_ve_corrections(
        ctx.logs.full, p.vars,
        min_samples=float(ctx.p("min_samples", 2)),
        axis_rpm=p.axis("rpm_ve"), axis_map=p.axis("map_ve"),
        n_tables=VE_TABLES, base_maps={k: b for k, b in bases.items() if b is not None},
        source=SOURCE_WIDEBAND if ctx.p("use_wideband", False) else SOURCE_TRIMS,
        wideband_gain=float(ctx.p("wideband_gain", WIDEBAND_GAIN)),
        wideband_offset=float(ctx.p("wideband_offset", WIDEBAND_OFFSET)),
        messages=ctx.messages,
    ), "Fueling")


def _knock(ctx: RunContext):
    p = ctx.preset
    d = ctx.logs.full
    return _on_sheet(generate_knock_removal(
        column(d, p.var("load_ign")), column(d, p.var("rpm")), column(d, p.var("knock")),
        base_map=p.base_map("base_iga"), base_title=IGNITION_MAP,
        axis_x=p.axis("maf_iga"), axis_y=p.axis("rpm_iga"), x_label="Load", y_label="RPM",
        min_samples=float(ctx.p("knock_min_samples", 1)),
        step=float(ctx.p("knock_step", DEFAULT_STEP)),
        min_pull=float(ctx.p("knock_min_pull", DEFAULT_MIN_PULL)),
        messages=ctx.messages,
    ), "Ignition")


SIEMENS_MS43 = Family(
    key="siemens_ms43",
    display_name="Siemens MS43",
    default_vars=DEFAULT_VARS,
    var_labels=VAR_LABELS,
    params=PARAMS,
    target_maps=TARGET_MAPS,
    log_sources=[LogSource("tunerpro", "TunerPro RT CSV", fuzzy_columns=True, required_channels=("rpm", "ve_table"))],
    generators=[
        GeneratorSpec("ve", "VE Correction Tables", ("full",), ("rpm_ve", "map_ve"), _ve),
        GeneratorSpec("knock", "Ignition Knock Removal", ("full",), ("rpm_iga", "maf_iga"), _knock,
                      required_base_maps=("base_iga",)),
    ],
    map_importer=XDF_IMPORTER,
    ingest_checks=[flag_was_on("vanos_limp", "VANOS Limp Home")],
    default_prep=DEFAULT_PREP,
    show_pressure_hack=False,
    excel_sheet="Fueling",
    excel_default_name="MS43_Tuning_Maps.xlsx",
)
