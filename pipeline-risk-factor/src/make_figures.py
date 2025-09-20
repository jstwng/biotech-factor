"""Task 5: publication-quality figures. 300 DPI, no titles (captions live in paper)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, load_config

FIG = OUTPUT_DIR / "figures"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.labelsize": 11})


def _cumulative_pr():
    pr = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])
    cum = (1 + pr["PR"]).cumprod() - 1
    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.plot(pr["date"], cum)
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative PR return")
    fig.tight_layout()
    fig.savefig(FIG / "pr_cumulative_return.png")
    plt.close(fig)


def _pipelinescore_distribution():
    cfg = load_config()
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    t = pd.Timestamp("2020-06-30")
    sub = scores[scores["date"] == t]
    sub = sub[sub["pipeline_score"] > 0]
    q_short = sub["pipeline_score"].quantile(cfg["factor"]["quintile_short"])
    q_long = sub["pipeline_score"].quantile(cfg["factor"]["quintile_long"])
    fig, ax = plt.subplots(figsize=(8, 4), dpi=300)
    ax.hist(sub["pipeline_score"], bins=40)
    ax.axvline(q_short, linestyle="--", color="C3", label=f"q20={q_short:.2f}")
    ax.axvline(q_long, linestyle="--", color="C2", label=f"q80={q_long:.2f}")
    ax.set_xlabel("PipelineScore (2020-06)")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "pipelinescore_distribution.png")
    plt.close(fig)


def _rolling_beta_figure(etf: str) -> None:
    import pickle
    import statsmodels.api as sm
    FF5 = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
    etf_df = pd.read_csv(DATA_RAW / "returns" / "etf_returns.csv", parse_dates=["date"])
    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
    pr = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])
    col = f"{etf}_return"
    df = etf_df[["date", col]].rename(columns={col: "ret"}).merge(ff5, on="date").merge(pr[["date", "PR"]], on="date")
    df["excess"] = df["ret"] - df["RF"]
    df = df.dropna().reset_index(drop=True)
    window = 36
    rows = []
    for i in range(window, len(df) + 1):
        sub = df.iloc[i - window : i]
        m = sm.OLS(sub["excess"], sm.add_constant(sub[FF5 + ["PR"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        rows.append({"end_date": sub["date"].iloc[-1], "beta": float(m.params["PR"]), "se": float(m.bse["PR"])})
    rb = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.plot(rb["end_date"], rb["beta"], color="C0")
    ax.fill_between(rb["end_date"], rb["beta"] - 1.96 * rb["se"], rb["beta"] + 1.96 * rb["se"], alpha=0.2, color="C0")
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("Window end date")
    ax.set_ylabel(r"$\beta_{PR}$")
    fig.tight_layout()
    fig.savefig(FIG / f"rolling_beta_pr_{etf.lower()}.png")
    plt.close(fig)


def _quintile_returns():
    """Average monthly excess return for Q1 through Q5 portfolios sorted on PipelineScore."""
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns.csv", parse_dates=["date"])
    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
    ret_pivot = returns.pivot(index="date", columns="ticker", values="return").sort_index()
    rf_map = dict(zip(ff5["date"], ff5["RF"]))

    bucket_returns: dict[int, list[float]] = {i: [] for i in range(5)}
    for t in sorted(scores["date"].unique()):
        sub = scores[scores["date"] == t]
        sub = sub[sub["pipeline_score"] > 0]
        if len(sub) < 20:
            continue
        sub = sub.copy()
        sub["q"] = pd.qcut(sub["pipeline_score"].rank(method="first"), 5, labels=False)
        t_next = pd.Timestamp(t) + pd.offsets.MonthEnd(1)
        if t_next not in ret_pivot.index:
            continue
        rf = rf_map.get(t_next, 0.0)
        for q, grp in sub.groupby("q"):
            tickers = [c for c in grp["ticker"] if c in ret_pivot.columns]
            r = ret_pivot.loc[t_next, tickers].dropna()
            if not r.empty:
                bucket_returns[int(q)].append(float(r.mean() - rf))

    means = [np.mean(bucket_returns[i]) if bucket_returns[i] else 0.0 for i in range(5)]
    fig, ax = plt.subplots(figsize=(7, 4), dpi=300)
    ax.bar([f"Q{i+1}" for i in range(5)], means, color=["C3", "C1", "C4", "C8", "C2"])
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("PipelineScore quintile (Q1=low, Q5=high)")
    ax.set_ylabel("Avg monthly excess return")
    fig.tight_layout()
    fig.savefig(FIG / "quintile_returns.png")
    plt.close(fig)


def _long_short_decomposition():
    pr = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.plot(pr["date"], pr["long_return"], label="Long (high PipelineScore)", color="C2", linewidth=0.9)
    ax.plot(pr["date"], pr["short_return"], label="Short (low PipelineScore)", color="C3", linewidth=0.9)
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("Date")
    ax.set_ylabel("Monthly portfolio return")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "long_short_decomposition.png")
    plt.close(fig)


if __name__ == "__main__":
    _cumulative_pr()
    _pipelinescore_distribution()
    _rolling_beta_figure("IBB")
    _rolling_beta_figure("XBI")
    _quintile_returns()
    _long_short_decomposition()
    print("figures written to", FIG)
