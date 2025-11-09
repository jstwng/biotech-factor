"""Phase 4 robustness: NW lag sensitivity (1/3/6/12) and subsample stability
(pre/post 2020) for the uniform-spec IBB regression. Two factor variants:
  - baseline: existing factor_returns.csv, PR_uniform column
  - exclusion_top3: rebuild in-memory dropping GILD/ABBV/AMGN

Does not touch factor construction code, raw data, or any Phase 3 output.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, load_config

ROB = OUTPUT_DIR / "robustness"
FF5_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
LAGS = [1, 3, 6, 12]
EXCLUDE_TOP3 = {"GILD", "ABBV", "AMGN"}


def _load_bf():
    spec = importlib.util.spec_from_file_location("bf", Path(__file__).parent / "06_build_factor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _ibb_df(pr: pd.DataFrame, pr_col: str) -> pd.DataFrame:
    """Inner-join IBB excess returns with FF5 and the chosen PR column."""
    etf = pd.read_csv(DATA_RAW / "returns" / "etf_returns.csv", parse_dates=["date"])
    ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
    df = etf[["date", "IBB_return"]].rename(columns={"IBB_return": "ret"})
    df = df.merge(ff5, on="date").merge(pr[["date", pr_col]].rename(columns={pr_col: "PR"}), on="date")
    df["excess"] = df["ret"] - df["RF"]
    return df.dropna().reset_index(drop=True)


def _fit(df: pd.DataFrame, nw_lag: int):
    return sm.OLS(df["excess"], sm.add_constant(df[FF5_FACTORS + ["PR"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": nw_lag}
    )


def _coef_block(m) -> dict:
    return {
        "beta": float(m.params["PR"]),
        "se": float(m.bse["PR"]),
        "t_stat": float(m.tvalues["PR"]),
        "p_value": float(m.pvalues["PR"]),
    }


def _ci(m, z: float = 1.96) -> tuple[float, float]:
    b = float(m.params["PR"])
    se = float(m.bse["PR"])
    return (b - z * se, b + z * se)


def build_exclusion_factor(cfg: dict) -> pd.DataFrame:
    """Rebuild the uniform-spec factor with GILD/ABBV/AMGN excluded. Returns
    a DataFrame with columns [date, PR_uniform]."""
    bf = _load_bf()
    scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
    returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns_cleaned.csv", parse_dates=["date"])
    f = bf.build_factor(scores, returns, cfg, score_col="pipeline_score_uniform", exclude_tickers=EXCLUDE_TOP3)
    return f[["date", "PR"]].rename(columns={"PR": "PR_uniform"})


def main() -> None:
    ROB.mkdir(parents=True, exist_ok=True)
    cfg = load_config()

    # Load baseline factor
    pr_baseline = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])[["date", "PR_uniform"]]
    pr_exclusion = build_exclusion_factor(cfg)

    variants = {
        "baseline_uniform_IBB": pr_baseline,
        "exclusion_top3_uniform_IBB": pr_exclusion,
    }

    # ---- Task 1: NW lag sensitivity ----
    lag_json: dict = {}
    for name, pr in variants.items():
        df = _ibb_df(pr, "PR_uniform")
        lag_json[name] = {}
        for L in LAGS:
            m = _fit(df, L)
            lag_json[name][f"lag_{L}"] = _coef_block(m)
    (ROB / "nw_lag_sensitivity.json").write_text(json.dumps(lag_json, indent=2))

    md_lines = [
        "## Newey-West Lag Sensitivity: PR_uniform on IBB",
        "",
        "| Variant | Lag | PR beta | NW t-stat | p-value |",
        "|---|---|---|---|---|",
    ]
    for name, label in [("baseline_uniform_IBB", "Baseline"), ("exclusion_top3_uniform_IBB", "Excl. top 3")]:
        for L in LAGS:
            c = lag_json[name][f"lag_{L}"]
            md_lines.append(f"| {label} | {L} | {c['beta']:+.4f} | {c['t_stat']:.2f} | {c['p_value']:.4f} |")
    md_lines.append("")

    # Task 1d: flag any lag where t-stat drops below 1.96
    flags = []
    for name, label in [("baseline_uniform_IBB", "baseline"), ("exclusion_top3_uniform_IBB", "excl-top3")]:
        for L in LAGS:
            t = lag_json[name][f"lag_{L}"]["t_stat"]
            if abs(t) < 1.96:
                flags.append(f"{label} lag {L} t={t:.2f}")
    md_lines.append("**Flags (|t| < 1.96):** " + (", ".join(flags) if flags else "none -- t-statistic stable across all four lags for both variants."))
    md_lines.append("")
    (ROB / "nw_lag_sensitivity.md").write_text("\n".join(md_lines) + "\n")

    # ---- Task 2: Subsample stability ----
    nw_lag = cfg["stats"]["newey_west_lag"]
    cuts = {
        "pre_2020": ("2015-01-01", "2019-12-31"),
        "post_2020": ("2020-01-01", "2024-12-31"),
        "full_sample": (cfg["start_date"], cfg["end_date"]),
    }

    sub_json: dict = {}
    for name, pr in variants.items():
        df = _ibb_df(pr, "PR_uniform")
        sub_json[name] = {}
        for period, (lo, hi) in cuts.items():
            sub = df[(df["date"] >= lo) & (df["date"] <= hi)].reset_index(drop=True)
            if len(sub) < 24:
                sub_json[name][period] = {"n": len(sub), "error": "too few obs"}
                continue
            m = _fit(sub, nw_lag)
            ci_lo, ci_hi = _ci(m)
            sub_json[name][period] = {
                "n": int(len(sub)),
                "beta": float(m.params["PR"]),
                "se": float(m.bse["PR"]),
                "t_stat": float(m.tvalues["PR"]),
                "p_value": float(m.pvalues["PR"]),
                "ci_lower": float(ci_lo),
                "ci_upper": float(ci_hi),
                "adj_r2": float(m.rsquared_adj),
            }
    (ROB / "subsample_stability.json").write_text(json.dumps(sub_json, indent=2))

    md_lines = [
        "## Subsample Stability: PR_uniform on IBB",
        "",
        "| Variant | Period | n | PR beta | NW SE | t-stat | p-value | 95% CI |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, label in [("baseline_uniform_IBB", "Baseline"), ("exclusion_top3_uniform_IBB", "Excl. top 3")]:
        for period in ["pre_2020", "post_2020", "full_sample"]:
            r = sub_json[name][period]
            md_lines.append(
                f"| {label} | {period.replace('_', ' ')} | {r['n']} | {r['beta']:+.4f} | "
                f"{r['se']:.4f} | {r['t_stat']:.2f} | {r['p_value']:.4f} | "
                f"[{r['ci_lower']:+.4f}, {r['ci_upper']:+.4f}] |"
            )
    md_lines.append("")

    # Task 2e: interpretation flags
    def _flags(name: str) -> dict:
        pre = sub_json[name]["pre_2020"]
        post = sub_json[name]["post_2020"]
        same_sign = (pre["beta"] * post["beta"]) > 0
        ratio = max(abs(pre["beta"]), abs(post["beta"])) / max(min(abs(pre["beta"]), abs(post["beta"])), 1e-12)
        ci_overlap = not (pre["ci_upper"] < post["ci_lower"] or post["ci_upper"] < pre["ci_lower"])
        return {"same_sign": same_sign, "magnitude_ratio": ratio, "ci_overlap": ci_overlap, "pre": pre, "post": post}

    md_lines.append("### Interpretation")
    for name, label in [("baseline_uniform_IBB", "Baseline"), ("exclusion_top3_uniform_IBB", "Excl. top 3")]:
        f = _flags(name)
        md_lines.append(
            f"- **{label}:** beta sign consistent across sub-periods: "
            f"{'YES' if f['same_sign'] else 'NO'}. "
            f"Magnitude ratio (larger/smaller): {f['magnitude_ratio']:.2f}x. "
            f"95% CIs overlap: {'YES' if f['ci_overlap'] else 'NO'}."
        )
    md_lines.append("")
    md_lines.append(
        "Power note: each sub-period has n≈60, half the full sample. A non-significant p-value "
        "in one sub-period does not demonstrate absence of effect; it may reflect lower power."
    )
    md_lines.append("")
    (ROB / "subsample_stability.md").write_text("\n".join(md_lines) + "\n")

    # ---- Task 3: append to robustness_summary.md ----
    existing = (ROB / "robustness_summary.md").read_text() if (ROB / "robustness_summary.md").exists() else ""
    new_sections = "\n\n" + (ROB / "nw_lag_sensitivity.md").read_text() + "\n\n" + (ROB / "subsample_stability.md").read_text()
    (ROB / "robustness_summary.md").write_text(existing + new_sections)
    print("wrote nw_lag_sensitivity.{json,md}, subsample_stability.{json,md}; appended to robustness_summary.md")

    # Stdout summary for quick sanity check
    for name in variants:
        print(f"\n{name}:")
        for L in LAGS:
            c = lag_json[name][f"lag_{L}"]
            print(f"  lag {L:>2}: beta={c['beta']:+.4f}, t={c['t_stat']:.2f}, p={c['p_value']:.4f}")
        for period in ["pre_2020", "post_2020", "full_sample"]:
            r = sub_json[name][period]
            print(f"  {period:>12}: n={r['n']}, beta={r['beta']:+.4f}, t={r['t_stat']:.2f}, p={r['p_value']:.4f}, CI=[{r['ci_lower']:+.4f}, {r['ci_upper']:+.4f}]")


if __name__ == "__main__":
    main()
