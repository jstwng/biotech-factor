"""Factor, residual, stability, and robustness diagnostics.

Saves structured JSON plus figures (factor correlation heatmap, residual
diagnostics per model, rolling beta_PR).
"""
from __future__ import annotations

import json
import pickle

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, get_logger, load_config

log = get_logger("diagnostics")

ETF_RETS = DATA_RAW / "returns" / "etf_returns.csv"
FF5 = DATA_RAW / "ff5" / "ff5_monthly.csv"
FACTOR = DATA_PROCESSED / "factor_returns.csv"
SCORES = DATA_PROCESSED / "pipeline_scores.parquet"
RESIDUALS = OUTPUT_DIR / "residuals.pkl"

FIG_DIR = OUTPUT_DIR / "figures"
TABLES_DIR = OUTPUT_DIR / "tables"

FF5_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]


def _merge(etf_col: str, etf: pd.DataFrame, ff5: pd.DataFrame, pr: pd.DataFrame, pr_col: str = "PR") -> pd.DataFrame:
    df = etf[["date", etf_col]].rename(columns={etf_col: "ret"})
    df = df.merge(ff5, on="date").merge(pr[["date", pr_col]].rename(columns={pr_col: "PR"}), on="date")
    df["excess"] = df["ret"] - df["RF"]
    return df.dropna().reset_index(drop=True)


def _fit(y: pd.Series, X: pd.DataFrame, nw_lag: int):
    return sm.OLS(y, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lag})


def factor_correlations(ff5: pd.DataFrame, pr: pd.DataFrame, pr_col: str = "PR") -> pd.DataFrame:
    merged = ff5.merge(pr[["date", pr_col]].rename(columns={pr_col: "PR"}), on="date")
    return merged[FF5_FACTORS + ["PR"]].corr()


def vif(df: pd.DataFrame) -> dict:
    X = sm.add_constant(df[FF5_FACTORS + ["PR"]]).values
    cols = ["const"] + FF5_FACTORS + ["PR"]
    return {c: float(variance_inflation_factor(X, i)) for i, c in enumerate(cols)}


def residual_tests(resid: pd.Series, exog: pd.DataFrame, lags: list[int]) -> dict:
    jb_stat, jb_p, _, _ = jarque_bera(resid)
    lb = acorr_ljungbox(resid, lags=lags, return_df=True)
    lb_out = {int(l): {"Q": float(lb.loc[l, "lb_stat"]), "p": float(lb.loc[l, "lb_pvalue"])} for l in lags}
    bp_lm, bp_p, _, _ = het_breuschpagan(resid, sm.add_constant(exog))
    return {
        "jarque_bera": {"stat": float(jb_stat), "p": float(jb_p)},
        "ljung_box": lb_out,
        "breusch_pagan": {"lm": float(bp_lm), "p": float(bp_p)},
    }


