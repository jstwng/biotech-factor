"""Phase 5b: flipped (pipeline-risk-premium) factor backtest.

Builds on Phase 5's exclusion-top-3 factor series. Goes long the bottom-quintile
(high-pipeline-risk) names and short the top-quintile (low-pipeline-risk) names,
which is the sign-flip of the Phase-5 PR factor. Runs:
  - Standalone long-short
  - FF5-hedged (static + rolling)
  - IBB + w*flipped tilt overlay at w = {0.10, 0.25, 0.50}
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, load_config

OUT = OUTPUT_DIR / "backtest_flipped"
OUT.mkdir(parents=True, exist_ok=True)
FF5 = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
ROLL = 36
POST = pd.Timestamp("2020-01-01")
TILT_WEIGHTS = [0.10, 0.25, 0.50]


# -----------------------------------------------------------------------
# Stat helpers
# -----------------------------------------------------------------------
def annualized(monthly: pd.Series) -> tuple[float, float]:
    if len(monthly) == 0:
        return float("nan"), float("nan")
    geo = float((1 + monthly).prod() ** (12 / len(monthly)) - 1)
    vol = float(monthly.std(ddof=1) * np.sqrt(12))
    return geo, vol


def max_drawdown(monthly: pd.Series) -> float:
    if len(monthly) == 0:
        return float("nan")
    eq = (1 + monthly).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    return float(dd.min())


def _streak(series: pd.Series, positive: bool) -> int:
    best = cur = 0
    for v in series:
        if pd.isna(v):
            cur = 0
            continue
        if (v > 0) == positive:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def strat_stats(monthly: pd.Series) -> dict:
    monthly = monthly.dropna()
    if len(monthly) == 0:
        return {"n": 0}
    cum = float((1 + monthly).prod() - 1)
    geo, vol = annualized(monthly)
    sharpe = geo / vol if vol > 0 else float("nan")
    mdd = max_drawdown(monthly)
    calmar = geo / abs(mdd) if mdd < 0 else float("nan")
    hit = float((monthly > 0).mean())
    return {
        "n": int(len(monthly)),
        "cum_return": cum,
        "ann_return": geo,
        "ann_vol": vol,
        "sharpe": float(sharpe),
        "max_drawdown": mdd,
        "calmar": float(calmar),
        "hit_rate": hit,
        "best_month": float(monthly.max()),
        "worst_month": float(monthly.min()),
        "longest_win_streak": _streak(monthly, positive=True),
        "longest_loss_streak": _streak(monthly, positive=False),
    }


def split_periods(df: pd.DataFrame, col: str) -> dict:
    return {
        "full_sample": strat_stats(df[col]),
        "pre_2020": strat_stats(df[df["date"] < POST][col]),
        "post_2020": strat_stats(df[df["date"] >= POST][col]),
    }


# -----------------------------------------------------------------------
# Task 1: flipped factor series
# -----------------------------------------------------------------------
def build_flipped() -> pd.DataFrame:
    src = pd.read_csv(DATA_PROCESSED / "factor_returns_excl_top3.csv", parse_dates=["date"])
    out = pd.DataFrame({
        "date": src["date"],
        "PR_flipped": -src["PR_uniform_excl"],
        "long_return": src["short_return"],   # now long the old shorts (high pipeline risk)
        "short_return": src["long_return"],   # now short the old longs (low pipeline risk)
        "n_long": src["n_short"],
        "n_short": src["n_long"],
    })
    return out


def factor_stats(flipped: pd.DataFrame, ff5: pd.DataFrame) -> dict:
    pr = flipped["PR_flipped"]
    src = pd.read_csv(DATA_PROCESSED / "factor_returns_excl_top3.csv", parse_dates=["date"])
    merged = flipped.merge(ff5, on="date")
    return {
        "n": int(len(pr)),
        "mean": float(pr.mean()),
        "std": float(pr.std(ddof=1)),
        "skew": float(pr.skew()),
        "kurtosis": float(pr.kurt()),
        "min": float(pr.min()),
        "max": float(pr.max()),
        "sharpe_annualized": float((pr.mean() / pr.std(ddof=1)) * np.sqrt(12)),
        "autocorr_1": float(pr.autocorr(lag=1)),
        "autocorr_3": float(pr.autocorr(lag=3)),
        "correlations_with_ff5": {f: float(merged["PR_flipped"].corr(merged[f])) for f in FF5},
        "correlation_with_original_pr": float(
            flipped.merge(src, on="date")["PR_flipped"].corr(flipped.merge(src, on="date")["PR_uniform_excl"])
        ),
        "avg_n_long": float(flipped["n_long"].mean()),
        "avg_n_short": float(flipped["n_short"].mean()),
    }


# -----------------------------------------------------------------------
# Task 2c: FF5 exposure regression
# -----------------------------------------------------------------------
def ff5_exposure_regression(flipped: pd.DataFrame, ff5: pd.DataFrame, nw_lag: int):
    df = flipped[["date", "PR_flipped"]].merge(ff5, on="date")
    X = sm.add_constant(df[FF5])
    y = df["PR_flipped"]
    return sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lag})


# -----------------------------------------------------------------------
# Task 3: factor-hedged flipped strategy
# -----------------------------------------------------------------------
def static_hedged(flipped: pd.DataFrame, ff5: pd.DataFrame, model) -> pd.DataFrame:
    df = flipped[["date", "PR_flipped"]].merge(ff5, on="date")
    hedge = sum(float(model.params[f]) * df[f] for f in FF5)
    df["hedged_return"] = df["PR_flipped"] - hedge
    return df[["date", "hedged_return"]]


def rolling_hedged(flipped: pd.DataFrame, ff5: pd.DataFrame) -> pd.DataFrame:
    """For month t, use a 36-month window ending at t-1 (out-of-sample).
    Months 12..35 use an expanding window. Months 0..11 are NaN."""
    df = flipped[["date", "PR_flipped"]].merge(ff5, on="date").reset_index(drop=True)
    hedged = [np.nan] * len(df)
    for t in range(len(df)):
        if t < 12:
            continue
        window = df.iloc[: t] if t < ROLL else df.iloc[t - ROLL : t]
        if len(window) < 12:
            continue
        X = sm.add_constant(window[FF5])
        m = sm.OLS(window["PR_flipped"], X).fit()
        h = sum(float(m.params[f]) * df[f].iloc[t] for f in FF5)
        hedged[t] = float(df["PR_flipped"].iloc[t]) - h
    return pd.DataFrame({"date": df["date"], "hedged_return": hedged})


# -----------------------------------------------------------------------
# Task 4: IBB + w*flipped tilt
# -----------------------------------------------------------------------
def tilt_strategy(flipped: pd.DataFrame, ibb_excess: pd.DataFrame, w: float) -> pd.DataFrame:
    df = ibb_excess.merge(flipped[["date", "PR_flipped"]], on="date")
    df["tilt_return"] = df["excess"] + w * df["PR_flipped"]
    return df[["date", "excess", "PR_flipped", "tilt_return"]]


def tilt_stats(tilted: pd.DataFrame) -> dict:
    merged = tilted.copy()
    merged["diff"] = merged["tilt_return"] - merged["excess"]
    te = float(merged["diff"].std(ddof=1) * np.sqrt(12))  # annualised tracking error
    ann_diff = float(merged["diff"].mean() * 12)
    ir = ann_diff / te if te > 0 else float("nan")
    return {
        **strat_stats(merged["tilt_return"]),
        "tracking_error_ann": te,
        "ann_return_diff_vs_ibb": ann_diff,
        "information_ratio": float(ir),
    }


# -----------------------------------------------------------------------
# Return-contribution decomposition (Task 5f)
# -----------------------------------------------------------------------
def return_decomposition(model, ff5: pd.DataFrame) -> dict:
    """Annualised contribution of each factor to the flipped factor's return.
    Contribution = beta_k * mean(factor_k), then ×12 to annualise."""
    means = {f: float(ff5[f].mean()) for f in FF5}
    contrib = {f: float(model.params[f]) * means[f] * 12 for f in FF5}
    contrib["alpha"] = float(model.params["const"]) * 12
    contrib["total"] = sum(contrib.values())
    return contrib


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main() -> None:
    cfg = load_config()
    nw_lag = cfg["stats"]["newey_west_lag"]

    # --- T1 ---
    flipped = build_flipped()
    assert len(flipped) == 119
    assert flipped["PR_flipped"].mean() > 0
    out_csv = DATA_PROCESSED / "factor_returns_flipped.csv"
    flipped.to_csv(out_csv, index=False)
    print(f"T1: {out_csv} (mean={flipped['PR_flipped'].mean():+.4f}/mo, "
          f"Sharpe={float((flipped['PR_flipped'].mean()/flipped['PR_flipped'].std(ddof=1))*np.sqrt(12)):+.3f})")

    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
    fstats = factor_stats(flipped, ff5)
    (OUT / "flipped_factor_stats.json").write_text(json.dumps(fstats, indent=2))

    # --- T2a, T2b ---
    standalone_stats = split_periods(flipped.rename(columns={"PR_flipped": "ret"}), "ret")
    (OUT / "standalone_stats.json").write_text(json.dumps(standalone_stats, indent=2, default=str))

    # --- T2c: FF5 exposure regression ---
    model = ff5_exposure_regression(flipped, ff5, nw_lag)
    ff5_reg_dict = {
        "coefficients": {
            name: {
                "estimate": float(model.params[name]),
                "std_error": float(model.bse[name]),
                "t_stat": float(model.tvalues[name]),
                "p_value": float(model.pvalues[name]),
            } for name in model.params.index
        },
        "adj_r_squared": float(model.rsquared_adj),
        "n_obs": int(model.nobs),
    }
    (OUT / "ff5_exposure_regression.json").write_text(json.dumps(ff5_reg_dict, indent=2))

    # --- T3 hedged strategies ---
    static_h = static_hedged(flipped, ff5, model)
    rolling_h = rolling_hedged(flipped, ff5)
    static_h.to_csv(OUT / "hedged_static.csv", index=False)
    rolling_h.to_csv(OUT / "hedged_rolling.csv", index=False)
    hedged_stats = {
        "static": split_periods(static_h.rename(columns={"hedged_return": "ret"}), "ret"),
        "rolling": split_periods(rolling_h.rename(columns={"hedged_return": "ret"}), "ret"),
    }
    (OUT / "hedged_stats.json").write_text(json.dumps(hedged_stats, indent=2, default=str))

    # --- T4 IBB tilt strategies ---
    etf = pd.read_csv(DATA_RAW / "returns" / "etf_returns.csv", parse_dates=["date"])
    ibb_excess = etf[["date", "IBB_return"]].merge(ff5[["date", "RF"]], on="date")
    ibb_excess["excess"] = ibb_excess["IBB_return"] - ibb_excess["RF"]
    ibb_excess = ibb_excess[["date", "excess"]]

    ibb_only_stats = strat_stats(
        ibb_excess.merge(flipped[["date"]], on="date")["excess"]
    )

    tilt_results: dict = {
        "w_0.00_ibb_only": {
            **ibb_only_stats,
            "tracking_error_ann": 0.0,
            "ann_return_diff_vs_ibb": 0.0,
            "information_ratio": None,
        }
    }
    tilt_series: dict[float, pd.DataFrame] = {}
    for w in TILT_WEIGHTS:
        t = tilt_strategy(flipped, ibb_excess, w)
        tilt_series[w] = t
        tilt_results[f"w_{w:.2f}"] = tilt_stats(t)
    (OUT / "tilt_stats.json").write_text(json.dumps(tilt_results, indent=2, default=str))

    # Save tilt time series
    tilt_wide = ibb_excess.merge(flipped[["date", "PR_flipped"]], on="date")
    for w in TILT_WEIGHTS:
        tilt_wide[f"tilt_{w:.2f}"] = tilt_wide["excess"] + w * tilt_wide["PR_flipped"]
    tilt_wide.to_csv(OUT / "tilt_returns.csv", index=False)

    # Breakeven w (min w in [0, 1] where cum tilt return >= cum IBB excess)
    ibb_cum = float((1 + tilt_wide["excess"]).prod() - 1)
    breakeven = None
    ws = np.arange(0.0, 1.001, 0.01)
    for w in ws:
        tilt = tilt_wide["excess"] + w * tilt_wide["PR_flipped"]
        if float((1 + tilt).prod() - 1) >= ibb_cum:
            if w > 1e-6:  # skip w=0
                breakeven = float(w)
                break
    breakeven_result = {"breakeven_w": breakeven, "ibb_cum_return": ibb_cum}
    (OUT / "breakeven.json").write_text(json.dumps(breakeven_result, indent=2))

    # --- Decomposition (for figure 5f and summary) ---
    decomp = return_decomposition(model, ff5.loc[ff5["date"].isin(flipped["date"])])
    (OUT / "return_decomposition.json").write_text(json.dumps(decomp, indent=2))

    # --- Print summary for the report ---
    print("\nFF5 exposure regression:")
    for n, c in ff5_reg_dict["coefficients"].items():
        print(f"  {n:10s} {c['estimate']:+.4f}  t={c['t_stat']:+.2f}  p={c['p_value']:.4f}")
    print(f"  adj_R2={ff5_reg_dict['adj_r_squared']:.4f}")

    print("\nStandalone flipped strategy:")
    for p in ("full_sample", "pre_2020", "post_2020"):
        s = standalone_stats[p]
        print(f"  [{p}] n={s['n']} cum={s['cum_return']*100:+.2f}% ann={s['ann_return']*100:+.2f}% "
              f"vol={s['ann_vol']*100:.2f}% sharpe={s['sharpe']:.3f} mdd={s['max_drawdown']*100:.2f}% "
              f"hit={s['hit_rate']*100:.1f}% win_streak={s['longest_win_streak']} loss_streak={s['longest_loss_streak']}")

    print("\nHedged (static):")
    for p in ("full_sample", "pre_2020", "post_2020"):
        s = hedged_stats["static"][p]
        print(f"  [{p}] cum={s['cum_return']*100:+.2f}% ann={s['ann_return']*100:+.2f}% sharpe={s['sharpe']:.3f}")
    print("\nHedged (rolling):")
    for p in ("full_sample", "pre_2020", "post_2020"):
        s = hedged_stats["rolling"][p]
        print(f"  [{p}] cum={s['cum_return']*100:+.2f}% ann={s['ann_return']*100:+.2f}% sharpe={s['sharpe']:.3f}")

    print("\nIBB tilt:")
    for key in sorted(tilt_results.keys()):
        s = tilt_results[key]
        ir = s.get("information_ratio")
        ir_str = f"IR={ir:+.3f}" if isinstance(ir, (int, float)) and not np.isnan(ir) and ir is not None else "IR=--"
        print(f"  {key}: cum={s['cum_return']*100:+.2f}% ann={s['ann_return']*100:+.2f}% "
              f"sharpe={s['sharpe']:.3f} mdd={s['max_drawdown']*100:.2f}% {ir_str}")
    print(f"\nbreakeven w = {breakeven} (ibb cum={ibb_cum*100:+.2f}%)")

    print("\nReturn decomposition (annualised, flipped factor):")
    for k, v in decomp.items():
        print(f"  {k:10s} {v*100:+.2f}%")


if __name__ == "__main__":
    main()
