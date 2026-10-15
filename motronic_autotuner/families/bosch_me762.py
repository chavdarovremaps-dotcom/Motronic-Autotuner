"""Bosch ME7.6.2 (Opel Z20LEH, Astra H / Zafira B OPC, no VVT) on vehicle-logger CSVs.

Everything is shared with the other Opel vehicle-logger family in
:mod:`opel_vehicle`; this module only names the per-cylinder knock channels,
which this ECU logs as ``dwkrz[0]`` to ``dwkrz[3]``. OP-COM logs are the
second log source for this family and are not wired yet.
"""

from __future__ import annotations

from .opel_vehicle import (  # noqa: F401  (re-exported for callers and tests)
    DEFAULT_VARS,
    PARAMS,
    TARGET_MAPS,
    VAR_LABELS,
    drop_overrun,
    knock_from_cylinders,
    modelled_manifold_pressure,
    opel_vehicle_family,
)

KNOCK_CYLINDERS = ("dwkrz[0]", "dwkrz[1]", "dwkrz[2]", "dwkrz[3]")

BOSCH_ME762 = opel_vehicle_family(
    key="bosch_me762",
    display_name="Bosch ME7.6.2 Opel (vehicle logs)",
    excel_default_name="ME762_Tuning_Maps.xlsx",
    knock_cylinders=KNOCK_CYLINDERS,
)
