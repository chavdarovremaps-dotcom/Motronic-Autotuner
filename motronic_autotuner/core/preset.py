"""ECU profile ("preset") JSON: logger variable names, prep rules, math
parameters, WinOLS axes and factory base maps for one ECU family.

Reads every spelling the MATLAB scripts and GUI ever wrote, keeps canonical
snake_case keys in memory, and writes the MATLAB spellings back so the
MATLAB app can still open a preset saved here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_FAMILY = "bosch_me7"

# canonical key -> spellings accepted on load (first one is written on save)
_PREP_KEYS = {
    "align_timestamps": ["ALIGN_TIMESTAMPS", "align_timestamps"],
    "hack_5120": ["HACK_5120", "hack_5120"],
    "pressure_columns": ["pressure_columns"],
}
_PARAM_KEYS = {
    "min_samples": ["min_samples"],
    "min_samples_base_wg": ["min_samples_base_wg"],
    "trim_format": ["trim_format"],
    "axis_wgdc_splat": ["axis_wgdc_splat"],
    "fill_missing_data": ["FILL_MISSING_DATA", "fill_missing_data"],
    "cwldimx": ["CWLDIMX", "cwldimx"],
    "ambient_pressure": ["ambient_pressure"],
    "safety_margin": ["safety_margin"],
    "vvt_enabled": ["VVT_ENABLED", "vvt_enabled"],
    "vvt_threshold": ["vvt_threshold"],
    "max_rpm_roc": ["max_rpm_roc"],
    "max_throttle_roc": ["max_throttle_roc"],
    "temp_max": ["temp_max"],
    "wot_min": ["wot_min"],
}
_BOOL_PARAMS = {"fill_missing_data", "cwldimx", "vvt_enabled"}
_BOOL_PREP = {"align_timestamps", "hack_5120"}


@dataclass
class Preset:
    family: str = DEFAULT_FAMILY
    vars: dict[str, str] = field(default_factory=dict)
    prep: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    axes: dict[str, np.ndarray] = field(default_factory=dict)
    base_maps: dict[str, np.ndarray] = field(default_factory=dict)
    files: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] = field(default_factory=dict)
    log_source: str = ""
    source_path: Path | None = None

    # ---- access helpers -------------------------------------------------

    def var(self, channel: str) -> str:
        """Logger column name for a logical channel such as ``"rpm"``."""
        return str(self.vars.get(channel, ""))

    def param(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)

    def axis(self, key: str) -> np.ndarray | None:
        a = self.axes.get(key)
        return None if a is None or np.asarray(a).size == 0 else np.asarray(a, dtype=float).ravel()

    def base_map(self, key: str) -> np.ndarray | None:
        m = self.base_maps.get(key)
        return None if m is None or np.asarray(m).size == 0 else np.asarray(m, dtype=float)

    def has_axes(self, *keys: str) -> bool:
        return all(self.axis(k) is not None for k in keys)

    # ---- JSON -------------------------------------------------------------

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Preset":
        p = cls()
        p.family = str(raw.get("family", DEFAULT_FAMILY))
        p.log_source = str(raw.get("log_source", ""))
        p.vars = {k: str(v) for k, v in dict(raw.get("vars", {})).items()}
        p.files = dict(raw.get("files", {}))
        p.workflow = dict(raw.get("workflow", {}))

        raw_prep = dict(raw.get("prep", {}))
        raw_params = dict(raw.get("params", {}))
        p.prep = _pick(raw_prep, _PREP_KEYS)
        p.params = _pick(raw_params, _PARAM_KEYS)
        # the command-line scripts kept wot_min / temp_max under prep
        for k in ("wot_min", "temp_max"):
            if k not in p.params and k in raw_prep:
                p.params[k] = raw_prep[k]
        # anything unknown is kept so nothing is lost on save
        for k, v in raw_params.items():
            if k not in _all_spellings(_PARAM_KEYS):
                p.params[k] = v

        for k in _BOOL_PREP:
            if k in p.prep:
                p.prep[k] = _to_bool(p.prep[k])
        for k in _BOOL_PARAMS:
            if k in p.params:
                p.params[k] = _to_bool(p.params[k])
        if "pressure_columns" in p.prep:
            p.prep["pressure_columns"] = _to_str_list(p.prep["pressure_columns"])
        if "trim_format" in p.params:
            p.params["trim_format"] = normalize_trim_format(p.params["trim_format"])
        if "axis_wgdc_splat" in p.params:
            p.params["axis_wgdc_splat"] = np.asarray(p.params["axis_wgdc_splat"], dtype=float).ravel()

        p.axes = {k: np.asarray(v, dtype=float).ravel() for k, v in dict(raw.get("axes", {})).items()}
        p.base_maps = {k: np.asarray(v, dtype=float) for k, v in dict(raw.get("base_maps", {})).items()}
        return p

    def to_dict(self) -> dict[str, Any]:
        prep = {}
        for canon, spellings in _PREP_KEYS.items():
            if canon in self.prep:
                prep[spellings[0]] = _jsonable(self.prep[canon], canon in _BOOL_PREP)
        params = {}
        for canon, spellings in _PARAM_KEYS.items():
            if canon in self.params:
                params[spellings[0]] = _jsonable(self.params[canon], canon in _BOOL_PARAMS)
        for k, v in self.params.items():
            if k not in _PARAM_KEYS:
                params[k] = _jsonable(v, False)
        if "trim_format" in params:
            params["trim_format"] = "Percent" if params["trim_format"] == "percent" else "Lambda"
        out = {
            "family": self.family,
            "files": self.files,
            "vars": self.vars,
            "prep": prep,
            "params": params,
            "axes": {k: _jsonable(v, False) for k, v in self.axes.items()},
            "base_maps": {k: _jsonable(v, False) for k, v in self.base_maps.items()},
        }
        if self.log_source:
            out["log_source"] = self.log_source
        if self.workflow:
            out["workflow"] = self.workflow
        return out

    @classmethod
    def load(cls, path: str | Path) -> "Preset":
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            p = cls.from_dict(json.load(f))
        p.source_path = path
        return p

    def save(self, path: str | Path) -> None:
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        self.source_path = path


def normalize_trim_format(value: Any) -> str:
    """Return ``"percent"`` or ``"lambda"`` from any spelling the presets used.

    The MATLAB GUI's dropdown item was spelled ``"Percent,"`` with a trailing
    comma, so that spelling counts as percent here.
    """
    if isinstance(value, str):
        return "percent" if value.strip().lower().startswith("percent") else "lambda"
    try:
        return "percent" if int(value) == 1 else "lambda"
    except (TypeError, ValueError):
        return "lambda"


def _pick(raw: dict[str, Any], keys: dict[str, list[str]]) -> dict[str, Any]:
    out = {}
    for canon, spellings in keys.items():
        for s in spellings:
            if s in raw:
                out[canon] = raw[s]
                break
    return out


def _all_spellings(keys: dict[str, list[str]]) -> set[str]:
    return {s for spellings in keys.values() for s in spellings}


def _to_bool(v: Any) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "on", "yes")
    return bool(v)


def _to_str_list(v: Any) -> list[str]:
    if isinstance(v, str):
        return [s.strip() for s in v.split(",") if s.strip()]
    return [str(s).strip() for s in list(v)]


def _jsonable(v: Any, as_bool: bool) -> Any:
    if as_bool:
        return 1 if _to_bool(v) else 0
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    return v
