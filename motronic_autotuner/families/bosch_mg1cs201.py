"""Bosch MG1CS201 (BMW B58 and S58, MHD+ definitions), logged with MHD.

Maps come from the MHD+ TunerPro XDF plus the car's binary. Logs are MHD
Flasher CSVs. Generators: knock-based timing removal applied to every
timing map the DME may have been using (main 1 and 2, cold 1 and 2), and
a fuel scalar correction from the short term trim.
"""

from __future__ import annotations

import numpy as np

from ..core.winols import TargetMap
from ..generators import column
from ..generators.ignition_knock import DEFAULT_MIN_PULL, generate_knock_removal
from ..generators.scalar_correction import generate_scalar_correction
from .base import XDF_IMPORTER, Family, GeneratorSpec, ParamSpec, RunContext, mhd_log_source

TIMING_MAPS = {
    "timing_main": "Timing (main)",
    "timing_main2": "Timing (main) 2",
    "timing_cold": "Timing (cold)",
    "timing_cold2": "Timing (cold) 2",
}
FUEL_SCALAR = "Fuel scalar 1"
TIMING_STEP = 0.5
"""The timing maps store half degrees (equation X*0.5)."""
CYLINDERS = 6

DEFAULT_VARS = {
    "rpm": "RPM",
    "load": "Load actual RAM",
    "stft": "STFT 1",
    **{f"knock_cyl{i}": f"Cyl{i} Timing Cor" for i in range(1, CYLINDERS + 1)},
    "boost": "Boost",
    "boost_target": "Boost target",
    "boost_dev": "Boost deviation",
    "wgdc": "WGDC 1",
    "maf": "MAF",
    "maf_req": "MAF req. WGDC",
    "ratio_target": "Boost setpoint factor",
    "comp_base": "Compressor base",
    "comp_pd": "Compressor after P-D",
    "pedal": "Accel Ped. Pos.",
    "gear": "Gear",
    "tmot": "Coolant",
    "time": "Time",
}

VAR_LABELS = {
    "rpm": "Engine speed",
    "load": "Engine load (%)",
    "stft": "Short term trim (%)",
    **{f"knock_cyl{i}": f"Knock correction cyl {i}" for i in range(1, CYLINDERS + 1)},
    "boost": "Boost (bar)",
    "boost_target": "Boost target (bar)",
    "boost_dev": "Boost deviation (bar)",
    "wgdc": "Wastegate duty (%)",
    "maf": "Mass air flow (g/s)",
    "maf_req": "MAF requested for WGDC (g/s)",
    "ratio_target": "Boost setpoint ratio",
    "comp_base": "Compressor base power (kW)",
    "comp_pd": "Compressor power after P-D (kW)",
    "pedal": "Pedal position (%)",
    "gear": "Gear",
    "tmot": "Coolant temp",
    "time": "Time",
}

DEFAULT_PREP = {"align_timestamps": True, "hack_5120": False, "pressure_columns": []}

PARAMS = [
    ParamSpec("knock_source", "Knock signal", "choice", "average", group="Timing Knock Removal",
              choices=(("Average of all cylinders", "average"), ("Worst cylinder (largest retard)", "worst"))),
    ParamSpec("knock_min_samples", "Min samples per cell", "int", 1, group="Timing Knock Removal", minimum=0),
    ParamSpec("knock_step", "Timing step (deg)", "float", TIMING_STEP, group="Timing Knock Removal", decimals=3, minimum=0.001),
    ParamSpec("knock_min_pull", "Ignore average pull below (deg)", "float", DEFAULT_MIN_PULL,
              group="Timing Knock Removal", decimals=3, minimum=0),
    ParamSpec("fuel_min_samples", "Min samples per cell", "int", 2, group="Fuel Scalar Correction", minimum=0),
    ParamSpec("wot_min", "WOT minimum pedal (%)", "float", 80.0, group="Log Split", minimum=0, maximum=100),
]

