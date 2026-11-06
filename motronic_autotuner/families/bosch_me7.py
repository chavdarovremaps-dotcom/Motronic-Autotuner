"""Bosch ME7.x family (1.8T, Volvo, Opel ME7): the defaults, target maps and
generator set of the MATLAB MotronicTuner_GUI, minus its MED9.1 tab."""

from __future__ import annotations

import numpy as np

from ..core.logs import hack_5120
from ..core.maps import CalibrationMap
from ..core.winols import TargetMap, looks_like_rpm
from ..generators import axis_block, column
from ..generators.boost import DUTY_OUT_OF_REACH, detect_spool_rpm, generate_boost_maps, spool_rpm_axis
from ..generators.boost_pid import MIN_DUTY_STEP, MIN_LEVEL_SAMPLES, generate_pid_maps
from ..generators.fuel import generate_fkkvs
from ..generators.maf_check import DEFAULT_MIN_THROTTLE, DEFAULT_VE, DISPLACEMENT_1_8T, generate_maf_check
from ..generators.handover import generate_handover_maps
from ..generators.ignition import generate_kfzw
from ..generators.manifold import generate_manifold_maps, generate_pbrk_maps
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
    "maf": "ml_w",
    "iat": "tanslin",
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
    "maf": "Corrected airflow (ml_w; g/s, kg/h converted)",
    "iat": "Charge air temperature (tanslin)",
    "time": "Time",
}

DEFAULT_PREP = {
    "align_timestamps": True,
    "hack_5120": False,
    "pressure_columns": ["pvdks_w", "pu", "pssol_w", "pvdk_w", "plgru_w", "ps_w"],
}

GENERAL, BOOST, AIRFLOW = "General", "Boost", "Airflow"

