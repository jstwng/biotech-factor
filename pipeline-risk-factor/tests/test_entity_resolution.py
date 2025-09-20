import importlib.util
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parent.parent / "src"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SRC / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


er = _load("entity_resolution", "05_entity_resolution.py")


def test_normalize_strips_suffixes():
    assert er._normalize("Gilead Sciences, Inc.") == "gilead sciences"
    assert er._normalize("Vertex Pharmaceuticals Incorporated") == "vertex pharmaceuticals"


def test_build_alias_index_dedupes():
    aliases = {
        "GILD": {"canonical_name": "Gilead Sciences Inc", "aliases": ["Gilead Sciences", "Gilead"]},
        "VRTX": {"canonical_name": "Vertex Pharmaceuticals", "aliases": ["Vertex"]},
    }
    n2t, n2o = er._build_alias_index(aliases)
    assert n2t["gilead sciences"] == "GILD"
    assert n2t["vertex pharmaceuticals"] == "VRTX"


def test_match_exact_and_fuzzy():
    aliases = {"GILD": {"canonical_name": "Gilead Sciences Inc", "aliases": ["Gilead Sciences"]}}
    n2t, n2o = er._build_alias_index(aliases)
    trials = pd.DataFrame([
        {"nct_id": "NCT1", "sponsor_name": "Gilead Sciences Inc.", "phase": "PHASE2", "conditions": "HIV", "overall_status": "COMPLETED", "start_date": "2020-01-01", "primary_completion_date": "2021-01-01", "status_verified_date": "2021-02-01"},
        {"nct_id": "NCT2", "sponsor_name": "Gilead Sciences USA", "phase": "PHASE1", "conditions": "", "overall_status": "RECRUITING", "start_date": "2022-01-01", "primary_completion_date": None, "status_verified_date": None},
        {"nct_id": "NCT3", "sponsor_name": "Totally Unrelated Corp", "phase": "PHASE1", "conditions": "", "overall_status": "RECRUITING", "start_date": "2022-01-01", "primary_completion_date": None, "status_verified_date": None},
    ])
    out = er._match(trials, n2t, n2o, auto_threshold=95, review_lo=85, exclusions=[], min_shared_token_chars=4)
    types = dict(zip(out["nct_id"], out["match_type"]))
    assert types["NCT1"] == "exact"
    assert types["NCT2"] in {"auto_fuzzy", "manual_review"}
    assert types["NCT3"] == "unmatched"


def test_exclusion_filter():
    aliases = {"GILD": {"canonical_name": "Gilead Sciences Inc", "aliases": []}}
    n2t, n2o = er._build_alias_index(aliases)
    trials = pd.DataFrame([
        {"nct_id": "NCT4", "sponsor_name": "Novartis Pharmaceuticals", "phase": "PHASE2", "conditions": "", "overall_status": "COMPLETED", "start_date": "2020-01-01", "primary_completion_date": None, "status_verified_date": None},
    ])
    out = er._match(trials, n2t, n2o, auto_threshold=95, review_lo=95, exclusions=["novartis"], min_shared_token_chars=4)
    assert out.iloc[0]["match_type"] == "excluded"


def test_token_check_blocks_false_positive():
    # "ARS Pharmaceuticals" vs "Novartis Pharmaceuticals" -- token_sort_ratio
    # is high but share no informative token ("pharmaceuticals" is generic).
    aliases = {"SPRY": {"canonical_name": "ARS Pharmaceuticals Inc", "aliases": ["ARS Pharmaceuticals"]}}
    n2t, n2o = er._build_alias_index(aliases)
    trials = pd.DataFrame([
        {"nct_id": "NCT5", "sponsor_name": "Novartis Pharmaceuticals", "phase": "PHASE2", "conditions": "", "overall_status": "COMPLETED", "start_date": "2020-01-01", "primary_completion_date": None, "status_verified_date": None},
    ])
    out = er._match(trials, n2t, n2o, auto_threshold=95, review_lo=95, exclusions=[], min_shared_token_chars=4)
    assert out.iloc[0]["match_type"] == "unmatched"
