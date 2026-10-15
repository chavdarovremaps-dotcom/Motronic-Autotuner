"""ECU family plugins. Each family declares its defaults, target maps, log
sources and generators; the core and the GUI are shared."""

from __future__ import annotations

from .base import Family


def all_families() -> dict[str, Family]:
    from .bosch_me7 import BOSCH_ME7
    from .bosch_me155 import BOSCH_ME155
    from .bosch_me762 import BOSCH_ME762
    from .bosch_mg1cs201 import BOSCH_MG1CS201
    from .siemens_ms43 import SIEMENS_MS43

    return {f.key: f for f in (BOSCH_ME7, BOSCH_ME155, BOSCH_ME762, SIEMENS_MS43, BOSCH_MG1CS201)}


def get_family(key: str) -> Family:
    families = all_families()
    if key not in families:
        raise KeyError(f"Unknown ECU family '{key}'. Known: {', '.join(families)}")
    return families[key]