LOG_SPLIT = [
    ParamSpec("wot_min", "WOT: pedal at least", "float", 70.0, section=GENERAL, group="Log split", unit="%",
              decimals=0, minimum=0, maximum=100,
              tip="Rows with the pedal at or above this are the WOT set: boost maps, PID and KFVPDKSD."),
    ParamSpec("temp_max", "Warm-up: coolant below", "float", 80.0, section=GENERAL, group="Log split", unit="C",
              decimals=0, tip="Rows under this coolant temperature are the warm-up set, the rest the hot set."),
]
TRANSIENTS = [
    ParamSpec("max_rpm_roc", "RPM change at most", "float", 1000.0, section=GENERAL, group="Transient filter",
              unit="rpm/s", decimals=0, minimum=0, tip="Rows where the rpm changes faster are dropped."),
    ParamSpec("max_throttle_roc", "Pedal change at most", "float", 33.0, section=GENERAL, group="Transient filter",
              unit="%/s", decimals=0, minimum=0, tip="Rows where the pedal moves faster are dropped."),
]
MAPS = [
    ParamSpec("min_samples", "Min samples per cell", "int", 1, section=GENERAL, group="Maps", minimum=0,
              tip="Fuel, warm-up, ignition, manifold model and MAF check: cells with less weight stay empty."),
    ParamSpec("trim_format", "Fuel trim format", "choice", "lambda", section=GENERAL, group="Maps",
              choices=(("Lambda (factor, e.g. 1.05)", "lambda"), ("Percent (e.g. 5)", "percent"))),
]
VVT = [
    ParamSpec("vvt_enabled", "Engine has VVT", "bool", False, section=GENERAL, group="VVT",
              tip="KFURL / KFPRG and KFPBRK / KFPBRKNW split by cam position."),
    ParamSpec("vvt_threshold", "Cam on above", "float", 18.0, section=GENERAL, group="VVT", unit="deg", decimals=1,
              tip="Cam position (wnwi_w) splitting the cam-off and cam-on rows, for the manifold model and KFZW."),
]
PRESSURE_REFERENCE = [
    ParamSpec("cwldimx", "Relative to logged pu (CWLDIMX)", "bool", False, section=BOOST, group="Pressure reference",
              tip="Relative boost = pvdks_w - pu. Off: pvdks_w minus the ambient pressure below."),
    ParamSpec("ambient_pressure", "Ambient pressure", "float", 1000.0, section=BOOST, group="Pressure reference",
              unit="hPa", decimals=0, minimum=0,
              tip="Relative boost when CWLDIMX is off, and the reference of the KFVPDKSD pressure ratio."),
]
KFLDRL = [
    ParamSpec("auto_axis_kfldrl", "Auto rpm axis around the spool", "bool", False, section=BOOST,
              group="KFLDRL / KFLDIMX",
              tip="Rebuilds the KFLDRL / KFLDIMX rpm axis: 5th point at the spool rpm, 250 rpm steps to the "
                  "10th point, 500 rpm steps after it."),
    ParamSpec("spool_boost_share", "Spool: share of the peak boost", "float", 90.0, section=BOOST,
              group="KFLDRL / KFLDIMX", unit="%", decimals=0, minimum=50, maximum=100,
              tip="The spool is where the boost first reaches this share of the peak. Used by the auto axis, "
                  "the KFLDRL finish and the PID."),
    ParamSpec("kfldrl_method", "Cells from", "choice", "rows", section=BOOST, group="KFLDRL / KFLDIMX",
              choices=(("Each rpm row between the logged duty levels", "rows"),
                       ("Bilinear splat (old)", "splat")),
              tip="Rows: the duty for a column's boost is interpolated between the duty levels logged at that "
                  "rpm, so one forced level no longer fills two columns with the same duty."),
    ParamSpec("kfldrl_level_samples", "Min samples per duty level and rpm", "float", 3.0, section=BOOST,
              group="KFLDRL / KFLDIMX", decimals=0, minimum=0,
              tip="A duty level counts at an rpm point with at least this weight; drops stray rows such as a "
                  "duty change while the boost still lags."),
    ParamSpec("min_samples_base_wg", "Min samples per cell", "int", 1, section=BOOST, group="KFLDRL / KFLDIMX",
              minimum=0, tip="The splat KFLDRL, the absolute WGDC map and the base-WG curve behind KFVPDKSD."),
    ParamSpec("kfldrl_finish", "Finish the map", "bool", True, section=BOOST, group="KFLDRL finish",
              tip="Column 0 at 0 %, every row rising with the target, empty cells by spool region: 95 % below "
                  "the spool, the spooled row's duties on the row just below it, the highest logged duty above it."),
    ParamSpec("kfldrl_out_of_reach", "Below the spool, unreached targets", "float", 95.0, section=BOOST,
              group="KFLDRL finish", unit="%", decimals=1, minimum=0, maximum=95,
              enabled_when=("kfldrl_finish", True),
              tip="Duty for the targets a row below the spool never reached: gate shut for the fastest spool. "
                  "The first such cell is bridged at the duty the turbo holds after the spool."),
    ParamSpec("fill_missing_data", "Fill empty cells by interpolation (old)", "bool", False, section=BOOST,
              group="KFLDRL finish", enabled_when=("kfldrl_finish", False),
              tip="Only with the finish off: linear inside the data, nearest outside it, last column 100 %."),
]
KFVPDKSD = [
    ParamSpec("auto_axis_kfvp", "Auto pressure-ratio axis", "bool", False, section=BOOST, group="KFVPDKSD",
              tip="0.95, 1.0, then even steps to 1.2 x the base-WG peak ratio; rows under 1.2 stay stock."),
]
PID = [
    ParamSpec("ldr_mode", "KFLDRQ0 / Q1 / Q2", "choice", "sensitivity", section=BOOST, group="Boost PID",
              choices=(("P from the boost sensitivity (I, D unchanged)", "sensitivity"),
                       ("P, I, D x duty ratio logs / file, one ratio", "overall"),
                       ("P, I, D x duty ratio logs / file, per rpm", "per_rpm"))),
    ParamSpec("ldr_min_samples", "Min samples per duty level and rpm", "float", MIN_LEVEL_SAMPLES, section=BOOST,
              group="Boost PID", decimals=0, minimum=0, enabled_when=("ldr_mode", "sensitivity")),
    ParamSpec("ldr_min_duty_step", "Compare duties at least", "float", MIN_DUTY_STEP, section=BOOST,
              group="Boost PID", unit="% apart", decimals=1, minimum=0.5, maximum=50,
              enabled_when=("ldr_mode", "sensitivity")),
    ParamSpec("ldr_min_file_duty", "KFLDRL cells with file duty from", "float", 20.0, section=BOOST,
              group="Boost PID", unit="%", decimals=0, minimum=0, maximum=100,
              enabled_when=("ldr_mode", ("overall", "per_rpm")),
              tip="Duty ratio logs / file: only KFLDRL cells where the file's duty is at least this."),
]
MANIFOLD = [
    ParamSpec("fit_load_max", "Fit KFURL / KFPRG on loads up to", "float", 0.0, section=AIRFLOW,
              group="Intake manifold model", unit="%", decimals=0, minimum=0, maximum=400, tip="0 = all loads."),
    ParamSpec("pbrk_apply", "KFPBRK factor acts on", "choice", "pressure", section=AIRFLOW,
              group="Intake manifold model",
              choices=(("Pressure: rl = (ps x f - KFPRG) x KFURL", "pressure"),
                       ("Load: rl = (ps - KFPRG) x KFURL x f", "load")),
              tip="Pressure: on the manifold pressure before the residual gas is taken off. Load: on the result."),
]
MAF = [
    ParamSpec("maf_ve", "Reference VE", "float", DEFAULT_VE, section=AIRFLOW, group="MAF check (information only)",
              unit="%", decimals=0, minimum=10, maximum=150),
    ParamSpec("maf_displacement", "Displacement", "float", DISPLACEMENT_1_8T, section=AIRFLOW,
              group="MAF check (information only)", unit="cc", decimals=0, minimum=100, maximum=10000),
    ParamSpec("maf_min_throttle", "Throttle at least", "float", DEFAULT_MIN_THROTTLE, section=AIRFLOW,
              group="MAF check (information only)", unit="%", decimals=0, minimum=0, maximum=100,
              tip="Only rows with the throttle (wdkba) at or above this: the check needs a wide-open throttle."),
]

