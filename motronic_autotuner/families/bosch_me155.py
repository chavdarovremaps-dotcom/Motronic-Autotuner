"""Bosch ME1.5.5 (Opel Z20LET, Astra G / Zafira A OPC, no VVT) on vehicle-logger CSVs.

The log carries the same RAM names as the ME7.6.2 one, so everything is
shared in :mod:`opel_vehicle`; this module only names the per-cylinder
knock channels, ``dwkrz_0_A`` to ``dwkrz_3_A`` on this ECU (the bare
``dwkrz`` column is a status byte, not a retard). OP-COM logs are the
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

KNOCK_CYLINDERS = ("dwkrz_0_A", "dwkrz_1_A", "dwkrz_2_A", "dwkrz_3_A")

BOSCH_ME155 = opel_vehicle_family(
    key="bosch_me155",
    display_name="Bosch ME1.5.5 Opel (vehicle logs)",
    excel_default_name="ME155_Tuning_Maps.xlsx",
    knock_cylinders=KNOCK_CYLINDERS,
)
