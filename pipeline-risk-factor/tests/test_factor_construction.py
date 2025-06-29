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


bf = _load("build_factor", "06_build_factor.py")


def test_normalize_phase_variants():
    assert bf.normalize_phase("PHASE2") == "Phase 2"
    assert bf.normalize_phase("PHASE1,PHASE2") == "Phase 1/Phase 2"
    assert bf.normalize_phase("NA") is None
    assert bf.normalize_phase("") is None


def test_classify_area():
    assert bf.classify_area("Breast Cancer") == "Oncology"
    assert bf.classify_area("HIV Infection") == "Infectious Disease"
    assert bf.classify_area("Parkinson's Disease") == "CNS/Neurology"
    assert bf.classify_area("Widget") == "Other"


def test_active_mask_logic():
    t = pd.Timestamp("2020-06-30")
    df = pd.DataFrame([
        {"start_date": "2019-01-01", "primary_completion_date": "2020-12-31", "overall_status": "RECRUITING"},
        {"start_date": "2019-01-01", "primary_completion_date": "2020-01-01", "overall_status": "COMPLETED"},
        {"start_date": "2021-01-01", "primary_completion_date": None, "overall_status": "NOT_YET_RECRUITING"},
        {"start_date": "2019-01-01", "primary_completion_date": None, "overall_status": "RECRUITING"},
    ])
    mask = bf.active_mask(df, t)
    assert mask.tolist() == [True, False, False, True]


def test_build_factor_quintiles():
    cfg = {
        "factor": {"quintile_long": 0.80, "quintile_short": 0.20, "return_lag": 1, "weighting": "equal"},
    }
    dates = [pd.Timestamp("2020-01-31")] * 10
    tickers = [f"T{i}" for i in range(10)]
    scores = pd.DataFrame({"date": dates, "ticker": tickers, "pipeline_score": np.arange(10, dtype=float) + 1})

    # returns realized one month later
    ret_date = pd.Timestamp("2020-02-29")
    returns = pd.DataFrame({
        "date": [ret_date] * 10,
        "ticker": tickers,
        "return": [0.10, 0.08, 0.06, 0.04, 0.02, 0.00, -0.02, -0.04, -0.06, -0.08],
    })
    factor = bf.build_factor(scores, returns, cfg)
    assert len(factor) == 1
    row = factor.iloc[0]
    # longs: top 20% (scores 9, 10), shorts: bottom 20% (scores 1, 2)
    assert row["n_long"] >= 2 and row["n_short"] >= 2
    # long had the worst returns in our setup (T8=-0.06, T9=-0.08); PR should be negative
    assert row["long_return"] < row["short_return"]