PARAMS = LOG_SPLIT + TRANSIENTS + MAPS + VVT + PRESSURE_REFERENCE + KFLDRL + KFVPDKSD + PID + MANIFOLD + MAF

TARGET_MAPS = [
    TargetMap("KFLDIMX", "rpm_boost", "boost", "base_kfldimx", "Boost Control"),
    TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "Boost Control"),
    TargetMap("KFVPDKSD", "rpm_kfvp", "pratio_kfvp", "base_kfvp", "Throttle Handover", direct=True),
    TargetMap("KFLDRQ0", "rpm_kfldrq0", "x_kfldrq0", "base_kfldrq0", "Boost PID"),
    TargetMap("KFLDRQ1", "rpm_kfldrq1", "x_kfldrq1", "base_kfldrq1", "Boost PID"),
    TargetMap("KFLDRQ2", "rpm_kfldrq2", "x_kfldrq2", "base_kfldrq2", "Boost PID"),
    TargetMap("LDRQ1ST", "row_ldrq1st", "rpm_ldrq1st", "base_ldrq1st", "Boost PID"),
    TargetMap("LDRQ0DY", "row_ldrq0dy", "rpm_ldrq0dy", "base_ldrq0dy", "Boost PID (512 kB layout)"),
    TargetMap("LDRQ1DY", "row_ldrq1dy", "rpm_ldrq1dy", "base_ldrq1dy", "Boost PID (512 kB layout)"),
    TargetMap("FKKVS", "rpm_fuel", "te", "base_fkkvs", "Fueling"),
    TargetMap("KFKHFM", "rpm_kfkhfm", "load_kfkhfm", "base_kfkhfm", "MAF Check"),
    TargetMap("KFFWLW", "rpm_kffwlw", "load_kffwlw", "base_kffwlw", "Warmup Enrichment"),
    TargetMap("KFFWL", "tmot", "kffwl_trim", "base_kffwl", "Warmup Enrichment"),
    TargetMap("KFZW", "rpm_ign", "load_ign", "base_kfzw", "Ignition Timing"),
    TargetMap("KFPBRK", "rpm_pbrk", "load_pbrk", "base_kfpbrk", "Saugrohrmodell"),
    TargetMap("KFPBRKNW", "rpm_pbrknw", "load_pbrknw", "base_kfpbrknw", "Saugrohrmodell"),
    TargetMap("KFPRG", "rpm_prg", "vvt_prg", "base_kfprg", "Saugrohrmodell"),
    TargetMap("KFURL", "rpm_url", "vvt_url", "base_kfurl", "Saugrohrmodell"),
    TargetMap("URLNM", "row_urlnm", "rpm_urlnm", "base_urlnm", "Saugrohrmodell (512 kB layout)"),
    TargetMap("PRGNM", "row_prgnm", "rpm_prgnm", "base_prgnm", "Saugrohrmodell (512 kB layout)"),
]
"""A 1 MB ME7.5 (VVT, KFURL / KFPRG by cam, KFLDRQ0 / Q1 maps) carries the first set; a 512 kB one
(06A906032S, SW 352760) has URLNM / PRGNM curves over rpm and LDRQ0DY / LDRQ1DY curves instead, and no
KFPBRKNW. The maps of the other layout are reported missing and the generators take what is there."""


# ---- generator wrappers: read the preset, call the pure math ------------------


def _on_sheet(maps, sheet: str):
    for m in maps:
        m.sheet = sheet
    return maps


def _spool(ctx: RunContext, d):
    """Spool rpm of the WOT rows, relative boost against logged pu (CWLDIMX) or the ambient parameter."""
    p = ctx.preset
    ref = column(d, p.var("pu")) if bool(ctx.p("cwldimx", False)) else float(ctx.p("ambient_pressure", 1000))
    return detect_spool_rpm(column(d, p.var("rpm")), column(d, p.var("boost")) - ref,
                            share=float(ctx.p("spool_boost_share", 90)))


