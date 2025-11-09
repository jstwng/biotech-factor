"""Compute monthly PipelineScore per company and construct the long-short
pipeline-risk factor (PR) portfolio.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, get_logger, load_config

log = get_logger("build_factor")

MATCHED = DATA_PROCESSED / "matched_trials.parquet"
CONST_RETS = DATA_RAW / "returns" / "constituent_returns_cleaned.csv"
SCORES_OUT = DATA_PROCESSED / "pipeline_scores.parquet"
FACTOR_OUT = DATA_PROCESSED / "factor_returns.csv"

CLOSED_STATUSES = {"COMPLETED", "TERMINATED", "WITHDRAWN"}
OPEN_STATUSES = {
    "RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING", "SUSPENDED",
}

THERAPEUTIC_RULES: list[tuple[str, list[str]]] = [
    ("Oncology", ["cancer", "tumor", "carcinoma", "lymphoma", "leukemia", "melanoma", "sarcoma", "neoplasm"]),
    ("Infectious Disease", ["infection", "virus", "bacterial", "hiv", "hepatitis", "covid", "influenza", "pneumonia"]),
    ("Cardiovascular", ["heart", "cardiac", "cardiovascular", "hypertension", "atherosclerosis", "arrhythmia"]),
    ("CNS/Neurology", ["alzheimer", "parkinson", "multiple sclerosis", "epilepsy", "als", "neuropathy", "dementia", "schizophrenia", "depression", "anxiety", "bipolar"]),
    ("Metabolic/Endocrine", ["diabetes", "obesity", "thyroid", "metabolic", "lipid"]),
    ("Rare Disease", ["orphan", "rare disease"]),
]


def classify_area(conditions: str) -> str:
    text = (conditions or "").lower()
    for area, keywords in THERAPEUTIC_RULES:
        if any(k in text for k in keywords):
            return area
    return "Other"


def normalize_phase(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.replace("PHASE", "Phase").replace("_", " ").strip().title()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    # Map ClinicalTrials v2 tokens. Input has already been .title()'d so every
    # key below is in its title-case form. "Na" covers the literal "NA" token.
    token_map = {
        "Phase1": "Phase 1", "Phase 1": "Phase 1",
        "Phase2": "Phase 2", "Phase 2": "Phase 2",
        "Phase3": "Phase 3", "Phase 3": "Phase 3",
        "Phase4": "Phase 4", "Phase 4": "Phase 4",
        "Early Phase1": "Phase 1", "Early Phase 1": "Phase 1",
        "Na": None,
    }
    mapped = [token_map.get(p, p) for p in parts]
    mapped = [p for p in mapped if p]
    if not mapped:
        return None
    if len(mapped) == 1:
        return mapped[0]
    return "/".join(sorted(set(mapped)))


def month_ends(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="M")


def active_mask(df: pd.DataFrame, t: pd.Timestamp) -> pd.Series:
    start = pd.to_datetime(df["start_date"], errors="coerce")
    compl = pd.to_datetime(df["primary_completion_date"], errors="coerce")
    status = df["overall_status"].fillna("")

    started = start.notna() & (start <= t)
    not_finished = compl.isna() | (compl > t) | status.isin(OPEN_STATUSES)
    # A trial with a closed status is inactive even when PCD is missing: the
    # status itself carries the information. (Phase 3 audit Finding 2.5.)
    closed_with_date = status.isin(CLOSED_STATUSES) & compl.notna() & (compl <= t)
    closed_no_date = status.isin(CLOSED_STATUSES) & compl.isna()
    closed = closed_with_date | closed_no_date
    return started & not_finished & ~closed


def compute_scores(matched: pd.DataFrame, months: pd.DatetimeIndex, cfg: dict) -> pd.DataFrame:
    """Compute both uniform (no disease multiplier) and adjusted (with
    multiplier) pipeline scores per company-month. Output columns:
    date, ticker, pipeline_score_uniform, pipeline_score_adjusted,
    n_active_trials, n_phase1, n_phase2, n_phase3, n_nda.
    """
    matched = matched.dropna(subset=["ticker"]).copy()
    matched["phase_norm"] = matched["phase"].apply(normalize_phase)
    matched["area"] = matched["conditions"].apply(classify_area)

    base = cfg["success_rates"]["overall"]
    mult = cfg["success_rates"]["disease_multipliers"]
    matched["contrib_uniform"] = matched["phase_norm"].apply(lambda p: base.get(p, 0.0))
    matched["contrib_adjusted"] = matched.apply(
        lambda r: base.get(r["phase_norm"], 0.0) * mult.get(r["area"], mult["Other"]),
        axis=1,
    )

    rows: list[pd.DataFrame] = []
    for t in months:
        mask = active_mask(matched, t)
        active = matched.loc[mask, ["ticker", "phase_norm", "contrib_uniform", "contrib_adjusted"]]
        if active.empty:
            continue
        grp = active.groupby("ticker")
        agg = grp[["contrib_uniform", "contrib_adjusted"]].sum()
        agg.columns = ["pipeline_score_uniform", "pipeline_score_adjusted"]
        agg["n_active_trials"] = grp.size()
        agg["n_phase1"] = grp["phase_norm"].apply(lambda s: s.eq("Phase 1").sum())
        agg["n_phase2"] = grp["phase_norm"].apply(lambda s: s.eq("Phase 2").sum())
        agg["n_phase3"] = grp["phase_norm"].apply(lambda s: s.eq("Phase 3").sum())
        agg["n_nda"] = grp["phase_norm"].apply(lambda s: s.eq("NDA/BLA").sum())
        agg["date"] = t
        rows.append(agg.reset_index())

    cols = ["date", "ticker", "pipeline_score_uniform", "pipeline_score_adjusted",
            "n_active_trials", "n_phase1", "n_phase2", "n_phase3", "n_nda"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.concat(rows, ignore_index=True)[cols]


def _select_portfolios(
    sub: pd.DataFrame,
    score_col: str,
    q_lo: float,
    q_hi: float,
    valid_tickers: set,
    min_tickers: int = 10,
) -> tuple[list[str], list[str]]:
    """Return (longs, shorts) lists after filtering to tickers with return
    data and score > 0, then applying top/bottom quantile cutoffs."""
    s = sub[sub[score_col] > 0]
    s = s[s["ticker"].isin(valid_tickers)]
    if len(s) < min_tickers:
        return [], []
    short_cut = s[score_col].quantile(q_lo)
    long_cut = s[score_col].quantile(q_hi)
    longs = s[s[score_col] >= long_cut]["ticker"].tolist()
    shorts = s[s[score_col] <= short_cut]["ticker"].tolist()
    return longs, shorts


def build_factor(
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    cfg: dict,
    score_col: str = "pipeline_score_uniform",
    exclude_tickers: set | None = None,
    min_months_history: int | None = None,
    score_cap_quantile: float | None = None,
) -> pd.DataFrame:
    """Build the long-short factor for one score specification.

    score_col: which pipeline-score column to rank on.
    exclude_tickers: tickers to drop from ranking and portfolios entirely.
    min_months_history: require each ticker to have this many months of return
        data (cumulative through t+1) before it can enter a portfolio.
    score_cap_quantile: if set (e.g. 0.95), cap each month's scores at that
        percentile before ranking.
    """
    q_lo = cfg["factor"]["quintile_short"]
    q_hi = cfg["factor"]["quintile_long"]
    lag = cfg["factor"]["return_lag"]
    exclude_tickers = exclude_tickers or set()

    returns = returns.copy()
    returns["date"] = pd.to_datetime(returns["date"])
    returns = returns[~returns["ticker"].isin(exclude_tickers)]
    ret_pivot = returns.pivot(index="date", columns="ticker", values="return").sort_index()
    valid_tickers = set(ret_pivot.columns)

    # Precompute per-ticker cumulative month count through each date
    months_history: dict[tuple[pd.Timestamp, str], int] = {}
    if min_months_history is not None:
        counts = returns.sort_values("date").groupby("ticker")["date"].rank(method="first").astype(int)
        rh = returns.assign(_n=counts)[["date", "ticker", "_n"]]
        for _, row in rh.iterrows():
            months_history[(row["date"], row["ticker"])] = int(row["_n"])

    scores = scores[~scores["ticker"].isin(exclude_tickers)]
    months = sorted(scores["date"].unique())
    rows: list[dict] = []
    for t in months:
        sub = scores[scores["date"] == t].copy()
        if score_cap_quantile is not None:
            cap = sub[sub[score_col] > 0][score_col].quantile(score_cap_quantile)
            sub[score_col] = sub[score_col].clip(upper=cap)
        longs, shorts = _select_portfolios(sub, score_col, q_lo, q_hi, valid_tickers)

        t_next = pd.Timestamp(t) + pd.offsets.MonthEnd(lag)
        if t_next not in ret_pivot.index:
            continue

        if min_months_history is not None:
            longs = [c for c in longs if months_history.get((t_next, c), 0) >= min_months_history]
            shorts = [c for c in shorts if months_history.get((t_next, c), 0) >= min_months_history]

        long_ret = ret_pivot.loc[t_next, [c for c in longs if c in ret_pivot.columns]].dropna()
        short_ret = ret_pivot.loc[t_next, [c for c in shorts if c in ret_pivot.columns]].dropna()
        if long_ret.empty or short_ret.empty:
            continue
        rows.append({
            "date": t_next,
            "PR": float(long_ret.mean() - short_ret.mean()),
            "n_long": int(len(long_ret)),
            "n_short": int(len(short_ret)),
            "long_return": float(long_ret.mean()),
            "short_return": float(short_ret.mean()),
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def summary_stats(factor: pd.DataFrame, pr_col: str = "PR") -> dict:
    pr = factor[pr_col]
    ac = lambda k: float(pr.autocorr(lag=k)) if len(pr) > k else None
    return {
        "n": int(len(pr)),
        "mean": float(pr.mean()),
        "std": float(pr.std()),
        "skew": float(pr.skew()),
        "kurtosis": float(pr.kurt()),
        "min": float(pr.min()),
        "max": float(pr.max()),
        "ac_1": ac(1),
        "ac_3": ac(3),
        "ac_6": ac(6),
        "sharpe_annualized": float((pr.mean() / pr.std()) * np.sqrt(12)) if pr.std() > 0 else None,
    }


def main() -> None:
    cfg = load_config()
    matched = pd.read_parquet(MATCHED)
    returns = pd.read_csv(CONST_RETS)
    months = month_ends(cfg["start_date"], cfg["end_date"])

    scores = compute_scores(matched, months, cfg)
    scores.to_parquet(SCORES_OUT, index=False)
    log.info("pipeline_scores: %d rows, %d tickers", len(scores), scores["ticker"].nunique())

    factor_u = build_factor(scores, returns, cfg, score_col="pipeline_score_uniform")
    factor_a = build_factor(scores, returns, cfg, score_col="pipeline_score_adjusted")

    # Align on date and produce the wide dual-factor CSV
    fu = factor_u.rename(columns={"PR": "PR_uniform", "n_long": "n_long_uniform", "n_short": "n_short_uniform", "long_return": "long_return_uniform", "short_return": "short_return_uniform"})
    fa = factor_a.rename(columns={"PR": "PR_adjusted", "n_long": "n_long_adjusted", "n_short": "n_short_adjusted", "long_return": "long_return_adjusted", "short_return": "short_return_adjusted"})
    out = fu.merge(fa, on="date", how="outer").sort_values("date").reset_index(drop=True)
    out.to_csv(FACTOR_OUT, index=False)
    log.info("factor_returns: %d rows; uniform std=%.5f, adjusted std=%.5f",
             len(out), out["PR_uniform"].std(), out["PR_adjusted"].std())
    log.info("avg n_long/short uniform:  %.1f / %.1f", out["n_long_uniform"].mean(), out["n_short_uniform"].mean())
    log.info("avg n_long/short adjusted: %.1f / %.1f", out["n_long_adjusted"].mean(), out["n_short_adjusted"].mean())

    stats = {
        "uniform": summary_stats(fu, "PR_uniform") | {"avg_n_long": float(fu["n_long_uniform"].mean()), "avg_n_short": float(fu["n_short_uniform"].mean())},
        "adjusted": summary_stats(fa, "PR_adjusted") | {"avg_n_long": float(fa["n_long_adjusted"].mean()), "avg_n_short": float(fa["n_short_adjusted"].mean())},
    }
    (OUTPUT_DIR / "factor_summary_stats.json").write_text(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
