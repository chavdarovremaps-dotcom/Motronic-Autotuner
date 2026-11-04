"""Bosch ME7.6.2 (Opel Z20LEH, Astra H / Zafira B OPC, no VVT) on vehicle-logger CSVs.

Everything is shared with the other Opel vehicle-logger family in
:mod:`opel_vehicle`; this module names the per-cylinder knock channels,
which this ECU logs as ``dwkrz[0]`` to ``dwkrz[3]``, and the map names of
its damos (WinOLS export "Opel Astra-H (Original) 371226", 2026-11-04). OP-COM logs are the
second log source for this family and are not wired yet.

Against the ME7 (1.8T) names:

- KFURL and KFPRG are KFURLE and KFPRGE, "Grund-KF bei Einlass-NWS": the
  same rpm by cam-overlap layout (overlap 0 and 90 deg, equal columns on
  this engine), but each on its own 24-point rpm axis, KFPRGE from 0 rpm.
- KFPBRK is KFPBRKLM, on throttle angle (wdkba) by rpm instead of load by
  rpm, all 1.0 on a default 0..12015 rpm axis in this file. ps_w is
  modelled here anyway, so it is not imported.
- The LDR works above the base boost, not above ambient: KFLDIMX and
  KFLDRL are looked up with plsolr_w = plsol_w - plgru_w, and plgru_w =
  pu + DPLPU(nmot) (BGPLGU). DPLPU and its twin DPLPUR (LDRPLSBY, the same
  curve in the Astra H file) are fitted to the 0 % duty pull; KFLDRL is
  calculated with the boost above the base boost the new DPLPU gives, and
  KFLDIMX gets an axis from 0 above it. The Astra H file has DPLPU at
  $AD578 (axis, 4 x 16 bit, 0.25 rpm) / $AD580 (4 bytes, 10 hPa) and
  DPLPUR at $ADC14 / $ADC1C; the ported export does not carry them yet.
- KFVPDKSD (the dynamic target pressure ratio of the 1.8T) does not exist.
  The steady-state KFVPDKSE (8 rpm x 4) runs on (ps - plgru) / (plsolmax -
  plgru), not on an absolute pressure ratio. It is filled by the MED9
  transform (:func:`generate_kfvpdkse`): the axis on the ECU's plgru (pu +
  the new DPLPU), the 0.95 / 1.0 step at the measured 0 % duty boost,
  plsolmax from VVMDXSN / VVNTUXS (compressor pressure-ratio limits by rpm)
  times pu.
- KFLDIMX, KFLDRL, KFLDRQ0 / Q1 / Q2, LDRQ1ST, FKKVS (te = tevfa_w,
  confirmed by its axis name), KFFWL, KFFWLW, KFZW and KFKHFM keep the
  ME7 names. KFLDRAPP (rpm by pedal) is there for forced-duty logging.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..core.winols import TargetMap
from ..generators import axis_block, column
from ..generators.base_boost import ambient_per_row, generate_base_boost_maps
from ..generators.handover import generate_kfvpdkse
from ..generators.maf_check import DEFAULT_MIN_THROTTLE, DEFAULT_VE, DISPLACEMENT_2_0, generate_maf_check
from . import bosch_me7 as me7
from .base import GeneratorSpec, ParamSpec, RunContext
from .opel_vehicle import (  # noqa: F401  (re-exported for callers and tests)
    DEFAULT_VARS,
    GENERATORS,
    VAR_LABELS,
    drop_overrun,
    knock_from_cylinders,
    modelled_manifold_pressure,
    opel_vehicle_family,
)
from .opel_vehicle import PARAMS as OPEL_PARAMS

KNOCK_CYLINDERS = ("dwkrz[0]", "dwkrz[1]", "dwkrz[2]", "dwkrz[3]")

TARGET_MAPS = [
    TargetMap("KFLDIMX", "rpm_boost", "boost", "base_kfldimx", "Boost Control"),
    TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "Boost Control"),
    TargetMap("DPLPU", "row_dplpu", "rpm_dplpu", "base_dplpu", "Boost Control"),
    TargetMap("DPLPUR", "row_dplpur", "rpm_dplpur", "base_dplpur", "Boost Control"),
    TargetMap("KFVPDKSE", "rpm_kfvpdkse", "ratio_kfvpdkse", "base_kfvpdkse", "Throttle Handover"),
    TargetMap("VVMDXSN", "row_vvmdxsn", "rpm_vvmdxsn", "base_vvmdxsn", "Throttle Handover"),
    TargetMap("VVNTUXS", "row_vvntuxs", "rpm_vvntuxs", "base_vvntuxs", "Throttle Handover"),
    TargetMap("KFLDRQ0", "rpm_kfldrq0", "x_kfldrq0", "base_kfldrq0", "Boost PID"),
    TargetMap("KFLDRQ1", "rpm_kfldrq1", "x_kfldrq1", "base_kfldrq1", "Boost PID"),
    TargetMap("KFLDRQ2", "rpm_kfldrq2", "x_kfldrq2", "base_kfldrq2", "Boost PID"),
    TargetMap("LDRQ1ST", "row_ldrq1st", "rpm_ldrq1st", "base_ldrq1st", "Boost PID"),
    TargetMap("FKKVS", "rpm_fuel", "te", "base_fkkvs", "Fueling"),
    TargetMap("KFFWLW", "rpm_kffwlw", "load_kffwlw", "base_kffwlw", "Warmup Enrichment"),
    TargetMap("KFFWL", "tmot", "kffwl_trim", "base_kffwl", "Warmup Enrichment"),
    TargetMap("KFZW", "rpm_ign", "load_ign", "base_kfzw", "Ignition Timing"),
    TargetMap("KFKHFM", "rpm_kfkhfm", "load_kfkhfm", "base_kfkhfm", "MAF Check"),
    TargetMap("KFPRGE", "rpm_prg", "vvt_prg", "base_kfprg", "Saugrohrmodell"),
    TargetMap("KFURLE", "rpm_url", "vvt_url", "base_kfurl", "Saugrohrmodell"),
]

# No KFVPDKSD here, so no automatic KFVPDKSD axis either. The pressure
# reference is a choice: the LDR of this ECU works above the base boost.
BOOST_REFERENCE = ParamSpec(
    "boost_reference", "Boost measured from", "choice", "plgru", section=me7.BOOST, group="Pressure reference",
    choices=(("Base boost plgru = pu + DPLPU, as the LDR does", "plgru"),
             ("Ambient pressure setting", "ambient"),
             ("Logged pu (CWLDIMX)", "pu")),
    tip="ME7.6.2 looks KFLDIMX and KFLDRL up with plsolr_w = plsol_w - plgru_w, the target above the base "
        "boost, not above ambient. With the new DPLPU the logged plgru_w is moved to the new curve.")
AUTO_AXIS_KFLDIMX = ParamSpec(
    "auto_axis_kfldimx", "Auto KFLDIMX axis from 0 above base boost", "bool", True, section=me7.BOOST,
    group="KFLDRL / KFLDIMX", enabled_when=("boost_reference", "plgru"),
    tip="KFLDIMX axis from 0 to the highest target above base boost in the logs (99th percentile, rounded "
        "up to 50 hPa), even steps, as many points as the imported axis.")


def _params() -> list[ParamSpec]:
    out = []
    for spec in OPEL_PARAMS:
        if spec in me7.KFVPDKSD:
            continue
        if spec.key == "cwldimx":
            out.append(BOOST_REFERENCE)
            continue
        if spec.key == "ambient_pressure":
            out.append(replace(spec, tip="pu where it cannot be had from plgru_w - DPLPU, and the pressure the "
                                         "VVMDXSN / VVNTUXS ratios multiply then."))
            continue
        out.append(spec)
        if spec.key == "auto_axis_kfldrl":
            out.append(AUTO_AXIS_KFLDIMX)
    return out


MAF_GROUP = "MAF check (information only)"
MAF = [
    replace(me7.MAF[0]),
    replace(me7.MAF[1], default=DISPLACEMENT_2_0),
    replace(me7.MAF[2], label="Throttle (wdk1) at least",
            tip="Only rows with the throttle wide open: at low rpm this ECU holds the throttle part closed even "
                "at full pedal, so the pedal does not tell."),
]

PARAMS = _params() + MAF
PLGRU_COLUMN = "__plgru_new"


def _dplpu_curves(p) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    curves = {}
    for name in ("DPLPU", "DPLPUR"):
        axis, values = p.axis(f"rpm_{name.lower()}"), p.base_map(f"base_{name.lower()}")
        if axis is not None and values is not None:
            curves[name] = (np.asarray(axis, dtype=float).ravel(), np.asarray(values, dtype=float).ravel())
    return curves


def _base_boost(ctx: RunContext):
    """DPLPU and DPLPUR from the 0 % duty pull."""
    p = ctx.preset
    return me7._on_sheet(generate_base_boost_maps(
        ctx.logs.wot, p.vars, curves=_dplpu_curves(p), ambient_pressure=float(ctx.p("ambient_pressure", 1000)),
        min_samples=float(ctx.p("min_samples_base_wg", 1)), messages=ctx.messages,
    ), "Boost")


def plgru_after(ctx: RunContext, data) -> tuple[np.ndarray | None, bool]:
    """Each row's base boost once the new DPLPU is in: the logged plgru_w
    moved by the new minus the file's DPLPU at the row's rpm. Returns
    ``(plgru, moved)``; None without a plgru_w channel."""
    p = ctx.preset
    col = p.var("plgru")
    if not col or col not in data.columns:
        return None, False
    plgru = column(data, col)
    new, file_curve = ctx.map("dplpu"), _dplpu_curves(p).get("DPLPU")
    if new is None or file_curve is None:
        return plgru, False
    rpm = column(data, p.var("rpm"))
    shift = (np.interp(rpm, np.asarray(new.x_axis, dtype=float), np.ravel(new.values))
             - np.interp(rpm, *file_curve))
    return plgru + shift, True


def kfldimx_axis(target_above, n_points: int) -> np.ndarray | None:
    """0 to the highest target above base boost (99th percentile, up to the next 50 hPa), in 10 hPa steps."""
    t = np.asarray(target_above, dtype=float)
    t = t[np.isfinite(t)]
    if t.size == 0 or n_points < 2:
        return None
    top = max(float(np.ceil(np.percentile(t, 99) / 50.0) * 50.0), 100.0)
    return np.round(np.linspace(0.0, top, n_points) / 10.0) * 10.0


def _boost(ctx: RunContext):
    """KFLDIMX / KFLDRL with the boost measured from the base boost plgru, as
    the ME7.6.2 LDR measures its target (plsolr = plsol - plgru)."""
    p = ctx.preset
    reference = str(ctx.p("boost_reference", "plgru"))
    if reference == "pu":
        pu = p.var("pu")
        if pu and pu in ctx.logs.wot.columns:
            return me7._boost(ctx, reference_column=pu)
        ctx.messages.append("KFLDRL: pu is not logged, boost measured from the ambient setting.")
        return me7._boost(ctx)
    if reference == "ambient":
        return me7._boost(ctx)
    data = ctx.logs.wot.copy()
    plgru, moved = plgru_after(ctx, data)
    if plgru is None:
        ctx.messages.append("KFLDRL: plgru_w is not logged, boost measured from the ambient setting instead of the "
                            "base boost; the LDR of this ECU works above the base boost, so log plgru_w.")
        return me7._boost(ctx)
    data[PLGRU_COLUMN] = plgru
    blocks, axis_boost = [], None
    target = p.var("boost_target")
    imported = p.axis("boost")
    if bool(ctx.p("auto_axis_kfldimx", True)) and target and target in data.columns:
        axis_boost = kfldimx_axis(column(data, target) - plgru, imported.size if imported is not None else 8)
        if axis_boost is not None:
            ctx.messages.append(f"Auto axis KFLDIMX: 0 to {axis_boost[-1]:g} hPa above base boost, "
                                f"{', '.join(f'{a:g}' for a in axis_boost)}.")
            blocks.append(axis_block("boost_axis_kfldimx", "KFLDIMX axis, hPa above base boost (paste into WinOLS)",
                                     axis_boost, "hPa"))
    ctx.messages.append("KFLDIMX / KFLDRL: boost measured from the base boost plgru, "
                        + ("the logged plgru_w moved to the new DPLPU" if moved else "the logged plgru_w")
                        + " (the ME7.6.2 LDR looks both up with plsolr = plsol - plgru).")
    return me7._boost(ctx, data=data, reference_column=PLGRU_COLUMN,
                      reference_label="Target above base boost plgru (hPa)", axis_boost=axis_boost, blocks=blocks)


def _kfvpdkse(ctx: RunContext):
    """KFVPDKSE from the 0 % duty pull and the compressor pressure-ratio limits,
    on the axis the ECU defines with its own plgru (the new DPLPU when there is one)."""
    p = ctx.preset
    curves = []
    for name in ("vvmdxsn", "vvntuxs"):
        axis, values = p.axis(f"rpm_{name}"), p.base_map(f"base_{name}")
        if axis is not None and values is not None:
            curves.append((axis, values))
    data = ctx.logs.wot
    file_curve = _dplpu_curves(p).get("DPLPU")
    pu_rows, from_logs = ambient_per_row(data, p.vars, *(file_curve or (None, None)),
                                         fallback=float(ctx.p("ambient_pressure", 1000)))
    pu = float(np.median(pu_rows)) if pu_rows.size else float(ctx.p("ambient_pressure", 1000))
    axis_rpm = np.asarray(p.axis("rpm_kfvpdkse"), dtype=float).ravel()
    new = ctx.map("dplpu")
    if new is not None:
        plgru = pu + np.interp(axis_rpm, np.asarray(new.x_axis, dtype=float), np.ravel(new.values))
    elif file_curve is not None:
        plgru = pu + np.interp(axis_rpm, *file_curve)
    else:
        plgru = None
    if from_logs:
        ctx.messages.append(f"KFVPDKSE: pu {pu:.0f} hPa from plgru_w - DPLPU.")
    return me7._on_sheet(generate_kfvpdkse(
        data, p.vars, min_samples=float(ctx.p("min_samples_base_wg", 1)), ambient_pressure=pu,
        axis_rpm=axis_rpm, axis_ratio=p.axis("ratio_kfvpdkse"), max_ratio_curves=curves, plgru=plgru,
        messages=ctx.messages,
    ), "Boost")


def _maf_check(ctx: RunContext):
    """ml_w against the airflow at the reference VE on the KFKHFM grid, as on
    ME7: tans is the charge temperature (the sensor sits in the boost
    pressure sensor after the intercooler), rows with the throttle (wdk1)
    wide open, 1998 cc. Information only."""
    p = ctx.preset
    v = dict(p.vars)
    v["pedal"] = p.var("throttle") or v["pedal"]
    data = ctx.logs.full
    return me7._on_sheet(generate_maf_check(
        data, v, axis_rpm=p.axis("rpm_kfkhfm"), axis_load=p.axis("load_kfkhfm"), base_map=p.base_map("base_kfkhfm"),
        displacement_cc=float(ctx.p("maf_displacement", DISPLACEMENT_2_0)),
        ve_pct=float(ctx.p("maf_ve", DEFAULT_VE)), min_throttle=float(ctx.p("maf_min_throttle", DEFAULT_MIN_THROTTLE)),
        min_samples=float(ctx.p("min_samples", 1)), messages=ctx.messages,
    ), "Airflow")


MAF_GENERATOR = GeneratorSpec(
    "maf", "MAF Check (ml_w vs reference VE, KFKHFM axes, information only)", ("full",),
    ("rpm_kfkhfm", "load_kfkhfm"), _maf_check)
BASE_BOOST_GENERATOR = GeneratorSpec(
    "base_boost", "Base Boost (DPLPU / DPLPUR from the 0 % duty pull)", ("wot",), ("rpm_dplpu",), _base_boost,
    required_base_maps=("base_dplpu",))
KFVPDKSE_GENERATOR = GeneratorSpec(
    "kfvpdkse", "Throttle Handover (KFVPDKSE from the 0 % duty pull)", ("wot",),
    ("rpm_kfvpdkse", "ratio_kfvpdkse", "rpm_vvmdxsn"), _kfvpdkse, required_base_maps=("base_vvmdxsn",))


def _generators() -> list[GeneratorSpec]:
    out = [BASE_BOOST_GENERATOR]
    for g in GENERATORS:
        if g.key == "handover":
            out.append(KFVPDKSE_GENERATOR)
        elif g.key == "boost":
            out.append(replace(g, run=_boost))
        else:
            out.append(g)
    return out + [MAF_GENERATOR]


GENERATORS_ME762 = _generators()

BOSCH_ME762 = opel_vehicle_family(
    key="bosch_me762",
    display_name="Bosch ME7.6.2 Opel (vehicle logs)",
    excel_default_name="ME762_Tuning_Maps.xlsx",
    knock_cylinders=KNOCK_CYLINDERS,
    target_maps=TARGET_MAPS,
    params=PARAMS,
    generators=GENERATORS_ME762,
)