def _boost(ctx: RunContext, *, data=None, reference_column: str | None = None,
           reference_label: str = "Target Rel Boost (mbar)", axis_boost=None, blocks=None):
    """KFLDIMX / KFLDRL; with the auto-axis tick the rpm axis is rebuilt around
    the spool point found in the WOT rows and written out as a block. A
    family without the KFLDRL method / finish settings keeps the splat. A
    family wrapper may pass its own WOT rows, the column the boost is
    measured from, a KFLDIMX axis and blocks to put first (ME7.6.2)."""
    p = ctx.preset
    d = ctx.logs.wot if data is None else data
    cwldimx = bool(ctx.p("cwldimx", False))
    ambient = float(ctx.p("ambient_pressure", 1000))
    axis_rpm = p.axis("rpm_boost")
    blocks = list(blocks or [])
    if bool(ctx.p("auto_axis_kfldrl", False)):
        spool, info = _spool(ctx, d)
        if spool is None:
            ctx.messages.append(f"Auto axis KFLDRL: no spool point found in {info.get('rows', 0)} WOT rows, "
                                "factory axis kept.")
        else:
            axis_rpm = spool_rpm_axis(spool)
            ctx.messages.append(
                f"Auto axis KFLDRL / KFLDIMX: spool at {spool:.0f} rpm, where the median relative boost reaches "
                f"{info['boost_at_spool']:.0f} hPa ({info['share']:g} % of the {info['peak']:.0f} hPa peak at "
                f"{info['peak_rpm']:.0f} rpm, {info['rows']} WOT rows); axis {', '.join(f'{a:g}' for a in axis_rpm)}.")
            blocks.append(axis_block("rpm_axis_boost", "KFLDRL / KFLDIMX RPM axis (paste into WinOLS)", axis_rpm, "RPM"))
    maps = generate_boost_maps(
        d, p.vars,
        cwldimx=cwldimx, ambient_pressure=ambient,
        min_samples=float(ctx.p("min_samples_base_wg", 1)),
        fill_missing=bool(ctx.p("fill_missing_data", False)),
        axis_rpm=axis_rpm, axis_boost=p.axis("boost") if axis_boost is None else axis_boost,
        axis_kfldrl_x=p.axis("kfldrl_x"),
        method=str(ctx.p("kfldrl_method", "splat")), finish=bool(ctx.p("kfldrl_finish", False)),
        spool_share=float(ctx.p("spool_boost_share", 90)),
        out_of_reach=float(ctx.p("kfldrl_out_of_reach", DUTY_OUT_OF_REACH)),
        level_min_samples=float(ctx.p("kfldrl_level_samples", 3)),
        reference_column=reference_column, reference_label=reference_label, messages=ctx.messages,
    )
    return _on_sheet(blocks + maps, "Boost")


Q_MAPS = ("KFLDRQ0", "KFLDRQ1", "KFLDRQ2")
Q_CURVES = ("LDRQ0DY", "LDRQ1DY", "LDRQ1ST")
PID_LAYOUTS = {
    "KFLDRQ0": ("KFLDRQ0", "KFLDRQ1", "KFLDRQ2", "LDRQ1ST"),
    "LDRQ0DY": ("LDRQ0DY", "LDRQ1DY", "LDRQ1ST", "KFLDRQ2"),
}
"""The maps each layout expects, keyed by its P map: 1 MB (maps) and 512 kB (curves)."""


def _pid(ctx: RunContext):
    """The LDR PID gains on the KFLDRL rpm axis: KFLDRQ0 / Q1 / Q2 and LDRQ1ST
    (one shared ROM axis), or in the 512 kB layout LDRQ0DY / LDRQ1DY / LDRQ1ST
    (shared axis) and KFLDRQ2 (its own). P from the boost sensitivity, or all
    gains by the duty ratio."""
    p = ctx.preset
    kfldrl = ctx.map("kfldrl")
    if kfldrl is None:
        ctx.messages.append("Boost PID: KFLDRL was not calculated, so there is no rpm axis to move the maps onto.")
        return []
    q_maps, curves = {}, {}
    for name in Q_MAPS:
        key = name.lower()
        base, a_rpm, a_dev = p.base_map(f"base_{key}"), p.axis(f"rpm_{key}"), p.axis(f"x_{key}")
        if base is not None and a_rpm is not None and a_dev is not None:
            q_maps[name] = (base, a_rpm, a_dev)
    for name in Q_CURVES:
        key = name.lower()
        base, a_rpm = p.base_map(f"base_{key}"), p.axis(f"rpm_{key}")
        if base is not None and a_rpm is not None:
            curves[name] = (base, a_rpm)
    layout = "KFLDRQ0" if "KFLDRQ0" in q_maps else "LDRQ0DY"
    for name in PID_LAYOUTS[layout]:
        if name not in q_maps and name not in curves:
            ctx.messages.append(f"Boost PID: {name} not imported; if it shares the rpm axis with {layout}, "
                                "it has to be moved onto the new axis by hand.")
    d = ctx.logs.wot
    mode = str(ctx.p("ldr_mode", "sensitivity"))
    spool = _spool(ctx, d)[0] if mode == "sensitivity" else None
    return _on_sheet(generate_pid_maps(
        axis_rpm=np.asarray(kfldrl.y_axis, dtype=float), q_maps=q_maps, curves=curves, mode=mode,
        logs_rpm=column(d, p.var("rpm")), logs_boost=column(d, p.var("boost")), logs_duty=column(d, p.var("wgdc")),
        spool_rpm=spool, kfldrl=kfldrl, factory_kfldrl=p.base_map("base_kfldrl"),
        factory_axis_rpm=p.axis("rpm_boost"), factory_axis_x=p.axis("kfldrl_x"),
        min_samples=float(ctx.p("ldr_min_samples", MIN_LEVEL_SAMPLES)),
        min_step=float(ctx.p("ldr_min_duty_step", MIN_DUTY_STEP)),
        min_file_duty=float(ctx.p("ldr_min_file_duty", 20)), messages=ctx.messages,
    ), "Boost")


