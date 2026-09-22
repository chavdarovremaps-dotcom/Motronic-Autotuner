"""Siemens MS43 with the MS4X custom firmware, tuned in TunerPro RT.

Maps come from the TunerPro XDF plus the car's binary instead of a WinOLS
export. Logs are TunerPro RT CSVs with ON/OFF flag columns. The one
generator is the closed-loop VE correction from Scripts/MS43_Tune_helper.m.
"""

from __future__ import annotations

from ..core.winols import TargetMap
from ..generators.ve_3d import generate_ve_corrections
from .base import XDF_IMPORTER, Family, GeneratorSpec, LogSource, ParamSpec, RunContext

VE_TABLES = 8

DEFAULT_VARS = {
    "rpm": "Engine Speed",
    "map": "Manifold Pressure",
    "ve_table": "Active VE Table",
    "load": "Engine Load Injection",
    "inj": "Injection Time Average",
    "stft_b1": "Short Term Fuel Trim Bank 1",
    "ltft_m_b1": "Long Term Fuel Trim Multiplicative Bank 1",
    "stft_b2": "Short Term Fuel Trim Bank 2",
    "ltft_m_b2": "Long Term Fuel Trim Multiplicative Bank 2",
    "lambda1": "Lambda Control 1",
    "lambda2": "Lambda Control 2",
    "full_load": "Full Load",
    "pedal": "Accelerator Pedal Position",
    "tmot": "Coolant Temperature",
    "time": "Time",
}

VAR_LABELS = {
    "rpm": "Engine speed",
    "map": "Manifold pressure",
    "ve_table": "Active VE table",
    "load": "Load",
    "inj": "Injection time",
    "stft_b1": "STFT bank 1",
    "ltft_m_b1": "LTFT multiplicative bank 1",
    "stft_b2": "STFT bank 2",
    "ltft_m_b2": "LTFT multiplicative bank 2",
    "lambda1": "Lambda control bank 1",
    "lambda2": "Lambda control bank 2",
    "full_load": "Full load flag",
    "pedal": "Pedal position",
    "tmot": "Coolant temp",
    "time": "Time",
}

DEFAULT_PREP = {"align_timestamps": True, "hack_5120": False, "pressure_columns": []}

PARAMS = [
    ParamSpec("min_samples", "Min samples per cell", "int", 2, group="VE Correction", minimum=0),
]

TARGET_MAPS = [
    TargetMap(f"ip_map_ve_{i}__map__n", "map_ve", "rpm_ve", f"base_ve_{i}", "Volumetric Efficiency", direct=True)
    for i in range(1, VE_TABLES + 1)
]


def _ve(ctx: RunContext):
    p = ctx.preset
    return generate_ve_corrections(
        ctx.logs.full, p.vars,
        min_samples=float(ctx.p("min_samples", 2)),
        axis_rpm=p.axis("rpm_ve"), axis_map=p.axis("map_ve"),
        n_tables=VE_TABLES, messages=ctx.messages,
    )


SIEMENS_MS43 = Family(
    key="siemens_ms43",
    display_name="Siemens MS43",
    default_vars=DEFAULT_VARS,
    var_labels=VAR_LABELS,
    params=PARAMS,
    target_maps=TARGET_MAPS,
    log_sources=[LogSource("tunerpro", "TunerPro RT CSV", fuzzy_columns=True, required_channels=("rpm", "ve_table"))],
    generators=[GeneratorSpec("ve", "VE Correction Tables", ("full",), ("rpm_ve", "map_ve"), _ve)],
    map_importer=XDF_IMPORTER,
    default_prep=DEFAULT_PREP,
    show_pressure_hack=False,
    excel_sheet="MS43 VE Maps",
    excel_default_name="MS43_Tuning_Maps.xlsx",
)
