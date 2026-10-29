"""Boost PID scaling for ME7: the sensitivity rule made exact.

A turbo that needs less wastegate duty than the file expected for the same
boost is a plant with more gain, and the controller gains have to come down
by the same ratio to keep the loop where it was tuned. The ratio is read
from the KFLDRL just computed from the logs against the KFLDRL in the file,
cell by cell: duty needed now over duty needed then. KFLDRQ0, KFLDRQ1 and
KFLDRQ2 (P, I and D over rpm and deviation band) and KFLDRAPP are multiplied
by it, either by one overall ratio or per rpm.

The file's KFLDRL is the reference, so import the stock export when the
working file's KFLDRL was already changed.
"""

from __future__ import annotations

import numpy as np

from ..core.maps import CalibrationMap
from .boost_feedforward import map_lookup

MIN_FILE_DUTY = 20.0
"""Cells where the file's duty is below this do not enter the ratio: small over small is noise."""


def duty_ratio(new: np.ndarray, axis_rpm: np.ndarray, axis_x: np.ndarray, factory: np.ndarray,
               factory_axis_rpm: np.ndarray, factory_axis_x: np.ndarray, *,
               min_file_duty: float = MIN_FILE_DUTY) -> dict:
    """Per-rpm and overall ratio of the duty the logs show over the duty the file holds.

    ``new`` is the computed KFLDRL (rows = ``axis_rpm``, columns =
    ``axis_x``), ``factory`` the imported one on its own axes, interpolated
    onto the computed grid. A cell counts when the computed map has data
    and the file's duty is at least ``min_file_duty``. Each ratio is a sum
    over sums, so one cell cannot dominate.
    """
    new = np.asarray(new, dtype=float)
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    axis_x = np.asarray(axis_x, dtype=float).ravel()
    X, Y = np.meshgrid(axis_x, axis_rpm)
    file = map_lookup(np.asarray(factory, dtype=float), factory_axis_x, factory_axis_rpm, X.ravel(), Y.ravel()).reshape(new.shape)
    valid = np.isfinite(new) & np.isfinite(file) & (file >= min_file_duty)
    per_rpm = np.full(axis_rpm.size, np.nan)
    file_mean = np.full(axis_rpm.size, np.nan)
    new_mean = np.full(axis_rpm.size, np.nan)
    cells = valid.sum(axis=1)
    for r in range(axis_rpm.size):
        sel = valid[r]
        if sel.any():
            file_mean[r] = file[r, sel].mean()
            new_mean[r] = new[r, sel].mean()
            per_rpm[r] = new[r, sel].sum() / file[r, sel].sum()
    overall = float(new[valid].sum() / file[valid].sum()) if valid.any() else float("nan")
    return {"per_rpm": per_rpm, "overall": overall, "cells": cells, "file_mean": file_mean, "new_mean": new_mean,
            "axis_rpm": axis_rpm}


def scale_rows(base: np.ndarray, base_axis_rpm: np.ndarray, ratio: dict, mode: str) -> tuple[np.ndarray, np.ndarray]:
    """Multiply a map with rpm down the rows by the overall ratio or by the
    per-rpm ratio interpolated onto its rpm axis (clamped at the ends).
    Returns the scaled map and the factor used per row."""
    base = np.asarray(base, dtype=float)
    base_axis_rpm = np.asarray(base_axis_rpm, dtype=float).ravel()
    if mode == "per_rpm":
        per = ratio["per_rpm"]
        ok = np.isfinite(per)
        if ok.sum() == 0:
            factor = np.full(base_axis_rpm.size, ratio["overall"])
        elif ok.sum() == 1:
            factor = np.full(base_axis_rpm.size, per[ok][0])
        else:
            factor = np.interp(base_axis_rpm, ratio["axis_rpm"][ok], per[ok])
    else:
        factor = np.full(base_axis_rpm.size, ratio["overall"])
    if base.ndim == 1:
        return base * factor, factor
    return base * factor[:, None], factor


def generate_pid_scaling(kfldrl: CalibrationMap, *, factory_kfldrl: np.ndarray, factory_axis_rpm: np.ndarray,
                         factory_axis_x: np.ndarray, pid_maps: list[tuple[str, str, np.ndarray, np.ndarray, np.ndarray, str]],
                         mode: str = "overall", min_file_duty: float = MIN_FILE_DUTY,
                         messages: list[str] | None = None) -> list[CalibrationMap]:
    """The ratio table and the scaled PID maps.

    ``pid_maps`` holds ``(key, name, base, axis_rpm, axis_x, x_label)`` for
    each map to scale, rows = rpm.
    """
    messages = messages if messages is not None else []
    ratio = duty_ratio(kfldrl.values, kfldrl.y_axis, kfldrl.x_axis, factory_kfldrl, factory_axis_rpm, factory_axis_x,
                       min_file_duty=min_file_duty)
    if not np.isfinite(ratio["overall"]):
        messages.append(f"Boost PID scaling: no KFLDRL cell with data where the file's duty is at least "
                        f"{min_file_duty:g} %, nothing scaled.")
        return []
    ok = np.isfinite(ratio["per_rpm"])
    messages.append(
        f"Boost PID scaling: the logs need {ratio['overall']:.3f} of the duty in the file "
        f"({int(ratio['cells'].sum())} KFLDRL cells with file duty >= {min_file_duty:g} %); per rpm "
        f"{np.nanmin(ratio['per_rpm']):.3f} to {np.nanmax(ratio['per_rpm']):.3f} over "
        f"{ratio['axis_rpm'][ok].min():g} to {ratio['axis_rpm'][ok].max():g} rpm; "
        f"applied {'per rpm' if mode == 'per_rpm' else 'as one overall ratio'}.")
    table = np.vstack([ratio["file_mean"], ratio["new_mean"], ratio["per_rpm"], ratio["cells"].astype(float)])
    maps = [CalibrationMap("ldr_scale", f"LDR PID scale: duty from the logs over duty in the file (overall {ratio['overall']:.3f})",
                           table, ratio["axis_rpm"],
                           ["File duty % (used cells)", "Logged duty %", "Ratio", "Cells used"], corner_label="Scale \\ RPM")]
    for key, name, base, axis_rpm, axis_x, x_label in pid_maps:
        scaled, factor = scale_rows(base, axis_rpm, ratio, mode)
        how = "per rpm" if mode == "per_rpm" else f"x {ratio['overall']:.3f}"
        maps.append(CalibrationMap(f"{key}_corrected", f"{name} Corrected ({how}, paste into WinOLS)", scaled,
                                   axis_x, axis_rpm, corner_label=f"RPM \\ {x_label}"))
        messages.append(f"  {name}: factor {factor.min():.3f} to {factor.max():.3f}.")
    return maps
