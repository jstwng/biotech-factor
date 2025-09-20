"""Match ClinicalTrials.gov sponsor names to ETF constituent tickers.

Two-pass flow:
  pass 1 (default): auto-match via exact alias hit or fuzzy >= auto threshold;
                    borderline scores go to manual_review_queue.csv.
  pass 2 (--incorporate-manual): read confirmed_ticker column from the
                    (human-edited) queue and write final matched_trials.parquet.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from common import ALIASES_PATH, DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, get_logger, load_config

log = get_logger("entity_resolution")

TRIALS_DIR = DATA_RAW / "trials"
QUEUE_PATH = DATA_PROCESSED / "manual_review_queue.csv"
OUTPUT_PATH = DATA_PROCESSED / "matched_trials.parquet"


GENERIC_TOKENS = {
    "inc", "corp", "corporation", "ltd", "incorporated", "plc", "co", "llc",
    "nv", "sa", "holdings", "group",
    "pharmaceuticals", "pharmaceutical", "pharma", "therapeutics",
    "biosciences", "sciences", "bio", "biotechnology", "biotech",
    "medicines", "life", "the", "and", "&",
}


def _normalize(name: str) -> str:
    s = str(name).lower().strip()
    s = re.sub(r"[.,]", "", s)
    s = re.sub(
        r"\b(inc|corp|corporation|ltd|incorporated|plc|co|llc|nv|sa|holdings|group)\b\.?",
        "",
        s,
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _informative_tokens(text: str, min_len: int) -> set[str]:
    """Tokens of length >= min_len that are not in GENERIC_TOKENS."""
    toks = re.split(r"[^a-z0-9]+", text.lower())
    return {t for t in toks if len(t) >= min_len and t not in GENERIC_TOKENS}


def _is_excluded(normalized_sponsor: str, exclusions: list[str]) -> bool:
    return any(pat in normalized_sponsor for pat in exclusions)


def _load_trials() -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(TRIALS_DIR.glob("*.json")):
        payload = json.loads(path.read_text())
        for s in payload.get("studies", []):
            ps = s.get("protocolSection", {})
            ident = ps.get("identificationModule", {})
            status = ps.get("statusModule", {})
            sponsor = ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name")
            design = ps.get("designModule", {})
            cond = ps.get("conditionsModule", {}).get("conditions", [])
            rows.append({
                "nct_id": ident.get("nctId"),
                "sponsor_name": sponsor,
                "phase": ",".join(design.get("phases", []) or []),
                "conditions": "|".join(cond) if cond else "",
                "overall_status": status.get("overallStatus"),
                "start_date": status.get("startDateStruct", {}).get("date"),
                "primary_completion_date": status.get("primaryCompletionDateStruct", {}).get("date"),
                "status_verified_date": status.get("statusVerifiedDate"),
            })
    df = pd.DataFrame(rows).drop_duplicates("nct_id")
    return df


def _build_alias_index(aliases: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Return (normalized_alias -> ticker, normalized_alias -> original_alias)."""
    norm_to_ticker: dict[str, str] = {}
    norm_to_orig: dict[str, str] = {}
    for ticker, spec in aliases.items():
        for name in [spec.get("canonical_name", ""), *spec.get("aliases", [])]:
            if not name:
                continue
            norm = _normalize(name)
            if norm and norm not in norm_to_ticker:
                norm_to_ticker[norm] = ticker
                norm_to_orig[norm] = name
    return norm_to_ticker, norm_to_orig


def _match(
    trials: pd.DataFrame,
    norm_to_ticker: dict[str, str],
    norm_to_orig: dict[str, str],
    auto_threshold: float,
    review_lo: float,
    exclusions: list[str],
    min_shared_token_chars: int,
) -> pd.DataFrame:
    choices = list(norm_to_ticker.keys())
    out = []
    for _, row in trials.iterrows():
        sponsor = row["sponsor_name"]
        if not sponsor:
            out.append({**row.to_dict(), "ticker": None, "match_type": "unmatched", "match_score": 0.0, "matched_alias": None})
            continue
        norm = _normalize(sponsor)
        if _is_excluded(norm, exclusions):
            out.append({**row.to_dict(), "ticker": None, "match_type": "excluded", "match_score": 0.0, "matched_alias": None})
            continue
        if norm in norm_to_ticker:
            out.append({**row.to_dict(), "ticker": norm_to_ticker[norm], "match_type": "exact", "match_score": 100.0, "matched_alias": norm_to_orig[norm]})
            continue
        best = process.extractOne(norm, choices, scorer=fuzz.token_sort_ratio)
        if best is None:
            out.append({**row.to_dict(), "ticker": None, "match_type": "unmatched", "match_score": 0.0, "matched_alias": None})
            continue
        match_norm, score, _ = best
        # Secondary validation: even at score >= auto_threshold, require
        # at least one shared informative (non-generic) token between the
        # sponsor and the matched alias. Otherwise the match is junk.
        sponsor_toks = _informative_tokens(norm, min_shared_token_chars)
        alias_toks = _informative_tokens(match_norm, min_shared_token_chars)
        shared = sponsor_toks & alias_toks
        if score >= auto_threshold and shared:
            mt = "auto_fuzzy"
            ticker = norm_to_ticker[match_norm]
        elif score >= review_lo and shared:
            mt = "manual_review"
            ticker = norm_to_ticker[match_norm]
        else:
            mt = "unmatched"
            ticker = None
        out.append({**row.to_dict(), "ticker": ticker, "match_type": mt, "match_score": float(score), "matched_alias": norm_to_orig.get(match_norm)})
    return pd.DataFrame(out)