def _handover(ctx: RunContext):
    p = ctx.preset
    return _on_sheet(generate_handover_maps(
        ctx.logs.wot, p.vars,
        min_samples_base_wg=float(ctx.p("min_samples_base_wg", 1)),
        ambient_pressure=float(ctx.p("ambient_pressure", 1000)),
        axis_rpm=p.axis("rpm_kfvp"), axis_pratio=p.axis("pratio_kfvp"),
        auto_axis=bool(ctx.p("auto_axis_kfvp", False)),
        base_map=p.base_map("base_kfvp"), base_axis_rpm=p.axis("rpm_kfvp"), base_axis_pratio=p.axis("pratio_kfvp"),
        messages=ctx.messages,
    ), "Boost")


def _warmup(ctx: RunContext):
    p = ctx.preset
    return _on_sheet(generate_warmup_maps(
        ctx.logs.warmup, ctx.logs.full, p.vars,
        min_samples=float(ctx.p("min_samples", 1)),
        trim_format=str(ctx.p("trim_format", "lambda")),
        axis_tmot=p.axis("tmot"), axis_load=p.axis("load_kffwlw"), axis_rpm=p.axis("rpm_kffwlw"),
        hot_temp=float(ctx.p("temp_max", 80)),
        messages=ctx.messages,
    ), "Fueling")


def _fuel(ctx: RunContext):
    p = ctx.preset
    return _on_sheet(generate_fkkvs(
        ctx.logs.hot, p.vars,
        min_samples=float(ctx.p("min_samples", 1)),
        trim_format=str(ctx.p("trim_format", "lambda")),
        axis_rpm=p.axis("rpm_fuel"), axis_te=p.axis("te"),
    ), "Fueling")


def _ignition(ctx: RunContext):
    p = ctx.preset
    return _on_sheet(generate_kfzw(
        ctx.logs.full, p.vars,
        min_samples=float(ctx.p("min_samples", 1)),
        axis_rpm=p.axis("rpm_ign"), axis_load=p.axis("load_ign"),
        vvt_split=float(ctx.p("vvt_threshold", 18)),
    ), "Ignition")


def _manifold(ctx: RunContext):
    """KFURL and KFPRG from the linear fit, then KFPBRK / KFPBRKNW from its residual
    when the correction map axes were imported. A file with URLNM / PRGNM in
    place of KFURL / KFPRG goes to :func:`_manifold_curves`."""
    p = ctx.preset
    if p.axis("rpm_url") is None and p.axis("rpm_urlnm") is not None:
        return _manifold_curves(ctx)
    min_samples = float(ctx.p("min_samples", 1))
    vvt_enabled = bool(ctx.p("vvt_enabled", False))
    vvt_threshold = float(ctx.p("vvt_threshold", 18))
    maps = generate_manifold_maps(
        ctx.logs.full, p.vars,
        min_samples=min_samples, vvt_enabled=vvt_enabled, vvt_threshold=vvt_threshold,
        axis_rpm=p.axis("rpm_url"), fit_load_max=float(ctx.p("fit_load_max", 0)),
        messages=ctx.messages,
    )
    axis_rpm_pbrk, axis_load_pbrk = p.axis("rpm_pbrk"), p.axis("load_pbrk")
    if axis_rpm_pbrk is None or axis_load_pbrk is None:
        ctx.messages.append("  KFPBRK: axes rpm_pbrk / load_pbrk not imported, correction maps skipped.")
    else:
        by = {m.key: m for m in maps}
        maps += generate_pbrk_maps(
            ctx.logs.full, p.vars,
            kfurl=by["kfurl"].values, kfprg=by["kfprg"].values, axis_rpm_fit=p.axis("rpm_url"),
            vvt_enabled=vvt_enabled, vvt_threshold=vvt_threshold,
            axis_rpm=axis_rpm_pbrk, axis_load=axis_load_pbrk, base_map=p.base_map("base_kfpbrk"),
            axis_rpm_nw=p.axis("rpm_pbrknw"), axis_load_nw=p.axis("load_pbrknw"),
            base_map_nw=p.base_map("base_kfpbrknw"),
            min_samples=min_samples, apply_to=str(ctx.p("pbrk_apply", "pressure")),
            messages=ctx.messages,
        )
    _kfprg_on_its_axis(maps, p.axis("rpm_url"), p.axis("rpm_prg"), ctx.messages)
    return _on_sheet(maps, "Airflow")


