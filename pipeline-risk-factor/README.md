# Pipeline Risk Factor for Biotech Equities

Monthly "pipeline risk" factor constructed from ClinicalTrials.gov, tested as an augmentation of the Fama-French five-factor model on IBB and XBI.

## Reproduction

```bash
pip install -r requirements.txt

# Build initial alias dictionary (auto variations)
python src/build_initial_aliases.py

# Manually enrich aliases/company_aliases.json for the top 50 companies
# by adding subsidiaries from each firm's most recent 10-K Exhibit 21.

# Ingest raw data (can run in parallel)
python src/01_ingest_trials.py
python src/02_ingest_constituents.py
python src/03_ingest_returns.py
python src/04_ingest_ff5.py

# Entity resolution (two-pass: auto, then manual-review incorporation)
python src/05_entity_resolution.py
# --> review data/processed/manual_review_queue.csv, add confirmed_ticker column
python src/05_entity_resolution.py --incorporate-manual

# Factor, regressions, diagnostics, tables
python src/06_build_factor.py
python src/07_run_regressions.py
python src/08_diagnostics.py
python src/09_generate_tables.py
```

All parameters live in `config.yaml`. Scripts never hardcode thresholds, paths, or dates.

## Manual steps

1. **Top-50 alias enrichment** — look up subsidiaries in each firm's 10-K Exhibit 21 (SEC EDGAR) and extend `aliases/company_aliases.json`.
2. **ETF holdings fallback** — if iShares/SSGA block automated CSV download, manually place the current holdings CSVs in `data/raw/constituents/`.
3. **Fuzzy-match review** — resolve entries in `data/processed/manual_review_queue.csv` by filling the `confirmed_ticker` column.

## Known limitations

Documented in `PHASE1_IMPLEMENTATION_PLAN.md`: survivorship bias, imperfect sponsor matching, heuristic therapeutic-area classification, monthly frequency, short sample, no out-of-sample test.