def _write_queue(df: pd.DataFrame) -> None:
    q = df[df["match_type"] == "manual_review"][[
        "nct_id", "sponsor_name", "ticker", "matched_alias", "match_score",
    ]].rename(columns={"ticker": "best_match_ticker", "matched_alias": "best_match_alias"})
    q["confirmed_ticker"] = ""
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    q.to_csv(QUEUE_PATH, index=False)
    log.info("wrote manual review queue: %d rows -> %s", len(q), QUEUE_PATH)


def _incorporate_manual(df: pd.DataFrame) -> pd.DataFrame:
    if not QUEUE_PATH.exists():
        log.warning("no queue file at %s; skipping", QUEUE_PATH)
        return df
    q = pd.read_csv(QUEUE_PATH)
    confirmed = q.dropna(subset=["confirmed_ticker"])
    confirmed = confirmed[confirmed["confirmed_ticker"].astype(str).str.strip() != ""]
    mapping = dict(zip(confirmed["nct_id"], confirmed["confirmed_ticker"]))
    df = df.copy()
    hit = df["nct_id"].isin(mapping)
    df.loc[hit, "ticker"] = df.loc[hit, "nct_id"].map(mapping)
    df.loc[hit, "match_type"] = "manual_confirmed"
    # Any manual_review rows not confirmed -> treat as unmatched
    unresolved = (df["match_type"] == "manual_review") & (~hit)
    df.loc[unresolved, "ticker"] = None
    df.loc[unresolved, "match_type"] = "unmatched"
    log.info("incorporated %d manual confirmations", int(hit.sum()))
    return df


def _report(df: pd.DataFrame, aliases: dict) -> dict:
    total = len(df)
    by_type = df["match_type"].value_counts().to_dict()
    matched = df[df["ticker"].notna()]
    coverage = matched["ticker"].nunique() / max(len(aliases), 1)
    return {
        "total_trials": int(total),
        "matched_by_type": {k: int(v) for k, v in by_type.items()},
        "match_rate": float(len(matched) / total) if total else 0.0,
        "unique_tickers_matched": int(matched["ticker"].nunique()),
        "alias_coverage": float(coverage),
        "score_quantiles": {
            str(q): float(df["match_score"].quantile(q)) for q in [0.25, 0.5, 0.75, 0.9]
        },
    }


def main(incorporate_manual: bool) -> None:
    cfg = load_config()
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    aliases = json.loads(ALIASES_PATH.read_text() or "{}")
    if not aliases:
        log.error("aliases/company_aliases.json is empty. Run build_initial_aliases.py first.")
        return

    trials = _load_trials()
    log.info("loaded %d unique trials", len(trials))
    norm_to_ticker, norm_to_orig = _build_alias_index(aliases)

    er = cfg["entity_resolution"]
    exclusions = [_normalize(x) for x in er.get("sponsor_exclusions", [])]
    df = _match(
        trials,
        norm_to_ticker,
        norm_to_orig,
        auto_threshold=er["auto_accept_threshold"],
        review_lo=er["fuzzy_match_threshold"],
        exclusions=exclusions,
        min_shared_token_chars=er.get("min_shared_token_chars", 4),
    )

    if incorporate_manual:
        df = _incorporate_manual(df)
    else:
        _write_queue(df)

    df.to_parquet(OUTPUT_PATH, index=False)
    log.info("wrote matched_trials: %d rows -> %s", len(df), OUTPUT_PATH)

    report = _report(df, aliases)
    (OUTPUT_DIR / "entity_resolution_report.json").write_text(json.dumps(report, indent=2))
    log.info("report: %s", report)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--incorporate-manual", action="store_true")
    args = p.parse_args()
    main(args.incorporate_manual)
