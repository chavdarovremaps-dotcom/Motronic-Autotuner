"""The MS43 turbo app: Siemens MS43 with the MS43X custom firmware on a
turbocharged M54, tuned in TunerPro RT with speed density, plus a Patches tab that writes
fixed patches (ICV delete, ...) into the binary through the XDF.

Rows with the coolant below the warm-engine threshold feed only the warm-up
correction; VE, ip_maf_1_diag and ignition use the warm rows.

Maps come from the MS43X XDF plus the car's binary. Logs are TunerPro RT
CSVs from the MS43X logging definition with the wideband channels added.
"""

from __future__ import annotations

from ..core.winols import TargetMap
from ..families.base import XDF_IMPORTER, Family, GeneratorSpec, LogSource, ParamSpec, RunContext
from . import ignition as ign
from . import warmup as wup
from .logs import read_log
from .maf_diag import TABLE as MAF_DIAG, generate_maf_diag
from .patch_tab import PatchTab
from .ve import VE_TABLES, channel, fuel_cut_window, generate_ve_correction, wideband_lag

FUEL_CUT_WINDOW = "Fuel Cut Window"
"""Column added at import: 1 in a fuel cut or shortly after it."""
START_COOLANT = "Coolant At Start"
TIME_AFTER_START = "Time After Start"
STEADY = "Steady State"
"""Columns added at import, per log file: coolant at the last engine start, seconds since it, 1 when rpm and load are steady."""

DEFAULT_VARS = {
    "rpm": "Engine Speed",
    "map": "Manifold Pressure",
    "load": "Engine Load Injection",
    "tps": "Throttle Body Position",
    "load_ign": "Engine Load Ignition",
    "knock": "Knock Correction Average",
    "part_load": "Part Load",
    "full_load": "Full Load",
    "idle": "Idle",
    "ve_table": "Active VE Table",
    "afr_target": "Air Fuel Ratio Target",
    "wideband_afr": "Wideband AFR",
    "wideband_v": "Downstream Lambda Sensor Input Bank 1",
    "stft_b1": "Short Term Fuel Trim Bank 1",
    "ltft_m_b1": "Long Term Fuel Trim Multiplicative Bank 1",
    "stft_b2": "Short Term Fuel Trim Bank 2",
    "ltft_m_b2": "Long Term Fuel Trim Multiplicative Bank 2",
    "lambda1": "Lambda Control 1",
    "lambda2": "Lambda Control 2",
    "fuel_cut": "Trailing Throttle Fuel Cut",
    "engine_start": "Engine Start",
    "warmup_flag": "Engine Warm Up",
    "ti": "Injection Time Average",
    "pedal": "Accelerator Pedal Position",
    "tmot": "Coolant Temperature",
    "time": "Time",
}

VAR_LABELS = {
    "rpm": "Engine speed",
    "map": "Manifold pressure (kPa)",
    "load": "Engine load (mg/stk)",
    "tps": "Throttle body position",
    "load_ign": "Engine load ignition (mg/stk)",
    "knock": "Knock correction average (deg)",
    "part_load": "Part load flag",
    "full_load": "Full load flag",
    "idle": "Idle flag",
    "ve_table": "Active VE table",
    "afr_target": "AFR target",
    "wideband_afr": "Wideband AFR",
    "wideband_v": "Wideband input voltage, optional (0 / 5 V rows dropped)",
    "stft_b1": "STFT bank 1 (%)",
    "ltft_m_b1": "LTFT multiplicative bank 1 (%)",
    "stft_b2": "STFT bank 2 (%)",
    "ltft_m_b2": "LTFT multiplicative bank 2 (%)",
    "lambda1": "Lambda control bank 1 (closed loop flag)",
    "lambda2": "Lambda control bank 2 (closed loop flag)",
    "fuel_cut": "Fuel cut flag",
    "engine_start": "Engine start flag (marks the start in a warm-up log)",
    "warmup_flag": "Engine warm-up flag, optional",
    "ti": "Injection time (ms), optional (warm-up formula check)",
    "pedal": "Pedal position",
    "tmot": "Coolant temp",
    "time": "Time",
}

