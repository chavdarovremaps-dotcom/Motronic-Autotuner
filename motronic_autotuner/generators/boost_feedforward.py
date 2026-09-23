"""Bosch power-based boost control (MG1CS201 and relatives): fold the steady
P and I effort into the compressor characteristic, and check the P chain.

See docs/mg1cs201_boost_pid.md for the controller structure this follows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from ..core.maps import CalibrationMap
from ..core.splatting import bilinear
from . import column


def map_lookup(values: np.ndarray, axis_x: np.ndarray, axis_y: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear table lookup with the inputs clamped to the axis range, as an ECU does."""
    axis_x = np.asarray(axis_x, dtype=float).ravel()
    axis_y = np.asarray(axis_y, dtype=float).ravel()
    f = RegularGridInterpolator((axis_y, axis_x), np.asarray(values, dtype=float), bounds_error=False, fill_value=None)
    xc = np.clip(np.asarray(x, dtype=float), axis_x.min(), axis_x.max())
    yc = np.clip(np.asarray(y, dtype=float), axis_y.min(), axis_y.max())
    return f(np.column_stack([yc, xc]))


def steady_mask(data: pd.DataFrame, v: dict[str, str], *, min_target: float, max_dev_bar: float,
                min_rpm: float = 0.0, exclude: np.ndarray | None = None) -> np.ndarray:
    """Rows where the boost controller is active and settled.

    Active: the boost target is at least ``min_target`` bar (below that the
    DME requests nothing and the P, I and D terms carry no information about
    the table). Settled: |deviation| within ``max_dev_bar``. Pedal and
    throttle are not conditions, so part-throttle boost requests count too;
    that is how the low-ratio, low-flow cells of the table get data.
    ``exclude`` drops extra rows such as those around a gear change.
    """
    keep = (column(data, v["boost_target"]) >= min_target) & (np.abs(column(data, v["boost_dev"])) <= max_dev_bar)
    if min_rpm > 0:
        keep &= column(data, v["rpm"]) >= min_rpm
    if exclude is not None:
        keep &= ~np.asarray(exclude, dtype=bool)
    return keep


def generate_compressor_feedforward(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    base_map: np.ndarray,
    base_title: str,
    axis_ratio: np.ndarray,
    axis_flow: np.ndarray,
    min_samples: float,
    min_target: float,
    max_dev_bar: float,
    min_rpm: float = 0.0,
    exclude: np.ndarray | None = None,
    messages: list[str] | None = None,
) -> list[CalibrationMap]:
    """Average (after P-D minus base) in steady, controller-active rows per
    cell of the compressor characteristic (x = setpoint ratio, y = MAF req.
    WGDC) and add it."""
    messages = messages if messages is not None else []
    axis_ratio = np.asarray(axis_ratio, dtype=float).ravel()
    axis_flow = np.asarray(axis_flow, dtype=float).ravel()
    base = np.asarray(base_map, dtype=float)
    if base.shape != (axis_flow.size, axis_ratio.size):
        raise ValueError(f"{base_title}: base map is {base.shape}, axes give {(axis_flow.size, axis_ratio.size)}")

    keep = steady_mask(data, v, min_target=min_target, max_dev_bar=max_dev_bar, min_rpm=min_rpm, exclude=exclude)
    d = data[keep]
    rpm_note = f", rpm >= {min_rpm:g}" if min_rpm > 0 else ""
    messages.append(
        f"Feed-forward: {len(d)} steady rows of {len(data)} (target >= {min_target:g} bar, "
        f"|deviation| <= {max_dev_bar:g} bar{rpm_note})."
    )
    if len(d) == 0:
        raise ValueError("No steady rows with an active boost target for the feed-forward correction.")

    effort = column(d, v["comp_pd"]) - column(d, v["comp_base"])
    err, counts = bilinear(column(d, v["ratio_target"]), column(d, v["maf_req"]), effort, axis_ratio, axis_flow, min_samples)
    corrected = np.where(np.isnan(err), base, base + err)
    has = ~np.isnan(err)
    messages.append(f"Feed-forward: {int(has.sum())} cells corrected, {np.nanmin(err):+.2f} to {np.nanmax(err):+.2f} kW.")

    gear_col = v.get("gear")
    if gear_col in d.columns and v.get("i_term") in d.columns:
        for g, grp in d.groupby(d[gear_col].round()):
            messages.append(
                f"  gear {int(g)}: {len(grp)} steady rows, I {grp[v['i_term']].mean():+.2f} %, "
                f"P {grp[v['p_term']].mean():+.2f} kW, effort {(grp[v['comp_pd']] - grp[v['comp_base']]).mean():+.2f} kW"
                if v.get("p_term") in d.columns else
                f"  gear {int(g)}: {len(grp)} steady rows, I {grp[v['i_term']].mean():+.2f} %"
            )

    corner = "Flow g/s \\ Ratio"
    return [
        CalibrationMap("comp_effort", f"{base_title}: Steady P+D effort (kW)", err, axis_ratio, axis_flow,
                       counts=counts, counts_title=f"{base_title}: SAMPLE WEIGHTS", corner_label=corner, sheet="Boost"),
        CalibrationMap("comp_corrected", f"{base_title} Corrected (kW, paste into TunerPro)", corrected,
                       axis_ratio, axis_flow, corner_label=corner, sheet="Boost"),
    ]


def p_chain_check(
    data: pd.DataFrame,
    v: dict[str, str],
    *,
    pfac: np.ndarray, pfac_ratio: np.ndarray, pfac_flow: np.ndarray,
    pcorr: np.ndarray, pcorr_dev_hpa: np.ndarray, pcorr_flow: np.ndarray,
    min_dev_bar: float = 0.02,
    messages: list[str] | None = None,
) -> dict[str, float]:
    """Reproduce the logged P term: P_kW = Pfactor(ratio, flow) * Pcorrection(deviation, flow) / 1000."""
    messages = messages if messages is not None else []
    dev = column(data, v["boost_dev"])
    keep = np.abs(dev) >= min_dev_bar
    if v.get("p_term") not in data.columns or keep.sum() < 5:
        messages.append("P chain check skipped: no logged P term or too few rows with deviation.")
        return {}
    flow = column(data, v["maf_req_p"]) if v.get("maf_req_p") in data.columns else column(data, v["maf_req"])
    ratio = column(data, v["ratio_target"])
    gain = map_lookup(pfac, pfac_ratio, pfac_flow, ratio[keep], flow[keep])
    shape = map_lookup(pcorr, pcorr_dev_hpa, pcorr_flow, dev[keep] * 1000.0, flow[keep])
    predicted = gain * shape / 1000.0
    logged = column(data, v["p_term"])[keep]
    r = float(np.corrcoef(predicted, logged)[0, 1]) if predicted.std() > 0 and logged.std() > 0 else float("nan")
    ratio_med = float(np.median(predicted[logged != 0] / logged[logged != 0])) if (logged != 0).any() else float("nan")
    messages.append(
        f"P chain check on {int(keep.sum())} rows: correlation {r:.3f}, predicted / logged median {ratio_med:.2f} "
        f"(1.00 = the tables and channels reproduce the DME's P term)."
    )
    return {"r": r, "ratio": ratio_med, "rows": int(keep.sum())}