TARGET_MAPS = [
    TargetMap(title, f"load_{key}", f"rpm_{key}", f"base_{key}", "Ignition Timing", direct=True)
    for key, title in TIMING_MAPS.items()
] + [
    TargetMap(FUEL_SCALAR, "load_fuel", "rpm_fuel", "base_fuel", "Fueling", direct=True),
    TargetMap("Compressor characteristic with required compressor / turbine power", "maf_comp", "ratio_comp",
              "base_comp", "Boost Control", direct=True),
    TargetMap("WGDC P factor", "maf_pfac", "ratio_pfac", "base_pfac", "Boost Control", direct=True),
    TargetMap("WGDC D-Factor", "grad_dfac", "dev_dfac", "base_dfac", "Boost Control", direct=True),
]


def knock_signal(data, v: dict[str, str], source: str) -> np.ndarray:
    """Per-row knock retard magnitude from the six cylinder corrections."""
    cols = [v[f"knock_cyl{i}"] for i in range(1, CYLINDERS + 1) if v.get(f"knock_cyl{i}") in data.columns]
    if not cols:
        raise KeyError("No cylinder timing correction channels in the logs (Cyl1 Timing Cor ...).")
    stack = np.abs(np.column_stack([data[c].to_numpy(float) for c in cols]))
    return stack.max(axis=1) if source == "worst" else stack.mean(axis=1)


def _timing(ctx: RunContext):
    p = ctx.preset
    d = ctx.logs.full
    knock = knock_signal(d, p.vars, str(ctx.p("knock_source", "average")))
    rpm, load = column(d, p.var("rpm")), column(d, p.var("load"))
    ctx.messages.append(f"Knock signal: {ctx.p('knock_source', 'average')} of {CYLINDERS} cylinders, "
                        f"{int((knock > 0).sum())} of {len(d)} rows with retard.")
    out = []
    for key, title in TIMING_MAPS.items():
        base = p.base_map(f"base_{key}")
        if base is None:
            ctx.messages.append(f"{title}: not imported, skipped.")
            continue
        out += generate_knock_removal(
            rpm, load, knock, base_map=base, base_title=title,
            axis_x=p.axis(f"rpm_{key}"), axis_y=p.axis(f"load_{key}"), x_label="RPM", y_label="Load %",
            min_samples=float(ctx.p("knock_min_samples", 1)), step=float(ctx.p("knock_step", TIMING_STEP)),
            min_pull=float(ctx.p("knock_min_pull", DEFAULT_MIN_PULL)), key=key, messages=ctx.messages,
        )
    return out


def _fuel(ctx: RunContext):
    p = ctx.preset
    d = ctx.logs.full
    return generate_scalar_correction(
        column(d, p.var("rpm")), column(d, p.var("load")), column(d, p.var("stft")),
        base_map=p.base_map("base_fuel"), base_title=FUEL_SCALAR,
        axis_x=p.axis("rpm_fuel"), axis_y=p.axis("load_fuel"), x_label="RPM", y_label="Load %",
        min_samples=float(ctx.p("fuel_min_samples", 2)), key="fuel", error_title="STFT Average (%)",
        messages=ctx.messages,
    )


BOSCH_MG1CS201 = Family(
    key="bosch_mg1cs201",
    display_name="Bosch MG1CS201 (MHD)",
    default_vars=DEFAULT_VARS,
    var_labels=VAR_LABELS,
    params=PARAMS,
    target_maps=TARGET_MAPS,
    log_sources=[mhd_log_source(required_channels=("rpm", "load"))],
    generators=[
        GeneratorSpec("timing", "Timing Knock Removal (main 1/2, cold 1/2)", ("full",),
                      ("rpm_timing_main", "load_timing_main"), _timing, required_base_maps=("base_timing_main",)),
        GeneratorSpec("fuel", "Fuel Scalar 1 from STFT", ("full",), ("rpm_fuel", "load_fuel"), _fuel,
                      required_base_maps=("base_fuel",)),
    ],
    map_importer=XDF_IMPORTER,
    default_prep=DEFAULT_PREP,
    show_pressure_hack=False,
    excel_sheet="MG1CS201 Maps",
    excel_default_name="MG1CS201_Tuning_Maps.xlsx",
)
