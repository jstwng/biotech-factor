"""Phase 5b figures. 300 DPI, no titles, publication quality."""
from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import DATA_PROCESSED, OUTPUT_DIR

OUT = OUTPUT_DIR / "backtest_flipped"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.labelsize": 11})
POST = pd.Timestamp("2020-01-01")


def _shade_post(ax, dates):
    if (dates >= POST).any():
        ax.axvspan(POST, dates.max(), alpha=0.08, color="gray")


def _cum(monthly: pd.Series) -> pd.Series:
    return (1 + monthly.fillna(0)).cumprod() - 1


def fig_5a():
    f = pd.read_csv(DATA_PROCESSED / "factor_returns_flipped.csv", parse_dates=["date"])
    rolling = pd.read_csv(OUT / "hedged_rolling.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.plot(f["date"], _cum(f["PR_flipped"]), label="Standalone flipped factor", color="C2")
    ax.plot(rolling["date"], _cum(rolling["hedged_return"]), label="Factor-hedged (rolling)", color="C0")
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post(ax, f["date"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative return")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "flipped_cumulative.png")
    plt.close(fig)


def fig_5b():
    t = pd.read_csv(OUT / "tilt_returns.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.plot(t["date"], _cum(t["excess"]), label="IBB alone (excess)", color="C0")
    ax.plot(t["date"], _cum(t["tilt_0.25"]), label="IBB + 25% pipeline tilt", color="C2")
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post(ax, t["date"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative excess return")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "flipped_vs_ibb.png")
    plt.close(fig)


def fig_5c():
    t = pd.read_csv(OUT / "tilt_returns.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.plot(t["date"], _cum(t["excess"]), label="IBB alone (w=0)", color="C0")
    ax.plot(t["date"], _cum(t["tilt_0.10"]), label="w = 0.10", color="C8")
    ax.plot(t["date"], _cum(t["tilt_0.25"]), label="w = 0.25", color="C2")
    ax.plot(t["date"], _cum(t["tilt_0.50"]), label="w = 0.50", color="C1")
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post(ax, t["date"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative excess return")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "tilt_comparison.png")
    plt.close(fig)


def _drawdown(monthly: pd.Series) -> pd.Series:
    eq = (1 + monthly.fillna(0)).cumprod()
    return eq / eq.cummax() - 1


def fig_5d():
    t = pd.read_csv(OUT / "tilt_returns.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.fill_between(t["date"], _drawdown(t["excess"]), 0, color="C0", alpha=0.3, label="IBB alone")
    ax.fill_between(t["date"], _drawdown(t["tilt_0.25"]), 0, color="C2", alpha=0.3, label="IBB + 25% tilt")
    ax.plot(t["date"], _drawdown(t["excess"]), color="C0", linewidth=0.7)
    ax.plot(t["date"], _drawdown(t["tilt_0.25"]), color="C2", linewidth=0.7)
    ax.axhline(0, color="k", linewidth=0.5)
    _shade_post(ax, t["date"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown from peak")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "drawdown_comparison.png")
    plt.close(fig)


def fig_5e():
    t = pd.read_csv(OUT / "tilt_returns.csv", parse_dates=["date"])
    t["year"] = t["date"].dt.year
    rows = []
    for year, g in t.groupby("year"):
        rows.append({
            "year": int(year),
            "ibb": float((1 + g["excess"]).prod() - 1),
            "flipped": float((1 + g["PR_flipped"]).prod() - 1),
            "tilt25": float((1 + g["tilt_0.25"]).prod() - 1),
        })
    a = pd.DataFrame(rows).query("year >= 2016")
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    x = a["year"].values
    w = 0.27
    ax.bar(x - w, a["ibb"], width=w, label="IBB excess", color="C0")
    ax.bar(x, a["flipped"], width=w, label="Standalone flipped", color="C2")
    ax.bar(x + w, a["tilt25"], width=w, label="IBB + 25% tilt", color="C3")
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(x)
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual return")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "annual_returns.png")
    plt.close(fig)


def fig_5f():
    """Horizontal waterfall of annualised return decomposition."""
    decomp = json.loads((OUT / "return_decomposition.json").read_text())
    items = [("Alpha", decomp["alpha"]),
             ("Mkt-RF", decomp["Mkt-RF"]),
             ("SMB", decomp["SMB"]),
             ("HML", decomp["HML"]),
             ("RMW", decomp["RMW"]),
             ("CMA", decomp["CMA"]),
             ("Total", decomp["total"])]
    labels = [x[0] for x in items]
    vals = [x[1] for x in items]
    colors = ["C2" if v >= 0 else "C3" for v in vals]
    # Total bar gets a distinct outline color
    colors[-1] = "black"
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    y = np.arange(len(items))[::-1]
    bars = ax.barh(y, vals, color=colors, edgecolor="black")
    ax.axvline(0, color="k", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Annualised contribution to flipped-factor return")
    for bar, v in zip(bars, vals):
        ax.annotate(f"{v*100:+.1f}%",
                    xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    xytext=(3 if v >= 0 else -3, 0),
                    textcoords="offset points",
                    ha="left" if v >= 0 else "right",
                    va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "factor_exposure_waterfall.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_5a()
    fig_5b()
    fig_5c()
    fig_5d()
    fig_5e()
    fig_5f()
    print(f"figures written to {OUT}")