def residual_figure(dates: pd.Series, resid: pd.Series, path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), dpi=300)
    axes[0, 0].plot(dates, resid)
    axes[0, 0].set_title("Residuals over time")
    axes[0, 1].hist(resid, bins=20)
    axes[0, 1].set_title("Residual histogram")
    stats.probplot(resid, dist="norm", plot=axes[1, 0])
    axes[1, 0].set_title("Q-Q plot")
    sm.graphics.tsa.plot_acf(resid, ax=axes[1, 1], lags=min(24, len(resid) // 2))
    axes[1, 1].set_title("ACF")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def rolling_beta(df: pd.DataFrame, window: int, nw_lag: int) -> pd.DataFrame:
    out = []
    for i in range(window, len(df) + 1):
        sub = df.iloc[i - window : i]
        m = _fit(sub["excess"], sub[FF5_FACTORS + ["PR"]], nw_lag)
        out.append({
            "end_date": sub["date"].iloc[-1],
            "beta_PR": float(m.params["PR"]),
            "t_PR": float(m.tvalues["PR"]),
            "se_PR": float(m.bse["PR"]),
            "adj_r2": float(m.rsquared_adj),
        })
    return pd.DataFrame(out)


def cusum_stat(resid: np.ndarray) -> float:
    n = len(resid)
    sigma = resid.std(ddof=1)
    cs = np.cumsum(resid - resid.mean()) / (sigma * np.sqrt(n))
    return float(np.max(np.abs(cs)))


def _build_alt_factor(scores: pd.DataFrame, returns: pd.DataFrame, cfg: dict, q_lo: float, q_hi: float) -> pd.DataFrame:
    """Replicates Module 06 factor build with different quantile cutoffs."""
    lag = cfg["factor"]["return_lag"]
    rets = returns.copy()
    rets["date"] = pd.to_datetime(rets["date"])
    ret_pivot = rets.pivot(index="date", columns="ticker", values="return").sort_index()
    rows = []
    for t, sub in scores.groupby("date"):
        sub = sub[sub["pipeline_score"] > 0]
        if len(sub) < 10:
            continue
        short_cut = sub["pipeline_score"].quantile(q_lo)
        long_cut = sub["pipeline_score"].quantile(q_hi)
        longs = sub[sub["pipeline_score"] >= long_cut]["ticker"].tolist()
        shorts = sub[sub["pipeline_score"] <= short_cut]["ticker"].tolist()
        t_next = pd.Timestamp(t) + pd.offsets.MonthEnd(lag)
        if t_next not in ret_pivot.index:
            continue
        long_ret = ret_pivot.loc[t_next, [c for c in longs if c in ret_pivot.columns]].dropna()
        short_ret = ret_pivot.loc[t_next, [c for c in shorts if c in ret_pivot.columns]].dropna()
        if long_ret.empty or short_ret.empty:
            continue
        rows.append({"date": t_next, "PR": float(long_ret.mean() - short_ret.mean())})
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _load_build_factor_module():
    """Load 06_build_factor.py despite its leading-digit filename."""
    from importlib.util import spec_from_file_location, module_from_spec
    from pathlib import Path
    path = Path(__file__).parent / "06_build_factor.py"
    spec = spec_from_file_location("build_factor_mod", path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _uniform_factor(matched: pd.DataFrame, months: pd.DatetimeIndex, returns: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Override success rates to a flat per-phase average, no disease multiplier."""
    mod = _load_build_factor_module()
    base = cfg["success_rates"]["overall"]
    uniform = float(np.mean(list(base.values())))

    m = matched.dropna(subset=["ticker"]).copy()
    m["phase_norm"] = m["phase"].apply(mod.normalize_phase)
    m["area"] = m["conditions"].apply(mod.classify_area)
    m["contrib"] = uniform

    rows: list[dict] = []
    for t in months:
        mask = mod.active_mask(m, t)
        active = m.loc[mask, ["ticker", "contrib"]]
        if active.empty:
            continue
        agg = active.groupby("ticker")["contrib"].sum().rename("pipeline_score").to_frame()
        agg["date"] = t
        rows.append(agg.reset_index())
    if not rows:
        return pd.DataFrame(columns=["date", "PR"])
    scores = pd.concat(rows, ignore_index=True)[["date", "ticker", "pipeline_score"]]
    return _build_alt_factor(scores, returns, cfg, cfg["factor"]["quintile_short"], cfg["factor"]["quintile_long"])


def _beta_pr_for_factor(etf_df: pd.DataFrame, alt_pr: pd.DataFrame, nw_lag: int) -> dict:
    df = etf_df.drop(columns=["PR"]).merge(alt_pr, on="date", how="inner").dropna()
    if len(df) < 20:
        return {"beta_PR": None, "p_value": None, "n": len(df)}
    m = _fit(df["excess"], df[FF5_FACTORS + ["PR"]], nw_lag)
    return {
        "beta_PR": float(m.params["PR"]),
        "p_value": float(m.pvalues["PR"]),
        "n": int(len(df)),
    }


SPECS = {"uniform": "PR_uniform", "adjusted": "PR_adjusted"}


def _run_one_spec(spec_name: str, pr_col: str, etf, ff5, pr, residuals_spec, scores_spec, cfg) -> dict:
    nw_lag = cfg["stats"]["newey_west_lag"]
    lb_lags = cfg["stats"]["ljung_box_lags"]
    window = cfg["stats"]["rolling_window_months"]

    # Factor correlations + heatmap (one per spec)
    corr = factor_correlations(ff5, pr, pr_col=pr_col)
    fig, ax = plt.subplots(figsize=(6, 5), dpi=300)
    sns.heatmap(corr, annot=True, cmap="coolwarm", center=0, ax=ax, fmt=".2f")
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"factor_correlations_{spec_name}.png")
    plt.close(fig)

    result: dict = {
        "factor_correlations": corr.to_dict(),
        "models": {},
        "rolling": {},
        "sub_periods": {},
        "cross_sectional_dispersion": (
            scores_spec.groupby("date")[f"pipeline_score_{spec_name}"].std().dropna().describe().to_dict()
        ),
    }

    for etf_spec in cfg["etfs"]:
        t = etf_spec["ticker"]
        col = f"{t}_return"
        if col not in etf.columns:
            continue
        df = _merge(col, etf, ff5, pr, pr_col=pr_col)

        result["models"][t] = {
            "vif_ff5_pr": vif(df),
            "model1_residual_tests": residual_tests(pd.Series(residuals_spec[t]["model1"]), df[FF5_FACTORS], lb_lags),
            "model2_residual_tests": residual_tests(pd.Series(residuals_spec[t]["model2"]), df[FF5_FACTORS + ["PR"]], lb_lags),
            "cusum_model2": cusum_stat(np.array(residuals_spec[t]["model2"])),
        }
        residual_figure(df["date"], pd.Series(residuals_spec[t]["model1"]), FIG_DIR / f"residual_{spec_name}_{t}_FF5.png")
        residual_figure(df["date"], pd.Series(residuals_spec[t]["model2"]), FIG_DIR / f"residual_{spec_name}_{t}_FF5_PR.png")

        if len(df) >= window:
            rb = rolling_beta(df, window, nw_lag)
            result["rolling"][t] = rb.to_dict(orient="list")
            fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
            ax.plot(rb["end_date"], rb["beta_PR"])
            ax.fill_between(
                rb["end_date"],
                rb["beta_PR"] - 1.96 * rb["se_PR"],
                rb["beta_PR"] + 1.96 * rb["se_PR"],
                alpha=0.2,
            )
            ax.axhline(0, color="k", linewidth=0.5)
            ax.set_xlabel("Window end date")
            ax.set_ylabel(r"$\beta_{PR}$")
            fig.tight_layout()
            fig.savefig(FIG_DIR / f"rolling_beta_pr_{spec_name}_{t.lower()}.png")
            plt.close(fig)

        # Sub-period splits
        sp: dict = {}
        for label, lo, hi in [("2015_2019", "2015-01-01", "2019-12-31"), ("2020_2024", "2020-01-01", "2024-12-31")]:
            sub = df[(df["date"] >= lo) & (df["date"] <= hi)]
            if len(sub) < 24:
                sp[label] = {"beta_PR": None, "p_value": None, "n": len(sub)}
                continue
            m = _fit(sub["excess"], sub[FF5_FACTORS + ["PR"]], nw_lag)
            sp[label] = {
                "beta_PR": float(m.params["PR"]),
                "p_value": float(m.pvalues["PR"]),
                "n": int(len(sub)),
            }
        result["sub_periods"][t] = sp

    return result


def main() -> None:
    cfg = load_config()

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    etf = pd.read_csv(ETF_RETS, parse_dates=["date"])
    ff5 = pd.read_csv(FF5, parse_dates=["date"])
    pr = pd.read_csv(FACTOR, parse_dates=["date"])
    scores = pd.read_parquet(SCORES)
    all_residuals = pickle.loads(RESIDUALS.read_bytes())  # nested by spec

    diagnostics: dict = {}
    for spec_name, pr_col in SPECS.items():
        diagnostics[spec_name] = _run_one_spec(spec_name, pr_col, etf, ff5, pr, all_residuals[spec_name], scores, cfg)

    (OUTPUT_DIR / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, default=str))
    log.info("wrote diagnostics.json (dual-spec)")


if __name__ == "__main__":
    main()
