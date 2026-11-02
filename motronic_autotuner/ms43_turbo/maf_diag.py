"""ip_maf_1_diag__n__tps_av from the logs: the MAF substitute the firmware
uses when the load signal fails. Rpm down the rows, throttle body position
(degrees TPS) across the columns, load in mg/stk.

The table gets the load the engine really had at each throttle and rpm,
not the logged load as it is: every row's logged load is multiplied by the
same factor the VE correction uses (Wideband AFR / AFR target plus the trims
with a wideband, 1 plus the trims on closed-loop rows without one). A rich
reading means the ECU over-estimated the air, so the load comes down. That
is also the load the ECU will calculate once the corrected VE is in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.maps import CalibrationMap
from .splat import splat_values
from .ve import channel, row_factors

TABLE = "ip_maf_1_diag__n__tps_av"
CORNER = "RPM \\ TPS"


def generate_maf_diag(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    wideband: bool,
    both_banks: bool,
    axis_tps,
    axis_rpm,
    base_map: np.ndarray | None = None,
    min_weight: float = 2.0,
    skip_col: str | None = None,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """The scaled load per cell and, with the factory table ``[len(axis_rpm), len(axis_tps)]``,
    the new table: logged cells from the logs, the rest unchanged."""
    messages = messages if messages is not None else []
    axis_tps = np.asarray(axis_tps, dtype=float).ravel()
    axis_rpm = np.asarray(axis_rpm, dtype=float).ravel()
    factor = row_factors(data, v, wideband=wideband, both_banks=both_banks, skip_col=skip_col,
                         messages=messages, tag=TABLE)
    used = np.isfinite(factor)
    if not used.any():
        hint = "." if wideband else ": closed loop was never on. Tick 'Wideband present' if one is fitted."
        raise ValueError(f"No usable rows for {TABLE}" + hint)
    load = channel(data, v["load"])
    scaled = load * factor
    s = splat_values(channel(data, v["tps"]), channel(data, v["rpm"]), scaled, axis_tps, axis_rpm, min_weight)
    if np.isnan(s.values).all():
        raise ValueError(f"{TABLE}: no cell reached {min_weight:g} samples.")
    cells = int(np.isfinite(s.values).sum())
    messages.append(
        f"{TABLE}: {cells} cells from the logs, {v['load']} x factor (median factor {np.median(factor[used]):.3f}), "
        f"{np.nanmin(s.values):.0f} to {np.nanmax(s.values):.0f} mg/stk."
    )
    out = [CalibrationMap(
        "maf_diag_logs", f"{TABLE}: Scaled Load from the Logs (mg/stk)", s.values, axis_tps, axis_rpm,
        counts=s.weights, counts_title=f"{TABLE} - SAMPLE WEIGHTS", corner_label=CORNER,
    )]
    if base_map is None:
        messages.append(f"{TABLE}: factory table not imported, so no new table.")
        return out
    base = np.asarray(base_map, dtype=float)
    if base.shape != s.values.shape:
        messages.append(f"{TABLE}: imported table is {base.shape}, the axes give {s.values.shape}; no new table.")
        return out
    has = np.isfinite(s.values)
    ratio = s.values[has] / np.where(base[has] > 0, base[has], np.nan)
    if np.isfinite(ratio).any():
        messages.append(f"{TABLE}: logged cells are {np.nanmedian(ratio):.2f} x the factory value (median).")
    out.append(CalibrationMap(
        "maf_diag_new", f"{TABLE} New (paste into TunerPro)", np.where(has, s.values, base), axis_tps, axis_rpm,
        corner_label=CORNER,
    ))
    return out
