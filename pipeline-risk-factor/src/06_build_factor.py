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
CONST_RETS = DATA_RAW / "returns" / "constituent_returns.csv"
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
    raw = raw.replace("PHASE", "Phase").replace("_", " ").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    # Map ClinicalTrials v2 tokens
    token_map = {
        "Phase1": "Phase 1", "Phase 1": "Phase 1",
        "Phase2": "Phase 2", "Phase 2": "Phase 2",
        "Phase3": "Phase 3", "Phase 3": "Phase 3",
        "Phase4": "Phase 4", "Phase 4": "Phase 4",
        "NA": None, "EARLY PHASE 1": "Phase 1", "Early Phase 1": "Phase 1",
    }
    mapped = [token_map.get(p, p) for p in parts]
    mapped = [p for p in mapped if p]
    if not mapped:
        return None
    if len(mapped) == 1:
        return mapped[0]
    # e.g., Phase 1 + Phase 2 -> "Phase 1/Phase 2"
    return "/".join(sorted(set(mapped)))


def month_ends(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="M")


def active_mask(df: pd.DataFrame, t: pd.Timestamp) -> pd.Series:
    start = pd.to_datetime(df["start_date"], errors="coerce")
    compl = pd.to_datetime(df["primary_completion_date"], errors="coerce")
    status = df["overall_status"].fillna("")

    started = start.notna() & (start <= t)
    not_finished = compl.isna() | (compl > t) | status.isin(OPEN_STATUSES)
    closed = status.isin(CLOSED_STATUSES) & compl.notna() & (compl <= t)
    return started & not_finished & ~closed


def compute_scores(matched: pd.DataFrame, months: pd.DatetimeIndex, cfg: dict) -> pd.DataFrame:
    matched = matched.dropna(subset=["ticker"]).copy()
    matched["phase_norm"] = matched["phase"].apply(normalize_phase)
    matched["area"] = matched["conditions"].apply(classify_area)

    base = cfg["success_rates"]["overall"]
    mult = cfg["success_rates"]["disease_multipliers"]
    matched["contrib"] = matched.apply(
        lambda r: base.get(r["phase_norm"], 0.0) * mult.get(r["area"], mult["Other"]),
        axis=1,
    )

    rows: list[dict] = []
    for t in months:
        mask = active_mask(matched, t)
        active = matched.loc[mask, ["ticker", "phase_norm", "contrib"]]
        if active.empty:
            continue
        grp = active.groupby("ticker")
        agg = grp["contrib"].sum().rename("pipeline_score").to_frame()
        agg["n_active_trials"] = grp.size()
        agg["n_phase1"] = grp["phase_norm"].apply(lambda s: s.eq("Phase 1").sum())
        agg["n_phase2"] = grp["phase_norm"].apply(lambda s: s.eq("Phase 2").sum())
        agg["n_phase3"] = grp["phase_norm"].apply(lambda s: s.eq("Phase 3").sum())
        agg["n_nda"] = grp["phase_norm"].apply(lambda s: s.eq("NDA/BLA").sum())
        agg["date"] = t
        rows.append(agg.reset_index())

    if not rows:
        return pd.DataFrame(columns=["date", "ticker", "pipeline_score", "n_active_trials", "n_phase1", "n_phase2", "n_phase3", "n_nda"])
    return pd.concat(rows, ignore_index=True)[
        ["date", "ticker", "pipeline_score", "n_active_trials", "n_phase1", "n_phase2", "n_phase3", "n_nda"]
    ]


def build_factor(scores: pd.DataFrame, returns: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    q_lo = cfg["factor"]["quintile_short"]
    q_hi = cfg["factor"]["quintile_long"]
    lag = cfg["factor"]["return_lag"]

    returns = returns.copy()
    returns["date"] = pd.to_datetime(returns["date"])
    # Shift returns back by `lag` months to align with the score date t:
    #   score at t is paired with the return realized in t + lag.
    ret_pivot = returns.pivot(index="date", columns="ticker", values="return").sort_index()
    months = sorted(scores["date"].unique())
    rows: list[dict] = []
    for t in months:
        sub = scores[scores["date"] == t]
        sub = sub[sub["pipeline_score"] > 0]
        if len(sub) < 10:
            continue
        short_cut = sub["pipeline_score"].quantile(q_lo)   # e.g. 20th percentile
        long_cut = sub["pipeline_score"].quantile(q_hi)    # e.g. 80th percentile
        longs = sub[sub["pipeline_score"] >= long_cut]["ticker"].tolist()   # top 20%
        shorts = sub[sub["pipeline_score"] <= short_cut]["ticker"].tolist() # bottom 20%

        t_next = pd.Timestamp(t) + pd.offsets.MonthEnd(lag)
        if t_next not in ret_pivot.index:
            continue
        long_ret = ret_pivot.loc[t_next, [c for c in longs if c in ret_pivot.columns]].dropna()
        short_ret = ret_pivot.loc[t_next, [c for c in shorts if c in ret_pivot.columns]].dropna()
        if long_ret.empty or short_ret.empty:
            continue
        lr = float(long_ret.mean())
        sr = float(short_ret.mean())
        rows.append({
            "date": t_next,
            "PR": lr - sr,
            "n_long": int(len(long_ret)),
            "n_short": int(len(short_ret)),
            "long_return": lr,
            "short_return": sr,
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def summary_stats(factor: pd.DataFrame) -> dict:
    pr = factor["PR"]
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
        "avg_n_long": float(factor["n_long"].mean()),
        "avg_n_short": float(factor["n_short"].mean()),
    }


def main() -> None:
    cfg = load_config()
    matched = pd.read_parquet(MATCHED)
    returns = pd.read_csv(CONST_RETS)
    months = month_ends(cfg["start_date"], cfg["end_date"])

    scores = compute_scores(matched, months, cfg)
    scores.to_parquet(SCORES_OUT, index=False)
    log.info("pipeline_scores: %d rows, %d tickers", len(scores), scores["ticker"].nunique())

    factor = build_factor(scores, returns, cfg)
    factor.to_csv(FACTOR_OUT, index=False)
    log.info("factor_returns: %d rows (PR std=%.5f)", len(factor), factor["PR"].std())

    stats = summary_stats(factor)
    (OUTPUT_DIR / "factor_summary_stats.json").write_text(json.dumps(stats, indent=2))
    log.info("summary: %s", stats)


if __name__ == "__main__":
    main()
