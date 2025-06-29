"""Download interventional clinical trials from ClinicalTrials.gov for each
ETF constituent company. Idempotent: re-running skips already-cached companies.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import requests

from common import ALIASES_PATH, DATA_RAW, get_logger, load_config

log = get_logger("ingest_trials")

TRIALS_DIR = DATA_RAW / "trials"

STATUS_FILTER = ",".join([
    "ACTIVE_NOT_RECRUITING",
    "COMPLETED",
    "RECRUITING",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
    "TERMINATED",
    "WITHDRAWN",
    "SUSPENDED",
])


def _today_tag() -> str:
    return date.today().isoformat()


def query_sponsor(
    base_url: str,
    sponsor: str,
    fields: list[str],
    delay: float,
    study_type: str,
) -> list[dict]:
    """Page through /studies for a sponsor. Returns list of raw study dicts."""
    out: list[dict] = []
    page_token: str | None = None
    while True:
        params = {
            "query.spons": sponsor,
            "filter.overallStatus": STATUS_FILTER,
            "filter.studyType": study_type,
            "fields": ",".join(fields),
            "pageSize": 1000,
            "format": "json",
        }
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(base_url, params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        out.extend(payload.get("studies", []))
        page_token = payload.get("nextPageToken")
        time.sleep(delay)
        if not page_token:
            break
    return out


def main() -> None:
    cfg = load_config()
    TRIALS_DIR.mkdir(parents=True, exist_ok=True)

    with open(ALIASES_PATH) as f:
        aliases = json.load(f)

    total_calls = 0
    total_trials = 0
    for ticker, spec in aliases.items():
        # Idempotent skip: any file for this ticker -> assume already downloaded
        existing = list(TRIALS_DIR.glob(f"{ticker}_*.json"))
        if existing:
            log.info("skip %s (cached: %s)", ticker, existing[0].name)
            continue

        names = [spec["canonical_name"], *spec.get("aliases", [])]
        seen_nct: set[str] = set()
        studies: list[dict] = []
        for name in names:
            try:
                batch = query_sponsor(
                    cfg["ct_api_base"],
                    name,
                    cfg["ct_fields"],
                    cfg["ct_api_delay_seconds"],
                    cfg["ct_study_type"],
                )
            except requests.HTTPError as e:
                log.warning("HTTP error for %s (%s): %s", ticker, name, e)
                continue
            total_calls += 1
            for s in batch:
                nct = (
                    s.get("protocolSection", {})
                    .get("identificationModule", {})
                    .get("nctId")
                )
                if nct and nct not in seen_nct:
                    seen_nct.add(nct)
                    studies.append(s)

        out_path = TRIALS_DIR / f"{ticker}_{_today_tag()}.json"
        with open(out_path, "w") as f:
            json.dump({"ticker": ticker, "aliases_queried": names, "studies": studies}, f)
        log.info("%s: %d unique trials, %d aliases queried", ticker, len(studies), len(names))
        total_trials += len(studies)

    log.info("done. total API calls: %d, total trials: %d", total_calls, total_trials)


if __name__ == "__main__":
    main()
