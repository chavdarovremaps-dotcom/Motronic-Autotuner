"""Ignition timing on ip_iga_ron98_pl__n__maf from the knock correction.

The map holds the RON98 target ignition angle for part and full load, rpm
down the rows and the ignition load (mg/stk) across the columns, in 0.375
degree steps. Only rows that ran on it are used: the Part Load or Full Load
flag is on (never during idle or fuel cut).

The logged Knock Correction Average (retard, logged negative) is averaged
per cell with the 4-cell splat, as a magnitude. Then per cell:

* average retard at or above the floor: timing comes out by the average,
  rounded up to whole map steps (0.4 with a 0.375 step removes 0.75);
* no retard at all, with enough samples: timing goes in by the advance
  (0.7 degree by default);
* a retard between zero and the floor (a share of a knock row that leaked
  in from a neighbouring cell), too few samples, or no data: unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from ..generators.ignition_knock import timing_removal
from .splat import splat_values
from .ve import channel, has

TABLE = "ip_iga_ron98_pl__n__maf"
CORNER = "RPM \\ Load"
STEP = 0.375
MIN_PULL = 0.1
ADVANCE = 0.7
MIN_PULL_SAMPLES = 1.0
MIN_ADVANCE_SAMPLES = 5.0
NO_RETARD = 1e-9


def map_rows(data: pd.DataFrame, v: dict[str, str], messages: list[str]) -> np.ndarray:
    """Rows on the part / full load map: Part Load or Full Load flag on. Without
    those flags, every row except fuel cut and idle."""
    n = len(data)
    if has(data, v.get("part_load", "")) or has(data, v.get("full_load", "")):
        keep = np.zeros(n, dtype=bool)
        for key in ("part_load", "full_load"):
            if has(data, v.get(key, "")):
                keep |= channel(data, v[key]) == 1
        messages.append(f"{TABLE}: {int(keep.sum())} of {n} rows with Part Load or Full Load on.")
        return keep
    keep = np.ones(n, dtype=bool)
    for key in ("fuel_cut", "idle"):
        if has(data, v.get(key, "")):
            keep &= channel(data, v[key]) != 1
    messages.append(f"{TABLE}: load range flags not logged; {int(keep.sum())} of {n} rows outside fuel cut and idle.")
    return keep


def generate_ignition(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    base_map: np.ndarray,
    axis_load,
    axis_rpm,
    step: float = STEP,
    min_pull: float = MIN_PULL,
    advance: float = ADVANCE,
    min_pull_samples: float = MIN_PULL_SAMPLES,
    min_advance_samples: float = MIN_ADVANCE_SAMPLES,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """``base_map`` is the factory map ``[len(axis_rpm), len(axis_load)]``."""
    messages = messages if messages is not None else []
    axis_load = np.asarray(axis_load, dtype=float).ravel()
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    base = np.asarray(base_map, dtype=float)
    if base.shape != (axis_rpm.size, axis_load.size):
        raise ValueError(f"{TABLE}: imported map is {base.shape}, the axes give {(axis_rpm.size, axis_load.size)}")
    keep = map_rows(data, v, messages)
    if not keep.any():
        raise ValueError(f"No rows on {TABLE}.")
    d = data[keep]
    retard = np.abs(channel(d, v["knock"]))
    s = splat_values(channel(d, v["load_ign"]), channel(d, v["rpm"]), retard, axis_load, axis_rpm, min_weight=0.0)

    avg, weight = s.values, s.weights
    pull_cells = (weight >= min_pull_samples) & (np.nan_to_num(avg) >= min_pull)
    advance_cells = (weight >= min_advance_samples) & (np.nan_to_num(avg, nan=1.0) <= NO_RETARD)
    pull = np.where(pull_cells, timing_removal(np.where(pull_cells, avg, 0.0), step), 0.0)
    change = np.full(base.shape, np.nan)
    change[weight > 0] = 0.0
    change[pull_cells] = -pull[pull_cells]
    change[advance_cells] = advance
    corrected = base + np.nan_to_num(change)

    slivers = int(((weight > 0) & (np.nan_to_num(avg) > NO_RETARD) & ~pull_cells).sum())
    thin = int(((weight > 0) & (np.nan_to_num(avg) <= NO_RETARD) & ~advance_cells).sum())
    messages.append(
        f"{TABLE}: knock in {int((retard > 0).sum())} of {len(d)} rows. {int(pull_cells.sum())} cells pulled "
        f"(up to {pull.max():.3f} deg, step {step:g}), {int(advance_cells.sum())} cells without retard advanced "
        f"{advance:g} deg; unchanged: {slivers} cells with a retard under {min_pull:g} deg or under "
        f"{min_pull_samples:g} samples, {thin} cells without retard but under {min_advance_samples:g} samples."
    )
    if advance and not np.isclose(advance / step, round(advance / step)):
        messages.append(f"{TABLE}: the map stores {step:g} deg steps, so +{advance:g} deg lands as "
                        f"+{round(advance / step) * step:g} deg once pasted.")
    return [
        CalibrationMap("iga_knock_avg", f"{TABLE}: Knock Correction Average (deg retard)", np.where(weight > 0, avg, np.nan),
                       axis_load, axis_rpm, counts=weight, counts_title=f"{TABLE}: Knock - SAMPLE WEIGHTS",
                       corner_label=CORNER),
        CalibrationMap("iga_change", f"{TABLE}: Timing Change (deg)", change, axis_load, axis_rpm, corner_label=CORNER),
        CalibrationMap("iga_new", f"{TABLE} Corrected (paste into TunerPro)", corrected, axis_load, axis_rpm,
                       corner_label=CORNER),
    ]
