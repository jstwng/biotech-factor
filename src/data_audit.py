"""Read-only data quality audit. Dumps structured findings to stdout.
No file I/O except reading existing data. Used to author DATA_AUDIT_FINDINGS.md.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from common import ALIASES_PATH, DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, load_config

pd.set_option("display.width", 180)
pd.set_option("display.max_rows", 200)
pd.set_option("display.max_columns", 30)


def banner(s: str) -> None:
    print("\n" + "=" * 80)
    print(s)
    print("=" * 80)


cfg = load_config()
matched = pd.read_parquet(DATA_PROCESSED / "matched_trials.parquet")
er_report = json.loads((OUTPUT_DIR / "entity_resolution_report.json").read_text())
aliases = json.loads(ALIASES_PATH.read_text())
ibb = pd.read_csv(DATA_RAW / "constituents" / "ibb_constituents.csv")
xbi = pd.read_csv(DATA_RAW / "constituents" / "xbi_constituents.csv")
returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns.csv", parse_dates=["date"])
etf_returns = pd.read_csv(DATA_RAW / "returns" / "etf_returns.csv", parse_dates=["date"])
ff5 = pd.read_csv(DATA_RAW / "ff5" / "ff5_monthly.csv", parse_dates=["date"])
scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
factor = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])

universe = pd.concat([ibb[["ticker", "company_name"]], xbi[["ticker", "company_name"]]]).drop_duplicates("ticker")

banner("1a. Match rate decomposition")
total = len(matched)
by_type = matched["match_type"].value_counts().to_dict()
print(f"total trials: {total}")
for k, v in by_type.items():
    print(f"  {k}: {v}  ({v/total:.2%})")
fuzzy = matched[matched["match_type"].isin(["auto_fuzzy", "manual_confirmed"])]
print(f"fuzzy/manual rows: {len(fuzzy)}")
if len(fuzzy):
    print(fuzzy[["sponsor_name", "ticker", "matched_alias", "match_score"]].drop_duplicates().sort_values("match_score").to_string(index=False))

# 30 random unmatched
rng = np.random.default_rng(42)
unm = matched[matched["match_type"] == "unmatched"]
sample = unm.sample(min(30, len(unm)), random_state=42)
print("\n30 random unmatched sponsors:")
print(sample[["nct_id", "sponsor_name"]].to_string(index=False))

excl = matched[matched["match_type"] == "excluded"]
print(f"\nexcluded total: {len(excl)}")
print("top excluded sponsor strings (pre-normalization):")
print(excl["sponsor_name"].value_counts().head(25).to_string())

banner("1b. Alias dictionary coverage")
ticker_set = set(universe["ticker"].tolist())
alias_tickers = set(aliases.keys())
print(f"total universe tickers: {len(ticker_set)}")
print(f"tickers with alias entry: {len(ticker_set & alias_tickers)}")
missing = ticker_set - alias_tickers
print(f"tickers MISSING alias entry: {len(missing)}")
print("missing:", sorted(missing))
sizes = []
for t in ticker_set & alias_tickers:
    n = len(aliases[t].get("aliases", []))
    sizes.append((t, n))
sizes_df = pd.DataFrame(sizes, columns=["ticker", "n_aliases"])
print(f"\nalias count distribution:\n{sizes_df['n_aliases'].describe()}")
print(f"tickers with 0 aliases: {(sizes_df['n_aliases']==0).sum()}")
print(f"tickers with exactly 1 alias: {(sizes_df['n_aliases']==1).sum()}")
print("tickers with <=1 alias:")
print(sizes_df[sizes_df["n_aliases"] <= 1].to_string(index=False))

banner("1c. Ticker validity")
# duplicates by capitalization/whitespace
all_tk = list(universe["ticker"].astype(str))
norm = [t.strip().upper() for t in all_tk]
dup_norm = [k for k, v in Counter(norm).items() if v > 1]
print(f"duplicate ticker (after strip/upper): {dup_norm}")

# tickers in constituents NOT in returns
returns_tickers = set(returns["ticker"].unique())
phantom = ticker_set - returns_tickers
print(f"\ntickers in universe but ABSENT from returns: {len(phantom)}")
print(sorted(phantom))

# tickers with <6 months of data
months_per_ticker = returns.groupby("ticker").size()
short = months_per_ticker[months_per_ticker < 6].sort_values()
print(f"\ntickers with <6 months of return data: {len(short)}")
print(short.to_string())

banner("1d. Sponsor name anomalies")
# Non-corporate sponsors: university/hospital/NIH hits
bad_patterns = re.compile(r"\b(univers|hospital|clinic|institute|school of medicine|national|NIH|NCI|cancer center|cooperative|foundation|government|college|medical center)\b", re.IGNORECASE)
noncorp_mask = matched["sponsor_name"].fillna("").str.contains(bad_patterns, regex=True, na=False)
print(f"non-corporate sponsor pattern hits: {noncorp_mask.sum()}")
# How many matched?
noncorp_matched = matched[noncorp_mask & (matched["match_type"].isin(["exact", "auto_fuzzy", "manual_confirmed"]))]
print(f"  of those, matched to a ticker: {len(noncorp_matched)}")
if len(noncorp_matched):
    print("  sample:")
    print(noncorp_matched[["sponsor_name", "ticker", "match_type"]].head(20).to_string(index=False))

# Encoding artifacts
enc_mask = matched["sponsor_name"].fillna("").str.contains(r"[^\x00-\x7F]", regex=True, na=False)
print(f"\nsponsor names with non-ASCII chars: {enc_mask.sum()}")
if enc_mask.sum():
    print(matched.loc[enc_mask, "sponsor_name"].value_counts().head(10).to_string())

# "Inc" vs "Inc." variants -- check how many distinct normalizations collapsed
def raw_norm(s: str) -> str:
    return str(s).lower().strip()
variants = matched.groupby(matched["sponsor_name"].fillna("").apply(raw_norm))["sponsor_name"].agg(lambda s: list(set(s))[:3])
multi = variants[variants.apply(len) > 1]
print(f"\nsponsor strings with multiple casings/spacings: {len(multi)}")

banner("2a. Phase distribution")
print("raw phase value counts:")
print(matched["phase"].fillna("<null>").value_counts().to_string())
# normalize via bf.normalize_phase
import importlib.util
spec = importlib.util.spec_from_file_location("bf", Path(__file__).parent / "06_build_factor.py")
bf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bf)
norm_phase = matched["phase"].apply(bf.normalize_phase)
print("\nnormalized phase:")
print(norm_phase.fillna("<null>").value_counts().to_string())
print(f"\nnull after normalization: {norm_phase.isna().sum()}  ({norm_phase.isna().mean():.2%})")
null_rows = matched[norm_phase.isna()]
print("sample raw phase values that normalized to null:")
print(null_rows["phase"].fillna("<null>").value_counts().head(15).to_string())

banner("2b. Date integrity")
sd = pd.to_datetime(matched["start_date"], errors="coerce")
pcd = pd.to_datetime(matched["primary_completion_date"], errors="coerce")
print(f"start_date NaN/invalid: {sd.isna().sum()}  ({sd.isna().mean():.2%})")
print(f"primary_completion_date NaN/invalid: {pcd.isna().sum()}  ({pcd.isna().mean():.2%})")

both = sd.notna() & pcd.notna()
inverted = both & (sd > pcd)
print(f"start_date > primary_completion_date: {inverted.sum()}")
if inverted.sum():
    print(matched.loc[inverted, ["nct_id", "sponsor_name", "start_date", "primary_completion_date"]].head(5).to_string(index=False))

pre2000 = sd.notna() & (sd.dt.year < 2000)
print(f"start_date before 2000: {pre2000.sum()}")
if pre2000.sum():
    print(matched.loc[pre2000, ["nct_id", "sponsor_name", "start_date"]].head(5).to_string(index=False))

future_pcd = pcd.notna() & (pcd > pd.Timestamp("2024-12-31"))
print(f"primary_completion_date in the future (past 2024-12-31): {future_pcd.sum()}")
print(f"  matched to a ticker among those: {(future_pcd & matched['ticker'].notna()).sum()}")

dur = (pcd - sd).dt.days / 365.25
long_dur = dur > 15
print(f"trial duration >15 years: {long_dur.sum()}")
if long_dur.sum():
    print(matched.loc[long_dur, ["nct_id", "sponsor_name", "start_date", "primary_completion_date"]].head(10).to_string(index=False))

banner("2c. Trial status consistency")
print(matched["overall_status"].fillna("<null>").value_counts().to_string())
completed_no_pcd = (matched["overall_status"] == "COMPLETED") & pcd.isna()
completed_future = (matched["overall_status"] == "COMPLETED") & (pcd > pd.Timestamp("2026-04-15"))
print(f"\nCOMPLETED with null primary_completion_date: {completed_no_pcd.sum()}")
print(f"COMPLETED with future (beyond today) PCD: {completed_future.sum()}")

not_yet = (matched["overall_status"] == "NOT_YET_RECRUITING") & (sd < pd.Timestamp("2024-04-15"))
print(f"NOT_YET_RECRUITING with start_date >2yr ago: {not_yet.sum()}")

banner("2d. Duplicate trials")
dup_nct = matched[matched.duplicated("nct_id", keep=False)]
print(f"duplicate nct_id rows: {len(dup_nct)}")
if len(dup_nct):
    print(dup_nct.groupby("nct_id").size().describe())
    print("sample:")
    print(dup_nct.sort_values("nct_id").head(10)[["nct_id", "sponsor_name", "ticker", "match_type"]].to_string(index=False))

banner("2e. Therapeutic area classification")
matched_area = matched.assign(area=matched["conditions"].apply(bf.classify_area))
print(matched_area["area"].value_counts().to_string())
print(f"\nOther %: {(matched_area['area']=='Other').mean():.2%}")
print("\n50 random trials (conditions -> area):")
sample = matched_area.sample(min(50, len(matched_area)), random_state=7)
for _, r in sample.iterrows():
    cond = (r["conditions"] or "")[:100]
    print(f"  [{r['area']:20s}] {cond}")

banner("3a. Returns coverage")
print(f"unique tickers in returns: {returns['ticker'].nunique()}")
print(f"unique tickers in universe: {len(ticker_set)}")
print(f"universe tickers with NO returns: {len(phantom)}  (see 1c)")
print(f"\nmonths per ticker distribution:\n{months_per_ticker.describe().to_string()}")

# Coverage by month
per_month = returns.groupby("date")["ticker"].nunique()
print(f"\nreturns per month distribution:\n{per_month.describe().to_string()}")
low_months = per_month[per_month < per_month.max() * 0.5]
print(f"months with coverage <50% of peak: {len(low_months)}")

banner("3b. Return distribution sanity")
r = returns["return"]
print(r.describe().to_string())
print(f"\n|return| > 1: {(r.abs() > 1).sum()}")
extreme_high = returns[returns["return"] > 1.0]
extreme_low = returns[returns["return"] < -0.9]
print(f"return > +100%: {len(extreme_high)}")
print(extreme_high.sort_values("return", ascending=False).head(15).to_string(index=False))
print(f"\nreturn < -90%: {len(extreme_low)}")
print(extreme_low.sort_values("return").head(15).to_string(index=False))
zero = (returns["return"] == 0.0)
print(f"\nexactly-zero returns: {zero.sum()}  ({zero.mean():.2%})")

# identical returns across tickers in a month
by_month_val = returns.groupby(["date", "return"]).size()
dup_vals = by_month_val[by_month_val > 1]
print(f"\n(date, return) pairs with >1 ticker: {len(dup_vals)} distinct pairs; worst offenders:")
print(dup_vals.sort_values(ascending=False).head(10).to_string())

banner("3c. Survivorship / departures")
last_date = returns.groupby("ticker")["date"].max()
sample_end = pd.Timestamp("2024-12-31")
departed = last_date[last_date < sample_end]
print(f"tickers whose last return is before {sample_end.date()}: {len(departed)}")
# year-by-year pattern
dep_year = departed.dt.year.value_counts().sort_index()
print("departures by year of last return:")
print(dep_year.to_string())

banner("4a. PipelineScore coverage")
per_month_scored = scores.groupby("date").agg(
    n_tickers=("ticker", "nunique"),
    n_positive=("pipeline_score", lambda s: (s > 0).sum()),
    n_zero=("pipeline_score", lambda s: (s == 0).sum()),
).reset_index()
print(per_month_scored.head(5).to_string(index=False))
print("...")
print(per_month_scored.tail(5).to_string(index=False))
print(f"\nn_positive mean: {per_month_scored['n_positive'].mean():.1f} / universe {len(ticker_set)}")
print(f"ratio (positive score / universe): {per_month_scored['n_positive'].mean()/len(ticker_set):.2%}")

banner("4b. Score concentration")
for d in ["2015-06-30", "2017-01-31", "2019-06-30", "2020-06-30", "2022-01-31", "2024-06-30"]:
    t = pd.Timestamp(d)
    sub = scores[scores["date"] == t].sort_values("pipeline_score", ascending=False)
    if sub.empty:
        continue
    top10 = sub.head(10)
    total_long_score = sub[sub["pipeline_score"] >= sub["pipeline_score"].quantile(0.80)]["pipeline_score"].sum()
    top3_share = top10.head(3)["pipeline_score"].sum() / total_long_score if total_long_score else 0
    print(f"\n{d}: top10 tickers")
    print(top10[["ticker", "pipeline_score", "n_active_trials"]].to_string(index=False))
    print(f"  top-3 share of long-portfolio total score: {top3_share:.2%}")

banner("4c. Portfolio turnover")
# Reconstruct quintile membership per month using the fixed code
q_short = cfg["factor"]["quintile_short"]
q_long = cfg["factor"]["quintile_long"]
long_sets: dict[pd.Timestamp, set] = {}
short_sets: dict[pd.Timestamp, set] = {}
for t in sorted(scores["date"].unique()):
    sub = scores[(scores["date"] == t) & (scores["pipeline_score"] > 0)]
    if len(sub) < 10:
        continue
    short_cut = sub["pipeline_score"].quantile(q_short)
    long_cut = sub["pipeline_score"].quantile(q_long)
    long_sets[t] = set(sub[sub["pipeline_score"] >= long_cut]["ticker"])
    short_sets[t] = set(sub[sub["pipeline_score"] <= short_cut]["ticker"])

ts = sorted(long_sets.keys())
long_turn = []
short_turn = []
for a, b in zip(ts, ts[1:]):
    lu = long_sets[a] | long_sets[b]
    if lu:
        long_turn.append(1 - len(long_sets[a] & long_sets[b]) / len(lu))
    su = short_sets[a] | short_sets[b]
    if su:
        short_turn.append(1 - len(short_sets[a] & short_sets[b]) / len(su))
print(f"avg monthly long turnover (Jaccard-complement): {np.mean(long_turn):.2%}")
print(f"avg monthly short turnover: {np.mean(short_turn):.2%}")
print(f"months with 100% long turnover: {sum(x == 1.0 for x in long_turn)}")

banner("4d. Factor return reconciliation")
# Pick 3 months and reconstruct
ret_pivot = returns.pivot(index="date", columns="ticker", values="return").sort_index()
for d in ["2018-03-31", "2020-09-30", "2023-11-30"]:
    t = pd.Timestamp(d)
    if t not in long_sets:
        continue
    long_tks = [c for c in long_sets[t] if c in ret_pivot.columns]
    short_tks = [c for c in short_sets[t] if c in ret_pivot.columns]
    t_next = t + pd.offsets.MonthEnd(1)
    if t_next not in ret_pivot.index:
        continue
    lr = ret_pivot.loc[t_next, long_tks].dropna().mean()
    sr = ret_pivot.loc[t_next, short_tks].dropna().mean()
    manual_pr = lr - sr
    row = factor[factor["date"] == t_next]
    stored = row["PR"].iloc[0] if len(row) else None
    print(f"  score date {d}: manual PR={manual_pr:+.6f}  stored PR={stored:+.6f}  diff={(manual_pr - stored) if stored is not None else 'n/a'}")

banner("5a. FF5 source verification")
print(f"ff5 rows: {len(ff5)}, range: {ff5['date'].min().date()} to {ff5['date'].max().date()}")
print("first 3 rows:")
print(ff5.head(3).to_string(index=False))
print("last 3 rows:")
print(ff5.tail(3).to_string(index=False))
print(f"\nRF summary by year (should rise from ~0 to ~0.004+):")
print(ff5.groupby(ff5["date"].dt.year)["RF"].mean().to_string())

banner("5b. Merge integrity")
ibb_col = "IBB_return"
m = etf_returns[["date", ibb_col, "XBI_return"]].merge(ff5, on="date", how="outer", indicator=True).merge(factor[["date", "PR"]], on="date", how="outer")
print(f"merged rows: {len(m)}")
print("NaN counts:")
print(m.isna().sum().to_string())
print("\n_merge breakdown (etf vs ff5):")
print(m["_merge"].value_counts().to_string())

banner("6a. Universe funnel (2020-06)")
t = pd.Timestamp("2020-06-30")
ibb_tks = set(ibb["ticker"])
print(f"IBB constituents: {len(ibb_tks)}")
matched_tks = set(matched.loc[matched["ticker"].notna(), "ticker"])
print(f"  of those with any matched trial ever: {len(ibb_tks & matched_tks)}")
scored_t = set(scores[(scores["date"] == t) & (scores["pipeline_score"] > 0)]["ticker"])
print(f"  of those with PipelineScore>0 at 2020-06: {len(ibb_tks & scored_t)}")
ret_at_t = set(returns[returns["date"] == t + pd.offsets.MonthEnd(1)]["ticker"])
print(f"  of those with 2020-07 return data: {len(ibb_tks & scored_t & ret_at_t)}")
long_at_t = long_sets.get(t, set())
short_at_t = short_sets.get(t, set())
print(f"  in long portfolio at this t: {len(long_at_t & ibb_tks)}")
print(f"  in short portfolio at this t: {len(short_at_t & ibb_tks)}")

banner("6b. Temporal alignment")
print("constituent as_of_date:", ibb["as_of_date"].iloc[0] if "as_of_date" in ibb.columns else "<absent>")
print("returns date dtype:", returns["date"].dtype, "; day-of-month sample:", returns["date"].drop_duplicates().head(3).dt.day.tolist())
print("ff5 date sample:", ff5["date"].head(3).dt.day.tolist())
print("factor date sample:", factor["date"].head(3).dt.day.tolist())
print("etf_returns date sample:", etf_returns["date"].head(3).dt.day.tolist())