PARAMS = [
    ParamSpec("wideband", "Wideband present in the logs", "bool", True, group="VE Correction"),
    ParamSpec("both_banks", "Average bank 1 and 2 trims", "bool", False, group="VE Correction"),
    ParamSpec("ve_min_samples", "Min samples per cell", "float", 2.0, group="VE Correction", decimals=1, minimum=0),
    ParamSpec("diag_min_samples", "Min samples per cell", "float", 2.0, group="MAF Substitute (ip_maf_1_diag)",
              decimals=1, minimum=0),
    ParamSpec("iga_step", "Timing step (deg)", "float", ign.STEP, group="Ignition (ip_iga_ron98_pl)", decimals=3,
              minimum=0.001),
    ParamSpec("iga_min_pull", "Ignore average retard below (deg)", "float", ign.MIN_PULL,
              group="Ignition (ip_iga_ron98_pl)", decimals=3, minimum=0),
    ParamSpec("iga_advance", "Advance cells without retard by (deg)", "float", ign.ADVANCE,
              group="Ignition (ip_iga_ron98_pl)", decimals=3, minimum=0),
    ParamSpec("iga_min_pull_samples", "Min samples to pull timing", "float", ign.MIN_PULL_SAMPLES,
              group="Ignition (ip_iga_ron98_pl)", decimals=1, minimum=0),
    ParamSpec("iga_min_advance_samples", "Min samples to add timing", "float", ign.MIN_ADVANCE_SAMPLES,
              group="Ignition (ip_iga_ron98_pl)", decimals=1, minimum=0),
    ParamSpec("wup_target", "Target lambda by coolant, linear between points, held beyond the ends", "curve",
              wup.DEFAULT_TARGET, group="Warm-up (ip_ti_tco_wup)", decimals=3, x_label="Coolant (C)",
              y_label="Lambda"),
    ParamSpec("wup_without_hot", "Rows whose VE cell has no warm data", "choice", wup.SKIP,
              group="Warm-up (ip_ti_tco_wup)",
              choices=(("Skip them", wup.SKIP), ("Assume the VE is right", wup.ASSUME))),
    ParamSpec("wup_min_samples", "Min samples per cell", "float", 2.0, group="Warm-up (ip_ti_tco_wup)",
              decimals=1, minimum=0),
    ParamSpec("wup_steady_rpm", "Steady: rpm change below (rpm/s)", "float", wup.STEADY_RPM_RATE,
              group="Warm-up (ip_ti_tco_wup)", decimals=0, minimum=0),
    ParamSpec("wup_steady_load", "Steady: load change below (mg/stk per s)", "float", wup.STEADY_LOAD_RATE,
              group="Warm-up (ip_ti_tco_wup)", decimals=0, minimum=0),
    ParamSpec("warm_engine", "Warm engine from coolant (C)", "float", wup.WARM_ENGINE, group="Filtering",
              decimals=1, minimum=-40, maximum=150),
    ParamSpec("fuel_cut_skip", "Skip after a fuel cut ends (s)", "float", 1.0, group="Filtering",
              decimals=2, minimum=0),
]

TARGET_MAPS = [
    TargetMap(f"ip_map_ve_{k}__map__n", "map_ve", "rpm_ve", f"base_ve_{k}", "Volumetric Efficiency", direct=True)
    for k in range(1, VE_TABLES + 1)
] + [
    TargetMap(MAF_DIAG, "rpm_maf_diag", "tps_maf_diag", "base_maf_diag", "Load", direct=True),
    TargetMap(ign.TABLE, "rpm_iga", "load_iga", "base_iga", "Ignition Timing", direct=True),
    TargetMap(wup.BASE, "rpm_wup", "load_wup", "base_wup", "Warm-up", direct=True),
    TargetMap(wup.FADE, "tco_fade", "tco_st_fade", "base_fade", "Warm-up", direct=True),
    TargetMap(wup.FADE_IS, "tco_fade_is", "tco_st_fade_is", "base_fade_is", "Warm-up", direct=True),
]