NM_PAD_STEP = 5.0
"""URLNM / PRGNM hold 30 points; the 512 kB file fills the tail with 1 rpm steps after its last real point."""
KFPBRK_LOAD_TOP = 400.0
"""A KFPBRK load axis reaching past this is the unused default of the file, not a range anyone drives."""


def real_points(axis) -> int:
    """How many points of a curve axis come before the padding (steps of NM_PAD_STEP or less)."""
    small = np.flatnonzero(np.diff(np.asarray(axis, dtype=float).ravel()) <= NM_PAD_STEP)
    return int(small[0]) + 1 if small.size else int(np.asarray(axis).size)


def _rpm_of_prgnm(axis_prg, axis_url, messages: list[str]):
    """The rpm of each PRGNM point. The 512 kB map pack defines PRGNM's axis with
    factor 0.1 and kg/h (280 .. 2400): the same bytes as URLNM's rpm axis, read
    0.4 times too small. An axis proportional to URLNM's is taken as URLNM's."""
    a, u = np.asarray(axis_prg, dtype=float).ravel(), np.asarray(axis_url, dtype=float).ravel()
    if looks_like_rpm(a[: real_points(a)]):
        return a
    if a.size == u.size and np.all(u > 0):
        ratio = a / u
        if np.allclose(ratio, ratio[0], rtol=1e-3):
            messages.append(f"  PRGNM: its axis in this export reads {a[0]:g} .. {a[real_points(a) - 1]:g} "
                            f"(x {ratio[0]:.2f} of URLNM's rpm axis, the same data with a wrong factor in the map "
                            "pack); its points are taken at URLNM's rpm.")
            return u
    messages.append("  PRGNM: its axis is neither rpm nor URLNM's, PRGNM not calculated.")
    return None


def _curve(fitted, fit_rpm, base, base_rpm, n_real: int) -> tuple[np.ndarray, int]:
    """A paste-ready curve on ``base_rpm``: the fit where it has a value (linear in
    rpm between fitted points), the file's value elsewhere, the padded tail equal
    to the last real point. Returns the curve and how many real points came from the fit."""
    fitted, fit_rpm = np.asarray(fitted, dtype=float).ravel(), np.asarray(fit_rpm, dtype=float).ravel()
    base, base_rpm = np.asarray(base, dtype=float).ravel(), np.asarray(base_rpm, dtype=float).ravel()
    out = base.copy()
    ok = np.isfinite(fitted)
    n_fit = 0
    if ok.any():
        inside = (base_rpm[:n_real] >= fit_rpm[ok].min()) & (base_rpm[:n_real] <= fit_rpm[ok].max())
        out[:n_real][inside] = np.interp(base_rpm[:n_real][inside], fit_rpm[ok], fitted[ok])
        n_fit = int(inside.sum())
    out[n_real:] = out[n_real - 1]
    return out, n_fit


