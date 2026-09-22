"""Session state shared by the tabs."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.logs import SplitLogs
from ..core.preset import Preset
from ..core.winols import MapStatus
from ..families.base import Family, RunResult


@dataclass
class AppState:
    family: Family
    preset: Preset
    logs: SplitLogs | None = None
    log_folder: str = ""
    map_status: list[MapStatus] = field(default_factory=list)
    result: RunResult | None = None
