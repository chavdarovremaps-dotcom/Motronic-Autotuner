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
- KFVPDKSD (the dynamic target pressure ratio of the 1.8T) does not exist.
  The steady-state KFVPDKSE (8 rpm x 4) runs on (ps - plgru) / (plsolmax -
  plgru), not on an absolute pressure ratio, so the ME7 handover math does
  not fill it; the MATLAB MED9 transform is the model for a later port.
- KFLDIMX, KFLDRL, KFLDRQ0 / Q1 / Q2, LDRQ1ST, FKKVS (te = tevfa_w,
  confirmed by its axis name), KFFWL, KFFWLW, KFZW and KFKHFM keep the
  ME7 names. KFLDRAPP (rpm by pedal) is there for forced-duty logging.
"""

from __future__ import annotations

from ..core.winols import TargetMap
from .opel_vehicle import (  # noqa: F401  (re-exported for callers and tests)
    DEFAULT_VARS,
    PARAMS,
    VAR_LABELS,
    drop_overrun,
    knock_from_cylinders,
    modelled_manifold_pressure,
    opel_vehicle_family,
)

KNOCK_CYLINDERS = ("dwkrz[0]", "dwkrz[1]", "dwkrz[2]", "dwkrz[3]")

TARGET_MAPS = [
    TargetMap("KFLDIMX", "rpm_boost", "boost", "base_kfldimx", "Boost Control"),
    TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "Boost Control"),
    TargetMap("KFLDRQ0", "rpm_kfldrq0", "x_kfldrq0", "base_kfldrq0", "Boost PID"),
    TargetMap("KFLDRQ1", "rpm_kfldrq1", "x_kfldrq1", "base_kfldrq1", "Boost PID"),
    TargetMap("KFLDRQ2", "rpm_kfldrq2", "x_kfldrq2", "base_kfldrq2", "Boost PID"),
    TargetMap("LDRQ1ST", "row_ldrq1st", "rpm_ldrq1st", "base_ldrq1st", "Boost PID"),
    TargetMap("FKKVS", "rpm_fuel", "te", "base_fkkvs", "Fueling"),
    TargetMap("KFFWLW", "rpm_kffwlw", "load_kffwlw", "base_kffwlw", "Warmup Enrichment"),
    TargetMap("KFFWL", "tmot", "kffwl_trim", "base_kffwl", "Warmup Enrichment"),
    TargetMap("KFZW", "rpm_ign", "load_ign", "base_kfzw", "Ignition Timing"),
    TargetMap("KFPRGE", "rpm_prg", "vvt_prg", "base_kfprg", "Saugrohrmodell"),
    TargetMap("KFURLE", "rpm_url", "vvt_url", "base_kfurl", "Saugrohrmodell"),
]

BOSCH_ME762 = opel_vehicle_family(
    key="bosch_me762",
    display_name="Bosch ME7.6.2 Opel (vehicle logs)",
    excel_default_name="ME762_Tuning_Maps.xlsx",
    knock_cylinders=KNOCK_CYLINDERS,
    target_maps=TARGET_MAPS,
)