def _manifold_curves(ctx: RunContext):
    """The manifold model of a 512 kB ME7.5 without cam-dependent maps: URLNM
    (ps -> rl factor) and PRGNM (residual gas pressure), curves over rpm. The
    line is fitted on URLNM's real points as KFURL / KFPRG are; points without
    a fit keep the file's value. KFPBRK follows from the residual as usual."""
    p = ctx.preset
    msgs = ctx.messages
    min_samples = float(ctx.p("min_samples", 1))
    vvt_threshold = float(ctx.p("vvt_threshold", 18))
    axis_url, base_url = p.axis("rpm_urlnm"), p.base_map("base_urlnm")
    n_url = real_points(axis_url)
    fit_rpm = np.asarray(axis_url, dtype=float)[:n_url]
    fit = {m.key: m for m in generate_manifold_maps(
        ctx.logs.full, p.vars, min_samples=min_samples, vvt_enabled=False, vvt_threshold=vvt_threshold,
        axis_rpm=fit_rpm, fit_load_max=float(ctx.p("fit_load_max", 0)), messages=msgs)}
    url_fit, prg_fit = fit["kfurl"].values[:, 0], fit["kfprg"].values[:, 0]
    counts = fit["kfurl"].counts[:, 0]

    maps = []
    url, n_fit = _curve(url_fit, fit_rpm, base_url, axis_url, n_url)
    msgs.append(f"  URLNM: {n_url} real points of {np.asarray(axis_url).size} ({fit_rpm[0]:g} .. {fit_rpm[-1]:g} rpm, "
                f"the rest padding); {n_fit} from the logs, the others keep the file's value.")
    maps.append(CalibrationMap("urlnm", "URLNM: ps -> rl factor by rpm (% / hPa, paste into WinOLS)", url,
                               np.asarray(axis_url, dtype=float), ["URLNM"],
                               counts=np.r_[counts, np.zeros(np.asarray(axis_url).size - n_url)],
                               counts_title="URLNM / PRGNM - ROWS PER RPM POINT"))
    prg_model = None
    axis_prg, base_prg = p.axis("rpm_prgnm"), p.base_map("base_prgnm")
    if axis_prg is None or base_prg is None:
        msgs.append("  PRGNM not imported: KFPBRK uses the fitted residual gas pressure where it has one.")
        prg_model = np.where(np.isfinite(prg_fit), prg_fit, np.nanmean(prg_fit) if np.isfinite(prg_fit).any() else 0.0)
    else:
        prg_rpm = _rpm_of_prgnm(axis_prg, axis_url, msgs)
        if prg_rpm is not None:
            n_prg = real_points(prg_rpm)
            prg, n_fit = _curve(prg_fit, fit_rpm, base_prg, prg_rpm, n_prg)
            msgs.append(f"  PRGNM: {n_fit} of {n_prg} real points from the logs, the others keep the file's value.")
            maps.append(CalibrationMap("prgnm", "PRGNM: residual gas pressure by rpm (hPa, paste into WinOLS)", prg,
                                       np.asarray(axis_prg, dtype=float), ["PRGNM"]))
            prg_model = np.interp(fit_rpm, prg_rpm[:n_prg], prg[:n_prg])
    url_model = np.interp(fit_rpm, np.asarray(axis_url, dtype=float)[:n_url], url[:n_url])

    axis_rpm_pbrk, axis_load_pbrk = p.axis("rpm_pbrk"), p.axis("load_pbrk")
    if axis_rpm_pbrk is None or axis_load_pbrk is None or prg_model is None:
        msgs.append("  KFPBRK: its axes or the residual gas pressure are missing, correction map skipped.")
    else:
        base_pbrk = p.base_map("base_kfpbrk")
        if float(np.max(axis_load_pbrk)) > KFPBRK_LOAD_TOP:
            unity = base_pbrk is not None and bool(np.allclose(base_pbrk, 1.0))
            msgs.append(f"  [WARNING] KFPBRK's axes in this file run to {np.max(axis_rpm_pbrk):g} rpm and "
                        f"{np.max(axis_load_pbrk):g} % load{', all 1.0' if unity else ''}: the unused default, not a "
                        "driven range. The correction below is on those axes; give KFPBRK real axes in WinOLS "
                        "(e.g. 700 .. 6500 rpm, 50 .. 140 % load as in the 1 MB files) and import again.")
        maps += generate_pbrk_maps(
            ctx.logs.full, p.vars, kfurl=url_model[:, None], kfprg=prg_model[:, None], axis_rpm_fit=fit_rpm,
            vvt_enabled=False, vvt_threshold=vvt_threshold, axis_rpm=axis_rpm_pbrk, axis_load=axis_load_pbrk,
            base_map=base_pbrk, min_samples=min_samples, apply_to=str(ctx.p("pbrk_apply", "pressure")),
            messages=msgs)
    return _on_sheet(maps, "Airflow")


def _kfprg_on_its_axis(maps, axis_url, axis_prg, messages: list[str]) -> None:
    """KFPRG is fitted on the KFURL rpm axis. Where the file gives KFPRG an rpm
    axis of its own (ME7.6.2 KFPRGE: 24 points from 0 rpm against KFURLE's
    from 700), the fitted values move onto it, linear in rpm and held at the
    ends, so the block pastes as it stands."""
    kfprg = next((m for m in maps if m.key == "kfprg"), None)
    if kfprg is None or axis_url is None or axis_prg is None:
        return
    axis_url, axis_prg = np.asarray(axis_url, dtype=float), np.asarray(axis_prg, dtype=float)
    if np.array_equal(axis_url, axis_prg):
        return
    values = np.asarray(kfprg.values, dtype=float)
    moved = np.full((axis_prg.size, values.shape[1]), np.nan)
    for c in range(values.shape[1]):
        ok = np.isfinite(values[:, c])
        if ok.any():
            moved[:, c] = np.interp(axis_prg, axis_url[ok], values[ok, c])
    kfprg.values, kfprg.y_axis, kfprg.counts = moved, axis_prg, None
    messages.append(f"  KFPRG moved from the KFURL rpm axis ({axis_url.size} points) onto its own "
                    f"({axis_prg.size} points, {axis_prg[0]:g} to {axis_prg[-1]:g} rpm), held flat past the fitted range.")


