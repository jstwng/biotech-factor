"""Generate an initial aliases/company_aliases.json by expanding the names in
the ETF constituent CSVs with common legal-suffix / token variations.

Manual enrichment (subsidiaries from 10-K Exhibit 21) is layered on top of
this seed and should NOT be overwritten: if the target file already has
entries, we merge -- never deleting existing aliases.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from common import ALIASES_PATH, DATA_RAW, get_logger

log = get_logger("build_aliases")

CONST_DIR = DATA_RAW / "constituents"

SUFFIXES = [
    "inc.", "inc", "corp.", "corp", "corporation", "ltd.", "ltd",
    "incorporated", "plc", "co.", "llc", "n.v.", "nv", "s.a.", "sa",
    "holdings", "group",
]

TRIM_TOKENS = [
    "therapeutics", "pharmaceuticals", "pharmaceutical", "pharma",
    "biosciences", "biotechnology", "biotech", "sciences", "medicines",
]


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def _variations(canonical: str) -> list[str]:
    base = _clean(canonical)
    variants: set[str] = {base, base.lower(), base.upper(), base.title()}

    lowered = base.lower()
    for suf in SUFFIXES:
        pattern = r"\b" + re.escape(suf) + r"\.?$"
        stripped = re.sub(pattern, "", lowered).strip(" ,.")
        if stripped and stripped != lowered:
            variants.update({stripped, stripped.title()})

    # Drop each trim token once (e.g. "Vertex Pharmaceuticals" -> "Vertex")
    tokens = re.split(r"\s+", lowered)
    for tok in TRIM_TOKENS:
        if tok in tokens:
            short = " ".join(t for t in tokens if t != tok).strip(" ,.")
            if short:
                variants.update({short, short.title()})

    # Always include punctuation-free variant
    no_punct = re.sub(r"[.,]", "", base).strip()
    variants.add(no_punct)

    variants.discard("")
    return sorted(variants)


def main() -> None:
    existing: dict = {}
    if ALIASES_PATH.exists():
        try:
            existing = json.loads(ALIASES_PATH.read_text() or "{}")
        except json.JSONDecodeError:
            log.warning("existing aliases file invalid JSON; starting fresh")

    seen: dict[str, str] = {}  # ticker -> canonical
    for path in CONST_DIR.glob("*_constituents.csv"):
        df = pd.read_csv(path)
        if not {"ticker", "company_name"}.issubset(df.columns):
            log.warning("skip %s (missing columns)", path)
            continue
        for _, row in df.iterrows():
            ticker = str(row["ticker"]).strip()
            name = str(row["company_name"]).strip()
            if ticker and name and ticker not in seen:
                seen[ticker] = name

    merged = dict(existing)
    for ticker, canonical in seen.items():
        auto = _variations(canonical)
        if ticker in merged:
            manual = merged[ticker].get("aliases", [])
            combined = sorted(set(manual) | set(auto))
            merged[ticker]["aliases"] = combined
            merged[ticker].setdefault("canonical_name", canonical)
        else:
            merged[ticker] = {"canonical_name": canonical, "aliases": auto}

    ALIASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALIASES_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    log.info("wrote %d companies to %s", len(merged), ALIASES_PATH)


if __name__ == "__main__":
    main()
