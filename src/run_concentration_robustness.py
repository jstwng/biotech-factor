"""Task 3: concentration robustness -- drop top 3, cap scores at 95th pctl,
min-history 12m filter. Runs for BOTH uniform and adjusted specs; 4 regressions
per variant (2 ETFs x 2 specs).

Outputs:
  output/robustness/exclusion_top3.json
  output/robustness/score_capped.json
  output/robustness/min_history_12m.json
  output/robustness/robustness_summary.md
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, load_config

FF5_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
ROB = OUTPUT_DIR / "robustness"
SPECS = {"uniform": "pipeline_score_uniform", "adjusted": "pipeline_score_adjusted"}
EXCLUDE_TOP3 = {"GILD", "ABBV", "AMGN"}


def _load_bf():
    spec = importlib.util.spec_from_file_location("bf", Path(__file__).parent / "06_build_factor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _fit(y: pd.Series, X: pd.DataFrame, nw_lag: int):
    return sm.OLS(y, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lag})


def _regress(factor: pd.DataFrame, etf: pd.DataFrame, ff5: pd.DataFrame, nw_lag: int) -> dict:
    out = {}
    for t in ["IBB", "XBI"]:
        col = f"{t}_return"
        df = etf[["date", col]].rename(columns={col: "ret"}).merge(ff5, on="date").merge(factor[["date", "PR"]], on="date")
        df["excess"] = df["ret"] - df["RF"]
        df = df.dropna().reset_index(drop=True)
        if len(df) < 30:
            out[t] = {"error": "too few obs", "n": len(df)}
            continue
        m1 = _fit(df["excess"], df[FF5_FACTORS], nw_lag)
        m2 = _fit(df["excess"], df[FF5_FACTORS + ["PR"]], nw_lag)
        out[t] = {
            "n": int(len(df)),
            "ff5_adj_r2": float(m1.rsquared_adj),
            "ff5_pr_adj_r2": float(m2.rsquared_adj),
            "delta_adj_r2": float(m2.rsquared_adj - m1.rsquared_adj),
            "beta_PR": float(m2.params["PR"]),
            "se_PR": float(m2.bse["PR"]),
            "t_PR": float(m2.tvalues["PR"]),
            "p_PR": float(m2.pvalues["PR"]),
        }
    return out


def _run_variant(bf, scores: pd.DataFrame, returns: pd.DataFrame, cfg: dict, etf: pd.DataFrame, ff5: pd.DataFrame, **kwargs) -> dict:
    """Run both specs for one robustness variant, return dict keyed by spec."""
    nw_lag = cfg["stats"]["newey_west_lag"]
    results: dict = {}
    for spec_name, score_col in SPECS.items():
        factor = bf.build_factor(scores, returns, cfg, score_col=score_col, **kwargs)
        results[spec_name] = _regress(factor, etf, ff5, nw_lag)
    return results


def main() -> None:
    ROB.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    bf = _load_bf()

    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns_cleaned.csv", parse_dates=["date"])
    etf = pd.read_csv(DATA_RAW / "returns" / "etf_returns.csv", parse_dates=["date"])
    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])

    # Baseline (no robustness modifier) for comparison
    baseline = _run_variant(bf, scores, returns, cfg, etf, ff5)
    (ROB / "baseline.json").write_text(json.dumps(baseline, indent=2))

    # 3a. Exclude GILD, ABBV, AMGN
    ex3 = _run_variant(bf, scores, returns, cfg, etf, ff5, exclude_tickers=EXCLUDE_TOP3)
    (ROB / "exclusion_top3.json").write_text(json.dumps(ex3, indent=2))

    # 3b. Score capped at 95th percentile each month
    cap = _run_variant(bf, scores, returns, cfg, etf, ff5, score_cap_quantile=0.95)
    (ROB / "score_capped.json").write_text(json.dumps(cap, indent=2))

    # 3c. Minimum 12 months of return history
    mh = _run_variant(bf, scores, returns, cfg, etf, ff5, min_months_history=12)
    (ROB / "min_history_12m.json").write_text(json.dumps(mh, indent=2))

    # Summary table
    rows: list[str] = [
        "| Test | Spec | IBB beta | IBB t | IBB p | XBI beta | XBI t | XBI p | dAdjR2 IBB |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for label, r in [
        ("Baseline", baseline),
        ("Exclude top-3 (GILD/ABBV/AMGN)", ex3),
        ("Score capped 95th pctl", cap),
        ("Min 12m history", mh),
    ]:
        for spec_name in ["uniform", "adjusted"]:
            ibb = r[spec_name]["IBB"]
            xbi = r[spec_name]["XBI"]
            rows.append(
                f"| {label} | {spec_name} | {ibb['beta_PR']:+.4f} | {ibb['t_PR']:.2f} | {ibb['p_PR']:.4f} "
                f"| {xbi['beta_PR']:+.4f} | {xbi['t_PR']:.2f} | {xbi['p_PR']:.4f} | {ibb['delta_adj_r2']:+.4f} |"
            )
    (ROB / "robustness_summary.md").write_text("\n".join(rows) + "\n")

    # Also print to stdout
    for label, r in [("baseline", baseline), ("ex3", ex3), ("cap", cap), ("mh", mh)]:
        for spec in ["uniform", "adjusted"]:
            ibb = r[spec]["IBB"]; xbi = r[spec]["XBI"]
            print(f"{label:10s} {spec:8s} IBB p={ibb['p_PR']:.4f} beta={ibb['beta_PR']:+.4f} | XBI p={xbi['p_PR']:.4f} beta={xbi['beta_PR']:+.4f}")


if __name__ == "__main__":
    main()
