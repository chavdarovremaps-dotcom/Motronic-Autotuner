"""KFVPDKSE (ME7.6.2): the MED9 transform of the ME7 throttle handover onto the normalised axis."""

import numpy as np
import pandas as pd
import pytest

from motronic_autotuner.families.bosch_me762 import BOSCH_ME762, DEFAULT_VARS
from motronic_autotuner.generators.handover import generate_kfvpdkse

V = DEFAULT_VARS
AXIS_RPM = np.array([0, 1000, 2000, 3000, 4000, 5000, 6000, 7000.0])
AXIS_RATIO = np.array([0.0, 0.15, 0.6, 0.9])


def base_boost(rpm):
    """Spring boost of the 0 % pull: 1050 hPa abs at 1000 rpm rising to 1500 from 3000 rpm."""
    return np.clip(1050 + (rpm - 1000) * 0.225, 1050, 1500)


def wot_rows(n=4000, seed=5):
    rng = np.random.default_rng(seed)
    rpm = rng.uniform(1200, 5800, n)
    duty = np.where(np.arange(n) < n // 2, 0.0, 60.0)          # half the rows are the 0 % pull
    boost = np.where(duty == 0, base_boost(rpm), base_boost(rpm) + 600) + rng.normal(0, 3, n)
    return pd.DataFrame({V["rpm"]: rpm, V["wgdc"]: duty, V["boost"]: boost})


def run(data, curves=None, **kw):
    curves = curves if curves is not None else [(np.array([1000, 4000, 6350.0]), np.array([2.0, 2.2, 2.2]))]
    messages = []
    maps = generate_kfvpdkse(data, V, min_samples=1, ambient_pressure=1000, axis_rpm=AXIS_RPM,
                             axis_ratio=AXIS_RATIO, max_ratio_curves=curves, messages=messages, **kw)
    return {m.key: m for m in maps}, messages


def test_cells_stand_for_base_plus_ratio_times_the_headroom():
    by, messages = run(wot_rows())
    base = by["kfvpdkse_base"].values
    assert base[4] == pytest.approx(1500, abs=5) and np.isnan(base[0]) and np.isnan(base[-1])
    top = by["kfvpdkse_top"].values
    assert top[0] == pytest.approx(2000) and top[-1] == pytest.approx(2200)   # held flat past the curve's ends
    target = by["kfvpdkse_target"].values                                     # rows = ratio, columns = rpm
    c = 4
    assert target[:, c] == pytest.approx(base[c] + AXIS_RATIO * (top[c] - base[c]))
    assert "0 % duty" in messages[0]


def test_throttle_open_above_the_base_boost_and_a_soft_step_at_it():
    by, _ = run(wot_rows())
    k = by["kfvpdkse"].values
    assert k.shape == (AXIS_RATIO.size, AXIS_RPM.size)
    assert (k <= 1.0).all() and (k >= 0.95).all()
    assert (k[2:] == 1.0).all()                       # well above the base boost: throttle wide open
    assert (k[0] < 1.0).all()                         # at the base boost: the smoothed handover step
    assert (np.diff(k, axis=0) >= 0).all()            # more headroom, never more throttle closing


def test_the_lower_limit_curve_sets_the_top():
    low = (np.array([1000, 6000.0]), np.array([1.8, 1.8]))
    high = (np.array([1000, 6000.0]), np.array([4.0, 4.0]))
    by, _ = run(wot_rows(), curves=[high, low])
    assert by["kfvpdkse_top"].values == pytest.approx(np.full(AXIS_RPM.size, 1800.0))


def test_needs_a_zero_duty_pull_and_a_limit():
    data = wot_rows()
    data[V["wgdc"]] = 60.0
    with pytest.raises(ValueError, match="0 % duty"):
        run(data)
    with pytest.raises(ValueError, match="VVMDXSN"):
        run(wot_rows(), curves=[])


def test_me762_family_carries_kfvpdkse_instead_of_kfvpdksd():
    keys = [g.key for g in BOSCH_ME762.generators]
    assert "kfvpdkse" in keys and "handover" not in keys
    names = [t.winols_name for t in BOSCH_ME762.target_maps]
    assert {"KFVPDKSE", "VVMDXSN", "VVNTUXS"} <= set(names)
    assert "auto_axis_kfvp" not in {p.key for p in BOSCH_ME762.params}


def test_me762_run_all_fills_kfvpdkse():
    from motronic_autotuner.core.logs import SplitLogs
    p = BOSCH_ME762.default_preset()
    p.axes.update({"rpm_kfvpdkse": AXIS_RPM, "ratio_kfvpdkse": AXIS_RATIO,
                   "rpm_vvmdxsn": np.array([1000, 4000, 6350.0]), "row_vvmdxsn": np.array([0.0])})
    p.base_maps["base_vvmdxsn"] = np.array([[2.0, 2.2, 2.2]])
    data = wot_rows()
    res = BOSCH_ME762.run_all(p, SplitLogs(full=data, wot=data, warmup=data.iloc[:0], hot=data))
    assert res.map("kfvpdkse") is not None
    assert not [r for r in res.rows if r.name.startswith("Throttle Handover") and r.status.startswith("Error")]
