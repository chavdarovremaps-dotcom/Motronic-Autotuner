"""Rows with the short-term trim at exactly neutral (lambda control not running) stay out of the fueling maps."""

import numpy as np
import pandas as pd

from motronic_autotuner.families.bosch_me7 import DEFAULT_VARS as V
from motronic_autotuner.generators import lambda_control_on
from motronic_autotuner.generators.fuel import generate_fkkvs
from motronic_autotuner.generators.warmup import generate_warmup_maps

RPM = np.array([2000.0, 3000.0])
TE = np.array([2.0, 4.0])


def rows(stft, n=40, tmot=90.0):
    """``n`` rows at 2500 rpm and te 3 ms (all four FKKVS cells share them), long-term trim 1.0."""
    return pd.DataFrame({V["rpm"]: np.full(n, 2500.0), V["inj"]: np.full(n, 3.0), V["stft"]: np.full(n, stft),
                         V["ltft"]: np.ones(n), V["tmot"]: np.full(n, tmot), V["load"]: np.full(n, 50.0)})


def test_neutral_trim_means_the_control_is_not_running():
    np.testing.assert_array_equal(lambda_control_on(np.array([1.0, 1.0000305, 0.98, np.nan]), "lambda"),
                                  [False, True, True, False])
    np.testing.assert_array_equal(lambda_control_on(np.array([0.0, 0.1, -2.0]), "percent"), [False, True, True])


def test_fkkvs_leaves_the_rows_at_exactly_one_out():
    data = pd.concat([rows(1.05), rows(1.0)], ignore_index=True)
    msgs = []
    fk = generate_fkkvs(data, V, min_samples=1, trim_format="lambda", axis_rpm=RPM, axis_te=TE, messages=msgs)[0]
    np.testing.assert_allclose(fk.values, 5.0)                     # not 2.5: the 40 idle rows do not dilute it
    assert fk.counts.sum() == 40
    assert msgs == ["  FKKVS: 40 of 80 rows left out, short-term trim at exactly 1.0 (lambda control not running)."]
    pct = pd.concat([rows(5.0), rows(0.0)], ignore_index=True)
    pct[V["ltft"]] = 0.0
    fk = generate_fkkvs(pct, V, min_samples=1, trim_format="percent", axis_rpm=RPM, axis_te=TE)[0]
    np.testing.assert_allclose(fk.values, 5.0)


def test_warmup_leaves_the_cold_rows_before_closed_loop_out():
    cold_on, cold_off = rows(1.08, tmot=30.0), rows(1.0, tmot=30.0)     # closed loop not started yet at 1.0
    hot = rows(1.02, tmot=90.0)
    warm = pd.concat([cold_on, cold_off], ignore_index=True)
    full = pd.concat([warm, hot], ignore_index=True)
    msgs = []
    maps = {m.key: m for m in generate_warmup_maps(
        warm, full, V, min_samples=1, trim_format="lambda", axis_tmot=np.array([20.0, 40.0, 80.0]),
        axis_load=np.array([40.0, 60.0]), axis_rpm=RPM, messages=msgs)}
    # (8 % cold - 2 % hot) = 6 %, not diluted to 1 % by the rows still at 1.0
    np.testing.assert_allclose(maps["kffwl"].values[:2][np.isfinite(maps["kffwl"].values[:2])], 6.0)
    assert any(m.startswith("  Warm-up rows: 40 of 80 rows left out") for m in msgs)