def mark_fuel_cut(df, preset, messages):
    """Import hook, per log file: flag fuel-cut rows and the rows just after,
    and report how far the wideband lags behind the fuel cuts."""
    v = preset.vars
    if v.get("fuel_cut") not in df.columns or v.get("time") not in df.columns:
        return df
    skip = float(preset.params.get("fuel_cut_skip", 1.0))
    time, cut = channel(df, v["time"]), channel(df, v["fuel_cut"])
    df[FUEL_CUT_WINDOW] = fuel_cut_window(time, cut, skip).astype(float)
    if v.get("wideband_afr") in df.columns:
        lags = sorted(wideband_lag(time, cut, channel(df, v["wideband_afr"])))
        if lags:
            messages.append(f"  -> Wideband reads lean {lags[len(lags) // 2]:.2f} s after a fuel cut starts "
                            f"(median of {len(lags)} cuts, {lags[0]:.2f} to {lags[-1]:.2f} s).")
    return df


def mark_warmup(df, preset, messages):
    """Import hook, per log file: coolant at start and seconds since it (from the
    Engine Start flag), and whether rpm and load are steady."""
    v, p = preset.vars, preset.params
    if v.get("time") not in df.columns or v.get("tmot") not in df.columns:
        return df
    time, cool = channel(df, v["time"]), channel(df, v["tmot"])
    flag = channel(df, v["engine_start"]) if v.get("engine_start") in df.columns else None
    t_ast, tco_st, found = wup.start_info(time, flag, cool)
    df[TIME_AFTER_START], df[START_COOLANT] = t_ast, tco_st
    if not found and (cool < float(p.get("warm_engine", wup.WARM_ENGINE))).any():
        messages.append(f"  -> No engine start in this file: coolant at start taken as the first logged "
                        f"value, {cool[0]:.1f} C.")
    if v.get("rpm") in df.columns and v.get("load") in df.columns:
        df[STEADY] = wup.steady_rows(
            time, channel(df, v["rpm"]), channel(df, v["load"]),
            max_rpm_rate=float(p.get("wup_steady_rpm", wup.STEADY_RPM_RATE)),
            max_load_rate=float(p.get("wup_steady_load", wup.STEADY_LOAD_RATE)),
        ).astype(float)
    return df


def warm_rows(ctx: RunContext, tag: str):
    """The logs without the rows whose coolant is below the warm-engine threshold."""
    d = ctx.logs.full
    col = ctx.preset.var("tmot")
    if col not in d.columns:
        return d
    limit = float(ctx.p("warm_engine", wup.WARM_ENGINE))
    keep = d[col].to_numpy(dtype=float) >= limit
    if not keep.all():
        ctx.messages.append(f"{tag}: {int((~keep).sum())} rows with coolant below {limit:g} C left out (warm-up).")
    return d[keep]


def _ve(ctx: RunContext):
    p = ctx.preset
    bases = {k: p.base_map(f"base_ve_{k}") for k in range(1, VE_TABLES + 1)}
    maps = generate_ve_correction(
        warm_rows(ctx, "VE"), p.vars,
        wideband=bool(ctx.p("wideband", True)), both_banks=bool(ctx.p("both_banks", False)),
        axis_rpm=p.axis("rpm_ve"), axis_map=p.axis("map_ve"),
        base_maps={k: b for k, b in bases.items() if b is not None},
        min_weight=float(ctx.p("ve_min_samples", 2.0)), skip_col=FUEL_CUT_WINDOW, messages=ctx.messages,
    )
    for m in maps:
        m.sheet = "Fueling"
    return maps


def _maf_diag(ctx: RunContext):
    p = ctx.preset
    maps = generate_maf_diag(
        warm_rows(ctx, MAF_DIAG), p.vars,
        wideband=bool(ctx.p("wideband", True)), both_banks=bool(ctx.p("both_banks", False)),
        axis_tps=p.axis("tps_maf_diag"), axis_rpm=p.axis("rpm_maf_diag"), base_map=p.base_map("base_maf_diag"),
        min_weight=float(ctx.p("diag_min_samples", 2.0)), skip_col=FUEL_CUT_WINDOW, messages=ctx.messages,
    )
    for m in maps:
        m.sheet = "Load"
    return maps


