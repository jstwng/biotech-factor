import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent.parent / "src"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SRC / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rg = _load("regressions", "07_run_regressions.py")


def test_fit_and_summary_shape():
    rng = np.random.default_rng(42)
    n = 120
    X = pd.DataFrame({
        "Mkt-RF": rng.normal(0, 0.05, n),
        "SMB": rng.normal(0, 0.03, n),
        "HML": rng.normal(0, 0.03, n),
        "RMW": rng.normal(0, 0.02, n),
        "CMA": rng.normal(0, 0.02, n),
    })
    beta = np.array([0.002, 1.2, 0.4, -0.1, 0.0, 0.0])  # alpha, 5 slopes
    y = beta[0] + X.values @ beta[1:] + rng.normal(0, 0.01, n)
    model = rg._fit(pd.Series(y), X, nw_lag=3)
    s = rg._model_summary(model)
    assert s["n_obs"] == n
    assert "Mkt-RF" in s["coefficients"]
    assert 0 <= s["adj_r_squared"] <= 1


def test_partial_f_adds_information():
    rng = np.random.default_rng(1)
    n = 120
    X = pd.DataFrame({f"f{i}": rng.normal(0, 0.03, n) for i in range(5)})
    pr = rng.normal(0, 0.02, n)
    y = 0.001 + X.values.sum(axis=1) * 0.5 + 0.7 * pr + rng.normal(0, 0.005, n)
    m1 = rg._fit(pd.Series(y), X, 3)
    X2 = X.copy()
    X2["PR"] = pr
    m2 = rg._fit(pd.Series(y), X2, 3)
    pf = rg._partial_f(m1, m2, n)
    # Adding an informative regressor should yield a small p-value
    assert pf["p_value"] < 0.05
    assert m2.rsquared_adj > m1.rsquared_adj