def _maf_check(ctx: RunContext):
    """ml_w against the airflow at the reference VE, on the KFKHFM grid. Information only."""
    p = ctx.preset
    return _on_sheet(generate_maf_check(
        ctx.logs.full, p.vars, axis_rpm=p.axis("rpm_kfkhfm"), axis_load=p.axis("load_kfkhfm"),
        base_map=p.base_map("base_kfkhfm"), displacement_cc=float(ctx.p("maf_displacement", DISPLACEMENT_1_8T)),
        ve_pct=float(ctx.p("maf_ve", DEFAULT_VE)), min_throttle=float(ctx.p("maf_min_throttle", DEFAULT_MIN_THROTTLE)),
        min_samples=float(ctx.p("min_samples", 1)), messages=ctx.messages,
    ), "Airflow")


def airflow_to_grams(df, preset, messages):
    """Ingest hook: an airflow logged in kg/h (the logger's units row says so) becomes g/s."""
    col = preset.var("maf")
    if not col or col not in df.columns:
        return df
    unit = str(df.attrs.get("units", {}).get(col, "")).lower().replace(" ", "")
    if unit in ("kg/h", "kg/hr", "kgh"):
        df[col] = df[col] / 3.6
        messages.append(f"  -> {col} logged in kg/h, converted to g/s.")
    return df


def _apply_5120_scaling(ctx: RunContext, result: RunResult) -> None:
    """With the 5120 hack on, logged pressures were doubled: KFURL (URLNM) doubles and KFPRG (PRGNM) halves."""
    if not ctx.preset.prep.get("hack_5120", False):
        return
    for url_key, prg_key in (("kfurl", "kfprg"), ("urlnm", "prgnm")):
        url, prg = result.map(url_key), result.map(prg_key)
        if url is None or prg is None:
            continue
        url.values = np.asarray(url.values) * 2.0
        prg.values = np.asarray(prg.values) / 2.0
        a, b = url_key.upper(), prg_key.upper()
        ctx.messages.append(f"  [INFO] 5120 Hack Enabled: {a} multiplied by 2, {b} divided by 2.")
        idx = next(i for i, r in enumerate(result.rows) if r.map_key == url_key)
        result.rows.insert(idx, StatusRow("5120 Patch", "Applied", f"{a}*2, {b}/2"))


GENERATORS = [
    GeneratorSpec("boost", "Boost Control (KFLDIMX / KFLDRL)", ("wot",), ("rpm_boost", "boost", "kfldrl_x"), _boost),
    GeneratorSpec("pid", "Boost PID (KFLDRQ0 / Q1 / Q2 or LDRQ0DY / LDRQ1DY, LDRQ1ST on the KFLDRL axis)", ("wot",),
                  ("rpm_boost", "kfldrl_x", ("rpm_kfldrq0", "rpm_ldrq0dy")), _pid,
                  required_base_maps=(("base_kfldrq0", "base_ldrq0dy"),)),
    GeneratorSpec("handover", "Throttle Handover (KFVPDKSD)", ("wot",), ("rpm_kfvp", "pratio_kfvp"), _handover),
    GeneratorSpec("warmup", "Warmup Enrichment (KFFWL / KFFWLW)", ("warmup", "full"),
                  ("rpm_kffwlw", "load_kffwlw", "tmot"), _warmup),
    GeneratorSpec("fuel", "Fuel Trim (FKKVS)", ("hot",), ("rpm_fuel", "te"), _fuel),
    GeneratorSpec("ignition", "Ignition Timing (KFZW)", ("full",), ("rpm_ign", "load_ign"), _ignition),
    GeneratorSpec("manifold", "Intake Manifold Model (KFURL / KFPRG or URLNM / PRGNM, KFPBRK)", ("full",),
                  (("rpm_url", "rpm_urlnm"),), _manifold),
    GeneratorSpec("maf", "MAF Check (ml_w vs reference VE, KFKHFM axes, information only)", ("full",),
                  ("rpm_kfkhfm", "load_kfkhfm"), _maf_check),
]

BOSCH_ME7 = Family(
    key="bosch_me7",
    display_name="Bosch ME7",
    default_vars=DEFAULT_VARS,
    var_labels=VAR_LABELS,
    params=PARAMS,
    target_maps=TARGET_MAPS,
    log_sources=[LogSource("me7_logger", "ME7-Logger / TunerPro CSV", hooks=(hack_5120, airflow_to_grams))],
    generators=GENERATORS,
    post_process=[_apply_5120_scaling],
    default_prep=DEFAULT_PREP,
    excel_sheet="Boost",
)
