"""Phase 5: beta-neutral backtest of the exclusion-top-3 uniform IBB
specification. Reconstructs the excl-top-3 factor return series, performs
return attribution (static + rolling), runs the static- and rolling-hedge
strategies, computes summary stats, and writes BACKTEST_SUMMARY.md.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, load_config

OUT = OUTPUT_DIR / "backtest"
FF5_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
EXCLUDE_TOP3 = {"GILD", "ABBV", "AMGN"}
ROLL_WINDOW = 36


def _load_bf():
    spec = importlib.util.spec_from_file_location("bf", Path(__file__).parent / "06_build_factor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# --------------------------------------------------------------------------
# Task 1: reconstruct the exclusion-top-3 factor return series
# --------------------------------------------------------------------------
def build_excl_factor(cfg: dict) -> pd.DataFrame:
    bf = _load_bf()
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    rets = pd.read_csv(DATA_RAW / "returns" / "constituent_returns_cleaned.csv", parse_dates=["date"])
    f = bf.build_factor(scores, rets, cfg, score_col="pipeline_score_uniform", exclude_tickers=EXCLUDE_TOP3)
    f = f.rename(columns={"PR": "PR_uniform_excl"})
    return f[["date", "PR_uniform_excl", "n_long", "n_short", "long_return", "short_return"]]


# --------------------------------------------------------------------------
# Helpers shared across attribution + backtest
# --------------------------------------------------------------------------
def merged_frame(excl_factor: pd.DataFrame) -> pd.DataFrame:
    etf = pd.read_csv(DATA_RAW / "returns" / "etf_returns.csv", parse_dates=["date"])
    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
    df = etf[["date", "IBB_return"]].rename(columns={"IBB_return": "ret"})
    df = df.merge(ff5, on="date").merge(excl_factor[["date", "PR_uniform_excl"]], on="date")
    df["excess"] = df["ret"] - df["RF"]
    return df.dropna().reset_index(drop=True)


def fit_full(df: pd.DataFrame, nw_lag: int):
    X = sm.add_constant(df[FF5_FACTORS + ["PR_uniform_excl"]])
    return sm.OLS(df["excess"], X).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lag})


def fit_window(window_df: pd.DataFrame):
    X = sm.add_constant(window_df[FF5_FACTORS + ["PR_uniform_excl"]])
    return sm.OLS(window_df["excess"], X).fit()


def annualized(monthly: pd.Series) -> tuple[float, float]:
    """(geometric ann. return, ann. vol) from a monthly return series."""
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


def strat_stats(monthly: pd.Series) -> dict:
    if len(monthly) == 0:
        return {"n": 0, "cum_return": None, "ann_return": None, "ann_vol": None,
                "sharpe": None, "max_drawdown": None, "calmar": None, "hit_rate": None}
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
    }


# --------------------------------------------------------------------------
# Task 2: return attribution
# --------------------------------------------------------------------------
def static_attribution(df: pd.DataFrame, model) -> pd.DataFrame:
    """Decomposes IBB excess into alpha + FF5 contribution + PR contribution + residual."""
    a = pd.DataFrame({"date": df["date"]})
    alpha = float(model.params["const"])
    a["alpha"] = alpha
    a["ff5_explained"] = sum(float(model.params[f]) * df[f] for f in FF5_FACTORS)
    a["pr_attr"] = float(model.params["PR_uniform_excl"]) * df["PR_uniform_excl"]
    a["residual"] = df["excess"] - a["alpha"] - a["ff5_explained"] - a["pr_attr"]
    a["ibb_excess"] = df["excess"]
    # identity check
    diff = (a["alpha"] + a["ff5_explained"] + a["pr_attr"] + a["residual"] - a["ibb_excess"]).abs().max()
    assert diff < 1e-10, f"identity violated: max abs diff {diff}"
    return a


def rolling_attribution(df: pd.DataFrame, full_beta_pr: float) -> pd.DataFrame:
    """Time-varying beta_PR via 36-month rolling regression. Months without
    enough history fall back to the full-sample beta."""
    out = pd.DataFrame({"date": df["date"]})
    rolling_beta = []
    for i in range(len(df)):
        if i + 1 < ROLL_WINDOW:
            rolling_beta.append(full_beta_pr)
            continue
        window = df.iloc[i + 1 - ROLL_WINDOW : i + 1]
        m = fit_window(window)
        rolling_beta.append(float(m.params["PR_uniform_excl"]))
    out["beta_pr_rolling"] = rolling_beta
    out["pr_attr_rolling"] = out["beta_pr_rolling"] * df["PR_uniform_excl"]
    return out


# --------------------------------------------------------------------------
# Task 3: hedged-strategy backtests
# --------------------------------------------------------------------------
def static_hedge_strategy(df: pd.DataFrame, model) -> pd.DataFrame:
    out = pd.DataFrame({"date": df["date"]})
    hedge = sum(float(model.params[f]) * df[f] for f in FF5_FACTORS)
    out["strategy_return"] = df["excess"] - hedge
    return out


def rolling_hedge_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """For month T, hedge betas come from a 36-month window ending at T-1.
    Months with insufficient history fall back to an expanding-window fit
    starting from month 12 (so we have a strategy from month 13 onward)."""
    out = pd.DataFrame({"date": df["date"]})
    strategy = [np.nan] * len(df)
    rolling_betas = {f: [np.nan] * len(df) for f in FF5_FACTORS}
    rolling_betas["PR_uniform_excl"] = [np.nan] * len(df)
    rolling_betas["const"] = [np.nan] * len(df)

    for t in range(len(df)):
        if t < 12:
            continue  # no hedge produced before month 12
        if t < ROLL_WINDOW:
            window = df.iloc[: t]  # expanding window, all months strictly before t
        else:
            window = df.iloc[t - ROLL_WINDOW : t]  # 36-month window ending at t-1
        if len(window) < 12:
            continue
        m = fit_window(window)
        hedge = sum(float(m.params[f]) * df[f].iloc[t] for f in FF5_FACTORS)
        strategy[t] = float(df["excess"].iloc[t]) - hedge
        for f in FF5_FACTORS + ["PR_uniform_excl", "const"]:
            rolling_betas[f][t] = float(m.params[f])

    out["strategy_return"] = strategy
    for f, vals in rolling_betas.items():
        out[f"beta_{f}"] = vals
    return out


def rolling_beta_with_se(df: pd.DataFrame) -> pd.DataFrame:
    """Standalone series of rolling beta_PR + standard error for figure 4c.
    Window ending AT T (centred on the actual estimation period for plotting)."""
    out = []
    for t in range(ROLL_WINDOW - 1, len(df)):
        window = df.iloc[t + 1 - ROLL_WINDOW : t + 1]
        m = fit_window(window)
        out.append({
            "date": df["date"].iloc[t],
            "beta_PR": float(m.params["PR_uniform_excl"]),
            "se_PR": float(m.bse["PR_uniform_excl"]),
        })
    return pd.DataFrame(out)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def split_periods(returns_df: pd.DataFrame, col: str) -> dict:
    pre = returns_df[returns_df["date"] < "2020-01-01"][col].dropna()
    post = returns_df[returns_df["date"] >= "2020-01-01"][col].dropna()
    full = returns_df[col].dropna()
    return {"full_sample": strat_stats(full), "pre_2020": strat_stats(pre), "post_2020": strat_stats(post)}


def annual_table(returns_df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = returns_df.copy()
    df["year"] = df["date"].dt.year
    rows = []
    for year, g in df.groupby("year"):
        row = {"year": int(year)}
        for c in cols:
            s = g[c].dropna()
            row[c] = float((1 + s).prod() - 1) if len(s) else None
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    nw_lag = cfg["stats"]["newey_west_lag"]

    # --- T1 ---
    excl = build_excl_factor(cfg)
    out_csv = DATA_PROCESSED / "factor_returns_excl_top3.csv"
    excl.to_csv(out_csv, index=False)
    assert len(excl) == 119, f"expected 119 obs, got {len(excl)}"
    assert excl["PR_uniform_excl"].notna().all()
    assert excl["PR_uniform_excl"].std() > 1e-4
    print(f"T1: wrote {out_csv} (n={len(excl)}, std={excl['PR_uniform_excl'].std():.4f})")

    # --- T2a static attribution ---
    df = merged_frame(excl)
    full_model = fit_full(df, nw_lag)
    static = static_attribution(df, full_model)

    # cumulative series: both multiplicative (real-money compounding) and
    # additive (sum of monthly contributions). Additive series satisfy the
    # decomposition identity exactly month by month and at every horizon.
    static_cum = pd.DataFrame({"date": static["date"]})
    for col in ["alpha", "ff5_explained", "pr_attr", "residual", "ibb_excess"]:
        static_cum[f"cum_{col}"] = (1 + static[col]).cumprod() - 1
        static_cum[f"sumcum_{col}"] = static[col].cumsum()

    # --- T2b rolling attribution ---
    full_beta_pr = float(full_model.params["PR_uniform_excl"])
    rolling = rolling_attribution(df, full_beta_pr)
    static["pr_attr_rolling"] = rolling["pr_attr_rolling"]
    static["beta_pr_rolling"] = rolling["beta_pr_rolling"]
    static_cum["cum_pr_attr_rolling"] = (1 + static["pr_attr_rolling"]).cumprod() - 1

    static.to_csv(OUT / "attribution.csv", index=False)
    static_cum.to_csv(OUT / "attribution_cumulative.csv", index=False)

    # --- T3a hedged strategies ---
    static_strat = static_hedge_strategy(df, full_model)
    rolling_strat = rolling_hedge_strategy(df)
    static_strat.to_csv(OUT / "strategy_static.csv", index=False)
    rolling_strat.to_csv(OUT / "strategy_rolling.csv", index=False)

    rb = rolling_beta_with_se(df)
    rb.to_csv(OUT / "rolling_beta_pr_with_se.csv", index=False)

    # --- T3b stats ---
    stats = {
        "regression_full_sample": {
            "coefficients": {
                name: {
                    "estimate": float(full_model.params[name]),
                    "std_error": float(full_model.bse[name]),
                    "t_stat": float(full_model.tvalues[name]),
                    "p_value": float(full_model.pvalues[name]),
                } for name in full_model.params.index
            },
            "adj_r_squared": float(full_model.rsquared_adj),
            "n_obs": int(full_model.nobs),
        },
        "static_hedge": split_periods(static_strat, "strategy_return"),
        "rolling_hedge": split_periods(rolling_strat, "strategy_return"),
    }
    (OUT / "backtest_stats.json").write_text(json.dumps(stats, indent=2, default=str))

    # --- annual table ---
    annual_df = pd.DataFrame({"date": df["date"], "ibb_excess": df["excess"]})
    annual_df["ff5_explained"] = static["ff5_explained"]
    annual_df["strategy_rolling"] = rolling_strat["strategy_return"]
    annual_df["strategy_static"] = static_strat["strategy_return"]
    annual = annual_table(annual_df, ["ibb_excess", "ff5_explained", "strategy_rolling", "strategy_static"])
    annual.to_csv(OUT / "annual_returns.csv", index=False)

    print("\nT2a static (full sample) cumulative attribution:")
    last = static_cum.iloc[-1]
    print(f"  cum FF5-explained:  {last['cum_ff5_explained']*100:+.2f}%")
    print(f"  cum PR-attributable: {last['cum_pr_attr']*100:+.2f}%")
    print(f"  cum alpha:          {last['cum_alpha']*100:+.2f}%")
    print(f"  cum residual:       {last['cum_residual']*100:+.2f}%")
    print(f"  cum IBB excess:     {last['cum_ibb_excess']*100:+.2f}%")

    print("\nT3 strategy stats:")
    for label in ("static_hedge", "rolling_hedge"):
        for period in ("full_sample", "pre_2020", "post_2020"):
            s = stats[label][period]
            if s["n"] == 0:
                continue
            print(f"  [{label} {period}] n={s['n']} cum={s['cum_return']*100:+.2f}% "
                  f"ann={s['ann_return']*100:+.2f}% vol={s['ann_vol']*100:.2f}% "
                  f"sharpe={s['sharpe']:.3f} mdd={s['max_drawdown']*100:.2f}% hit={s['hit_rate']*100:.1f}%")

    print("\nAnnual returns:")
    print(annual.to_string(index=False))

    print(f"\nbeta_PR (full sample) = {full_beta_pr:.4f}")
    print(f"alpha (annualised) = {(1 + float(full_model.params['const']))**12 - 1:.4%}")


if __name__ == "__main__":
    main()
