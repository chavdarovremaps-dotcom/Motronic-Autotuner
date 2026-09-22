"""The Family protocol: everything that differs between ECU families, declared once per family."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..core.logs import IngestSettings, PrepHook, SplitLogs, process_raw_logs, read_logger_csv
from ..core.maps import CalibrationMap
from ..core.preset import Preset
from ..core.winols import TargetMap


@dataclass(frozen=True)
class ParamSpec:
    """One field on the ingestion tab, stored under ``preset.params[key]``."""

    key: str
    label: str
    kind: str  # "bool" | "int" | "float" | "choice"
    default: Any
    group: str = "General"
    choices: tuple[tuple[str, Any], ...] = ()
    """For ``kind == "choice"``: (label, value) pairs."""
    decimals: int = 2
    minimum: float = -1e9
    maximum: float = 1e9


@dataclass(frozen=True)
class LogSource:
    """Where logs come from: a reader and the prep hooks applied to each file."""

    key: str
    label: str
    reader: Callable[[Path], pd.DataFrame] = read_logger_csv
    hooks: tuple[PrepHook, ...] = ()


@dataclass
class RunContext:
    preset: Preset
    logs: SplitLogs
    messages: list[str] = field(default_factory=list)

    def p(self, key: str, default: Any = None) -> Any:
        return self.preset.params.get(key, default)


@dataclass(frozen=True)
class GeneratorSpec:
    key: str
    label: str
    subsets: tuple[str, ...]
    """Log subsets that must be non-empty: any of "full", "wot", "warmup", "hot"."""
    required_axes: tuple[str, ...]
    run: Callable[[RunContext], list[CalibrationMap]]

    def readiness(self, preset: Preset, logs: SplitLogs) -> str | None:
        """None when the generator can run, else the reason it is skipped."""
        missing = [a for a in self.required_axes if preset.axis(a) is None]
        if missing:
            return f"Missing axes in preset: {', '.join(missing)}"
        empty = [s for s in self.subsets if len(logs.subset(s)) == 0]
        if empty:
            return f"No {', '.join(s.upper() for s in empty)} log rows"
        return None


@dataclass
class StatusRow:
    name: str
    status: str
    size: str
    map_key: str = ""


@dataclass
class RunResult:
    maps: list[CalibrationMap] = field(default_factory=list)
    rows: list[StatusRow] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def map(self, key: str) -> CalibrationMap | None:
        return next((m for m in self.maps if m.key == key), None)


PostProcess = Callable[[RunContext, RunResult], None]


@dataclass
class Family:
    key: str
    display_name: str
    default_vars: dict[str, str]
    """Logical channel -> default logger column, in the order shown on the profile tab."""
    var_labels: dict[str, str]
    params: list[ParamSpec]
    target_maps: list[TargetMap]
    log_sources: list[LogSource]
    generators: list[GeneratorSpec]
    post_process: list[PostProcess] = field(default_factory=list)
    """Run after all generators, e.g. the 5120 scaling of KFURL and KFPRG."""
    extra_tabs: list[type] = field(default_factory=list)
    default_prep: dict[str, Any] = field(default_factory=dict)

    # ---- presets ----------------------------------------------------------

    def default_preset(self) -> Preset:
        p = Preset(family=self.key)
        p.vars = dict(self.default_vars)
        p.prep = dict(self.default_prep)
        p.params = {spec.key: spec.default for spec in self.params}
        p.files = {
            "raw_log_folder": "",
            "filename_wot": "ME_Logs_WOT.csv",
            "filename_full": "ME_Logs_Full.csv",
            "filename_warmup": "ME_Logs_Warmup.csv",
            "filename_hot": "ME_Logs_Hot.csv",
            "excel_filename": "ME_Tuning_Maps.xlsx",
        }
        if self.log_sources:
            p.log_source = self.log_sources[0].key
        return p

    def fill_defaults(self, preset: Preset) -> Preset:
        """Add any missing vars and params from the family defaults (older presets)."""
        for k, v in self.default_vars.items():
            preset.vars.setdefault(k, v)
        for spec in self.params:
            preset.params.setdefault(spec.key, spec.default)
        for k, v in self.default_prep.items():
            preset.prep.setdefault(k, v)
        if not preset.log_source and self.log_sources:
            preset.log_source = self.log_sources[0].key
        return preset

    def log_source(self, key: str) -> LogSource:
        for s in self.log_sources:
            if s.key == key:
                return s
        return self.log_sources[0]

    # ---- pipeline ---------------------------------------------------------

    def ingest_settings(self, preset: Preset) -> IngestSettings:
        p = preset.params
        return IngestSettings(
            max_rpm_roc=float(p.get("max_rpm_roc", 1000)),
            max_pedal_roc=float(p.get("max_throttle_roc", 33)),
            wot_min=float(p.get("wot_min", 70)),
            temp_max=float(p.get("temp_max", 80)),
        )

    def ingest(self, folder: str | Path, preset: Preset) -> SplitLogs:
        source = self.log_source(preset.log_source)
        return process_raw_logs(folder, preset, self.ingest_settings(preset), list(source.hooks))

    def run_all(self, preset: Preset, logs: SplitLogs) -> RunResult:
        ctx = RunContext(preset=preset, logs=logs)
        result = RunResult(messages=ctx.messages)
        for gen in self.generators:
            reason = gen.readiness(preset, logs)
            if reason is not None:
                result.rows.append(StatusRow(gen.label, f"Skipped: {reason}", "-"))
                ctx.messages.append(f"[SKIP] {gen.label}: {reason}")
                continue
            try:
                maps = gen.run(ctx)
            except Exception as exc:  # one failing area must not stop the others
                result.rows.append(StatusRow(gen.label, f"Error: {exc}", "-"))
                ctx.messages.append(f"{gen.label} Error: {exc}")
                continue
            for m in maps:
                result.maps.append(m)
                result.rows.append(StatusRow(m.title, "Calculated", m.shape_label(), m.key))
        for hook in self.post_process:
            hook(ctx, result)
        return result
