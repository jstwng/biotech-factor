"""Phase 5 figures (300 DPI, no titles, clean labels)."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from common import OUTPUT_DIR

FIG = OUTPUT_DIR / "backtest"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.labelsize": 11})

POST = pd.Timestamp("2020-01-01")


def _shade_post_2020(ax, dates):
    """Light gray vertical shading from 2020-01-01 to end of x-range."""
    if (dates >= POST).any():
        ax.axvspan(POST, dates.max(), alpha=0.08, color="gray")


def fig_attribution():
    """4a. Cumulative IBB excess return decomposed into FF5/PR/alpha/residual.
    Uses additive cumulation so the four series visually sum to the total."""
    cum = pd.read_csv(FIG / "attribution_cumulative.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.plot(cum["date"], cum["sumcum_ibb_excess"], color="black", linewidth=1.6, label="IBB excess (sum-cum)")
    ax.plot(cum["date"], cum["sumcum_ff5_explained"], color="C0", label="FF5-explained")
    ax.plot(cum["date"], cum["sumcum_pr_attr"], color="C2", label="PR-attributable")
    ax.plot(cum["date"], cum["sumcum_alpha"], color="C1", label="Alpha")
    ax.plot(cum["date"], cum["sumcum_residual"], color="C3", label="Residual")
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post_2020(ax, cum["date"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative monthly contribution (sum)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "cumulative_attribution.png")
    plt.close(fig)


def fig_strategy_cumulative():
    """4b. Static-hedge vs rolling-hedge cumulative return, multiplicative."""
    s = pd.read_csv(FIG / "strategy_static.csv", parse_dates=["date"])
    r = pd.read_csv(FIG / "strategy_rolling.csv", parse_dates=["date"])
    s_cum = (1 + s["strategy_return"].fillna(0)).cumprod() - 1
    r_cum = (1 + r["strategy_return"].fillna(0)).cumprod() - 1
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.plot(s["date"], s_cum, label="Static-hedge (full-sample betas, look-ahead)", color="C0")
    ax.plot(r["date"], r_cum, label="Rolling-hedge (out-of-sample 36mo betas)", color="C1")
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post_2020(ax, s["date"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative beta-neutral strategy return")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG / "strategy_cumulative_return.png")
    plt.close(fig)


def fig_rolling_beta():
    """4c. Rolling 36-month beta_PR with 95% CI band."""
    rb = pd.read_csv(FIG / "rolling_beta_pr_with_se.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.plot(rb["date"], rb["beta_PR"], color="C0")
    ax.fill_between(
        rb["date"],
        rb["beta_PR"] - 1.96 * rb["se_PR"],
        rb["beta_PR"] + 1.96 * rb["se_PR"],
        alpha=0.2,
        color="C0",
    )
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post_2020(ax, rb["date"])
    ax.set_xlabel("Window end date")
    ax.set_ylabel(r"$\beta_{PR}$ (36-month rolling)")
    fig.tight_layout()
    fig.savefig(FIG / "rolling_beta_pr_with_ci.png")
    plt.close(fig)


def fig_annual_bars():
    """4d. Annual returns: IBB excess, FF5-explained, beta-neutral (rolling)."""
    a = pd.read_csv(FIG / "annual_returns.csv")
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    x = a["year"].astype(int).values
    w = 0.27
    ax.bar(x - w, a["ibb_excess"], width=w, label="IBB excess", color="C0")
    ax.bar(x, a["ff5_explained"], width=w, label="FF5-explained", color="C2")
    ax.bar(x + w, a["strategy_rolling"].fillna(0), width=w, label="Beta-neutral (rolling)", color="C3")
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(x)
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual return")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "annual_returns_bar.png")
    plt.close(fig)


def fig_drawdown():
    """4e. Drawdown of the rolling-hedge beta-neutral strategy."""
    r = pd.read_csv(FIG / "strategy_rolling.csv", parse_dates=["date"])
    s = r["strategy_return"].fillna(0)
    eq = (1 + s).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    fig, ax = plt.subplots(figsize=(10, 4), dpi=300)
    ax.fill_between(r["date"], dd, 0, color="C3", alpha=0.4)
    ax.plot(r["date"], dd, color="C3")
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post_2020(ax, r["date"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown from peak")
    fig.tight_layout()
    fig.savefig(FIG / "drawdown.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_attribution()
    fig_strategy_cumulative()
    fig_rolling_beta()
    fig_annual_bars()
    fig_drawdown()
    print(f"figures written to {FIG}")