def _ignition(ctx: RunContext):
    p = ctx.preset
    maps = ign.generate_ignition(
        warm_rows(ctx, ign.TABLE), p.vars, base_map=p.base_map("base_iga"), axis_load=p.axis("load_iga"), axis_rpm=p.axis("rpm_iga"),
        step=float(ctx.p("iga_step", ign.STEP)), min_pull=float(ctx.p("iga_min_pull", ign.MIN_PULL)),
        advance=float(ctx.p("iga_advance", ign.ADVANCE)),
        min_pull_samples=float(ctx.p("iga_min_pull_samples", ign.MIN_PULL_SAMPLES)),
        min_advance_samples=float(ctx.p("iga_min_advance_samples", ign.MIN_ADVANCE_SAMPLES)),
        messages=ctx.messages,
    )
    for m in maps:
        m.sheet = "Ignition"
    return maps


def _warmup(ctx: RunContext):
    p = ctx.preset
    if not bool(ctx.p("wideband", True)):
        raise ValueError("The warm-up correction needs the wideband: closed loop aims at lambda 1, not the warm-up target.")
    target_tco, target_lambda = wup.target_curve(ctx.p("wup_target", wup.DEFAULT_TARGET))
    maps = wup.generate_warmup(
        ctx.logs.full, p.vars,
        base=p.base_map("base_wup"), axis_base_load=p.axis("load_wup"), axis_base_rpm=p.axis("rpm_wup"),
        fade=p.base_map("base_fade"), axis_fade_tco=p.axis("tco_fade"), axis_fade_tco_st=p.axis("tco_st_fade"),
        fade_is=p.base_map("base_fade_is"), axis_fade_is_tco=p.axis("tco_fade_is"),
        axis_fade_is_tco_st=p.axis("tco_st_fade_is"),
        axis_ve_rpm=p.axis("rpm_ve"), axis_ve_map=p.axis("map_ve"),
        warm_engine=float(ctx.p("warm_engine", wup.WARM_ENGINE)),
        target_tco=target_tco, target_lambda=target_lambda,
        without_hot=str(ctx.p("wup_without_hot", wup.SKIP)),
        min_weight=float(ctx.p("wup_min_samples", 2.0)), ve_min_weight=float(ctx.p("ve_min_samples", 2.0)),
        both_banks=bool(ctx.p("both_banks", False)),
        skip_col=FUEL_CUT_WINDOW, steady_col=STEADY, start_col=START_COOLANT, messages=ctx.messages,
    )
    for m in maps:
        m.sheet = "Warm-up"
    return maps


MS43_TURBO = Family(
    key="siemens_ms43x_turbo",
    display_name="Siemens MS43X Turbo",
    default_vars=DEFAULT_VARS,
    var_labels=VAR_LABELS,
    params=PARAMS,
    target_maps=TARGET_MAPS,
    log_sources=[LogSource("tunerpro", "TunerPro RT CSV (MS43X)", reader=read_log, hooks=(mark_fuel_cut, mark_warmup),
                           required_channels=("rpm", "map"))],
    generators=[
        GeneratorSpec("ve", "VE Correction", ("full",), ("rpm_ve", "map_ve"), _ve),
        GeneratorSpec("maf_diag", "MAF Substitute (ip_maf_1_diag)", ("full",), ("rpm_maf_diag", "tps_maf_diag"), _maf_diag),
        GeneratorSpec("ignition", "Ignition (ip_iga_ron98_pl)", ("full",), ("rpm_iga", "load_iga"), _ignition,
                      required_base_maps=("base_iga",)),
        GeneratorSpec("warmup", "Warm-up (ip_ti_tco_wup)", ("full",),
                      ("tco_fade", "tco_st_fade", "rpm_wup", "load_wup", "rpm_ve", "map_ve"), _warmup,
                      required_base_maps=("base_wup", "base_fade")),
    ],
    map_importer=XDF_IMPORTER,
    extra_tabs=[PatchTab],
    default_prep={"align_timestamps": False, "hack_5120": False, "pressure_columns": []},
    show_pressure_hack=False,
    excel_sheet="Fueling",
    excel_default_name="MS43X_Turbo_Tuning_Maps.xlsx",
)
