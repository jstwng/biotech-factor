"""Task 6: publication-quality figures, dual specification where applicable."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, load_config

FIG = OUTPUT_DIR / "figures"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.labelsize": 11})

FF5 = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]


def _cumulative_pr():
    pr = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])
    cum_u = (1 + pr["PR_uniform"]).cumprod() - 1
    cum_a = (1 + pr["PR_adjusted"]).cumprod() - 1
    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.plot(pr["date"], cum_u, label="PR (uniform, primary)", color="C0")
    ax.plot(pr["date"], cum_a, label="PR (disease-adjusted)", color="C1", linestyle="--")
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative PR return")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "pr_cumulative_return.png")
    plt.close(fig)


def _pipelinescore_distribution():
    cfg = load_config()
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    t = pd.Timestamp("2020-06-30")
    sub = scores[scores["date"] == t]
    sub = sub[sub["pipeline_score_uniform"] > 0]
    q_short = sub["pipeline_score_uniform"].quantile(cfg["factor"]["quintile_short"])
    q_long = sub["pipeline_score_uniform"].quantile(cfg["factor"]["quintile_long"])
    fig, ax = plt.subplots(figsize=(8, 4), dpi=300)
    ax.hist(sub["pipeline_score_uniform"], bins=40)
    ax.axvline(q_short, linestyle="--", color="C3", label=f"q20={q_short:.2f}")
    ax.axvline(q_long, linestyle="--", color="C2", label=f"q80={q_long:.2f}")
    ax.set_xlabel("PipelineScore (uniform, 2020-06)")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "pipelinescore_distribution.png")
    plt.close(fig)


def _rolling_beta(etf: str) -> None:
    etf_df = pd.read_csv(DATA_RAW / "returns" / "etf_returns.csv", parse_dates=["date"])
    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
    pr = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])
    col = f"{etf}_return"
    window = 36

    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    colors = {"uniform": "C0", "adjusted": "C1"}
    for spec_name, pr_col in [("uniform", "PR_uniform"), ("adjusted", "PR_adjusted")]:
        df = etf_df[["date", col]].rename(columns={col: "ret"}).merge(ff5, on="date").merge(pr[["date", pr_col]].rename(columns={pr_col: "PR"}), on="date")
        df["excess"] = df["ret"] - df["RF"]
        df = df.dropna().reset_index(drop=True)
        rows = []
        for i in range(window, len(df) + 1):
            sub = df.iloc[i - window : i]
            m = sm.OLS(sub["excess"], sm.add_constant(sub[FF5 + ["PR"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
            rows.append({"end_date": sub["date"].iloc[-1], "beta": float(m.params["PR"]), "se": float(m.bse["PR"])})
        rb = pd.DataFrame(rows)
        ax.plot(rb["end_date"], rb["beta"], label=spec_name, color=colors[spec_name])
        ax.fill_between(rb["end_date"], rb["beta"] - 1.96 * rb["se"], rb["beta"] + 1.96 * rb["se"], alpha=0.15, color=colors[spec_name])
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("Window end date")
    ax.set_ylabel(r"$\beta_{PR}$")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / f"rolling_beta_pr_{etf.lower()}.png")
    plt.close(fig)


def _quintile_returns():
    """Quintile portfolios sorted by score_uniform. Side-by-side bars for uniform vs adjusted."""
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns_cleaned.csv", parse_dates=["date"])
    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
    ret_pivot = returns.pivot(index="date", columns="ticker", values="return").sort_index()
    rf_map = dict(zip(ff5["date"], ff5["RF"]))

    def bucket_means(score_col: str) -> list[float]:
        buckets: dict[int, list[float]] = {i: [] for i in range(5)}
        for t in sorted(scores["date"].unique()):
            sub = scores[scores["date"] == t]
            sub = sub[sub[score_col] > 0]
            if len(sub) < 20:
                continue
            sub = sub.copy()
            sub["q"] = pd.qcut(sub[score_col].rank(method="first"), 5, labels=False)
            t_next = pd.Timestamp(t) + pd.offsets.MonthEnd(1)
            if t_next not in ret_pivot.index:
                continue
            rf = rf_map.get(t_next, 0.0)
            for q, grp in sub.groupby("q"):
                tickers = [c for c in grp["ticker"] if c in ret_pivot.columns]
                r = ret_pivot.loc[t_next, tickers].dropna()
                if not r.empty:
                    buckets[int(q)].append(float(r.mean() - rf))
        return [np.mean(buckets[i]) if buckets[i] else 0.0 for i in range(5)]

    uniform_bars = bucket_means("pipeline_score_uniform")
    adjusted_bars = bucket_means("pipeline_score_adjusted")
    x = np.arange(5)
    w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4), dpi=300)
    ax.bar(x - w/2, uniform_bars, width=w, label="Uniform", color="C0")
    ax.bar(x + w/2, adjusted_bars, width=w, label="Adjusted", color="C1")
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q{i+1}" for i in range(5)])
    ax.set_xlabel("PipelineScore quintile (Q1=low, Q5=high)")
    ax.set_ylabel("Avg monthly excess return")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "quintile_returns.png")
    plt.close(fig)


def _long_short_decomposition():
    pr = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.plot(pr["date"], pr["long_return_uniform"], label="Long (high score, uniform)", color="C2", linewidth=0.9)
    ax.plot(pr["date"], pr["short_return_uniform"], label="Short (low score, uniform)", color="C3", linewidth=0.9)
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("Date")
    ax.set_ylabel("Monthly portfolio return")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "long_short_decomposition.png")
    plt.close(fig)


def _score_concentration():
    """Stacked area: share of long-quintile score held by top 1, top 3, top 5 firms."""
    cfg = load_config()
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    q_hi = cfg["factor"]["quintile_long"]
    rows = []
    for t in sorted(scores["date"].unique()):
        sub = scores[scores["date"] == t]
        sub = sub[sub["pipeline_score_uniform"] > 0]
        if len(sub) < 10:
            continue
        cut = sub["pipeline_score_uniform"].quantile(q_hi)
        long_set = sub[sub["pipeline_score_uniform"] >= cut].sort_values("pipeline_score_uniform", ascending=False)
        total = long_set["pipeline_score_uniform"].sum()
        if total == 0:
            continue
        top1 = long_set.head(1)["pipeline_score_uniform"].sum() / total
        top3 = long_set.head(3)["pipeline_score_uniform"].sum() / total
        top5 = long_set.head(5)["pipeline_score_uniform"].sum() / total
        rows.append({"date": t, "top1": top1, "top3": top3, "top5": top5})
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.fill_between(df["date"], 0, df["top1"], alpha=0.85, label="Top 1")
    ax.fill_between(df["date"], df["top1"], df["top3"], alpha=0.65, label="Top 2-3")
    ax.fill_between(df["date"], df["top3"], df["top5"], alpha=0.45, label="Top 4-5")
    ax.set_ylim(0, 1)
    ax.set_xlabel("Date")
    ax.set_ylabel("Share of long-quintile total score")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "score_concentration.png")
    plt.close(fig)


def _universe_funnel():
    """Attrition bar chart for 4 sample months."""
    cfg = load_config()
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns_cleaned.csv", parse_dates=["date"])
    ibb = pd.read_csv(DATA_RAW / "constituents" / "ibb_constituents.csv")
    q_lo = cfg["factor"]["quintile_short"]
    q_hi = cfg["factor"]["quintile_long"]

    dates = [pd.Timestamp("2015-06-30"), pd.Timestamp("2018-06-29"), pd.Timestamp("2021-06-30"), pd.Timestamp("2024-06-28")]
    universe = set(ibb["ticker"])
    ret_by_month = returns.groupby("date")["ticker"].apply(set).to_dict()

    labels = ["IBB constituents", "Scored > 0", "+ Return data", "In long", "In short"]
    values_by_date = {}
    for t in dates:
        s = scores[scores["date"] == t]
        s = s[s["pipeline_score_uniform"] > 0]
        t_next = pd.Timestamp(t) + pd.offsets.MonthEnd(1)
        rets = ret_by_month.get(t_next, set())
        scored = set(s["ticker"]) & universe
        with_rets = scored & rets
        if len(s) >= 10:
            short_cut = s["pipeline_score_uniform"].quantile(q_lo)
            long_cut = s["pipeline_score_uniform"].quantile(q_hi)
            longs = set(s[s["pipeline_score_uniform"] >= long_cut]["ticker"]) & universe & rets
            shorts = set(s[s["pipeline_score_uniform"] <= short_cut]["ticker"]) & universe & rets
        else:
            longs, shorts = set(), set()
        values_by_date[t] = [len(universe), len(scored), len(with_rets), len(longs), len(shorts)]

    fig, ax = plt.subplots(figsize=(10, 4), dpi=300)
    x = np.arange(len(labels))
    w = 0.2
    for i, t in enumerate(dates):
        ax.bar(x + (i - 1.5) * w, values_by_date[t], width=w, label=t.strftime("%Y-%m"))
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Ticker count (IBB only)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "universe_funnel.png")
    plt.close(fig)


def _coverage_over_time():
    cfg = load_config()
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns_cleaned.csv", parse_dates=["date"])
    factor = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])

    returns_count = returns.groupby("date")["ticker"].nunique()
    scored_count = scores[scores["pipeline_score_uniform"] > 0].groupby("date")["ticker"].nunique()

    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.plot(returns_count.index, returns_count.values, label="Tickers with returns", color="C0")
    ax.plot(scored_count.index, scored_count.values, label="Tickers scored > 0 (uniform)", color="C1")
    ax.plot(factor["date"], factor["n_long_uniform"], label="In long portfolio", color="C2")
    ax.plot(factor["date"], factor["n_short_uniform"], label="In short portfolio", color="C3")
    ax.set_xlabel("Date")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "coverage_over_time.png")
    plt.close(fig)


if __name__ == "__main__":
    _cumulative_pr()
    _pipelinescore_distribution()
    _rolling_beta("IBB")
    _rolling_beta("XBI")
    _quintile_returns()
    _long_short_decomposition()
    _score_concentration()
    _universe_funnel()
    _coverage_over_time()
    print("figures written to", FIG)
