"""The Family protocol: everything that differs between ECU families, declared once per family."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..core.logs import IngestSettings, PrepHook, SplitLogs, process_raw_logs, read_logger_csv
from ..core.maps import CalibrationMap
from ..core.preset import Preset
from ..core.winols import ImportResult, TargetMap, parse_export
from ..core.xdf import import_xdf_maps


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
    """Where logs come from: a reader, the prep hooks applied to each file, and cleaning rules."""

    key: str
    label: str
    reader: Callable[[Path], pd.DataFrame] = read_logger_csv
    hooks: tuple[PrepHook, ...] = ()
    fuzzy_columns: bool = False
    """Match logger columns case-insensitively or by substring (TunerPro exports)."""
    required_channels: tuple[str, ...] = ()
    """Drop rows with NaN only in these channels; empty means any NaN drops the row."""


@dataclass(frozen=True)
class FileInput:
    key: str
    """Stored under ``preset.files[key]``."""
    label: str
    filter: str


@dataclass(frozen=True)
class MapImporter:
    """How a family gets its axes and factory maps: a WinOLS export, or an XDF plus binary."""

    kind: str
    label: str
    inputs: tuple[FileInput, ...]
    run: Callable[[dict[str, str], list[TargetMap]], ImportResult]


WINOLS_IMPORTER = MapImporter(
    kind="winols",
    label="Import WinOLS CSV Export",
    inputs=(FileInput("winols_csv", "WinOLS CSV export", "CSV export (*.csv);;All files (*)"),),
    run=lambda paths, targets: parse_export(paths["winols_csv"], targets),
)

XDF_IMPORTER = MapImporter(
    kind="xdf",
    label="Import maps from XDF + binary",
    inputs=(
        FileInput("xdf", "TunerPro XDF definition", "XDF definition (*.xdf);;All files (*)"),
        FileInput("bin", "Binary file", "Binary (*.bin *.ori *.hex *.rom);;All files (*)"),
    ),
    run=lambda paths, targets: import_xdf_maps(paths["xdf"], paths["bin"], targets),
)


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
    required_base_maps: tuple[str, ...] = ()

    def readiness(self, preset: Preset, logs: SplitLogs) -> str | None:
        """None when the generator can run, else the reason it is skipped."""
        missing = [a for a in self.required_axes if preset.axis(a) is None]
        if missing:
            return f"Missing axes in preset: {', '.join(missing)}"
        missing = [m for m in self.required_base_maps if preset.base_map(m) is None]
        if missing:
            return f"Missing base maps in preset: {', '.join(missing)}"
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

IngestCheck = Callable[[SplitLogs, Preset], list[str]]
"""Runs after ingestion; returns warnings to show the user, e.g. a limp-home flag that was ON."""


def flag_was_on(channel: str, label: str) -> IngestCheck:
    """An ingest check that warns when an ON/OFF channel was ever ON in the imported logs."""

    def check(logs: SplitLogs, preset: Preset) -> list[str]:
        col = preset.var(channel)
        if not col or col not in logs.full.columns:
            return []
        on = int((logs.full[col] == 1).sum())
        if on == 0:
            return []
        share = 100.0 * on / max(len(logs.full), 1)
        return [f"{label} was ON in {on} of {len(logs.full)} rows ({share:.1f} %). The data is compromised."]

    return check


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
    map_importer: MapImporter = WINOLS_IMPORTER
    post_process: list[PostProcess] = field(default_factory=list)
    """Run after all generators, e.g. the 5120 scaling of KFURL and KFPRG."""
    ingest_checks: list[IngestCheck] = field(default_factory=list)
    extra_tabs: list[type] = field(default_factory=list)
    default_prep: dict[str, Any] = field(default_factory=dict)
    show_pressure_hack: bool = True
    """Show the 5120 mbar hack controls on the profile tab."""
    excel_sheet: str = "Tuning Maps"
    excel_default_name: str = "ME_Tuning_Maps.xlsx"

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
            "excel_filename": self.excel_default_name,
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
        """Rates default to infinity (no transient filter) when the family declares no such parameter."""
        p = preset.params
        declared = {spec.key for spec in self.params}
        return IngestSettings(
            max_rpm_roc=float(p.get("max_rpm_roc", 1000 if "max_rpm_roc" in declared else math.inf)),
            max_pedal_roc=float(p.get("max_throttle_roc", 33 if "max_throttle_roc" in declared else math.inf)),
            wot_min=float(p.get("wot_min", 70)),
            temp_max=float(p.get("temp_max", 80)),
        )

    def ingest(self, folder: str | Path, preset: Preset) -> SplitLogs:
        source = self.log_source(preset.log_source)
        required = [preset.var(ch) for ch in source.required_channels if preset.var(ch)]
        logs = process_raw_logs(
            folder, preset, self.ingest_settings(preset), list(source.hooks),
            reader=source.reader, fuzzy_columns=source.fuzzy_columns, required_columns=required or None,
        )
        for check in self.ingest_checks:
            for warning in check(logs, preset):
                logs.warnings.append(warning)
                logs.messages.append(f"[WARNING] {warning}")
        return logs

    def import_maps(self, preset: Preset) -> ImportResult:
        """Run the family's map importer with the paths stored in ``preset.files``."""
        paths = {inp.key: str(preset.files.get(inp.key, "")) for inp in self.map_importer.inputs}
        missing = [inp.label for inp in self.map_importer.inputs if not paths[inp.key]]
        if missing:
            raise FileNotFoundError("Missing file: " + ", ".join(missing))
        return self.map_importer.run(paths, self.target_maps)

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
                status = "No data" if (m.skip_if_empty and m.all_nan) else "Calculated"
                result.rows.append(StatusRow(m.title, status, m.shape_label(), m.key))
        for hook in self.post_process:
            hook(ctx, result)
        return result


def mhd_log_source(required_channels: tuple[str, ...] = ("rpm",), hooks: tuple[PrepHook, ...] = ()) -> LogSource:
    """MHD Flasher CSV logs: comment header, units in the column names, converted to bar and degrees C."""
    from ..core.mhd import read_mhd_csv

    return LogSource("mhd", "MHD Flasher CSV", reader=read_mhd_csv, hooks=hooks, fuzzy_columns=True,
                     required_channels=required_channels)
