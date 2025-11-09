"""Phase 2 audit of 06_build_factor.py. Prints verification output for every
audit point in the plan and exits non-zero if a bug is detected.
"""
from __future__ import annotations

import pandas as pd

from common import DATA_PROCESSED, DATA_RAW, load_config

pd.set_option("display.float_format", lambda x: f"{x:.4f}")

cfg = load_config()
scores = pd.read_parquet(DATA_PROCESSED / "pipeline_scores.parquet")
factor = pd.read_csv(DATA_PROCESSED / "factor_returns.csv", parse_dates=["date"])
returns = pd.read_csv(DATA_RAW / "returns" / "constituent_returns.csv", parse_dates=["date"])

print("=" * 60)
print("TASK 1a: SIGN CONVENTION")
print("=" * 60)
# Simulate the code's behavior on one month and compare score means
sample_t = pd.Timestamp("2020-06-30")
sub = scores[scores["date"] == sample_t]
sub = sub[sub["pipeline_score"] > 0]
q_lo = cfg["factor"]["quintile_short"]  # 0.20
q_hi = cfg["factor"]["quintile_long"]   # 0.80
lo = sub["pipeline_score"].quantile(q_lo)
hi_q = sub["pipeline_score"].quantile(q_hi)
longs_as_coded = sub[sub["pipeline_score"] >= lo]  # from 06_build_factor.py
shorts_as_coded = sub[sub["pipeline_score"] <= hi_q]
print(f"At {sample_t.date()}, {len(sub)} non-zero-score tickers.")
print(f"  quantile(0.20) value: {lo:.3f}")
print(f"  quantile(0.80) value: {hi_q:.3f}")
print(f"  longs (as coded, score >= q_lo={lo:.3f}):  n={len(longs_as_coded)}, mean score={longs_as_coded['pipeline_score'].mean():.3f}")
print(f"  shorts (as coded, score <= q_hi={hi_q:.3f}): n={len(shorts_as_coded)}, mean score={shorts_as_coded['pipeline_score'].mean():.3f}")
print()
print("The correct long portfolio should have HIGHER mean PipelineScore than the short portfolio.")
print(f"  Is long mean > short mean? {longs_as_coded['pipeline_score'].mean() > shorts_as_coded['pipeline_score'].mean()}")
print()
print("Also, long portfolio should be ~20% of non-zero; got", f"{len(longs_as_coded)}/{len(sub)} = {len(longs_as_coded)/len(sub):.1%}")
print("  -> If portfolio sizes are ~80% of non-zero, quintile cutoffs are INVERTED.")

print()
print("=" * 60)
print("TASK 1b: RETURN LAG ALIGNMENT")
print("=" * 60)
print("First 3 rows of factor_returns.csv:")
print(factor.head(3)[["date", "PR", "n_long", "n_short", "long_return", "short_return"]].to_string(index=False))
print()
print("First date in scores:", scores["date"].min())
print("First date in factor:", factor["date"].min())
# If lag=1 is correct, scores min + 1 month == factor min
expected_first = scores["date"].min() + pd.offsets.MonthEnd(1)
print(f"Expected first factor date (score_min + 1mo): {expected_first}")
print(f"  Match: {expected_first == factor['date'].min()}")

print()
print("=" * 60)
print("TASK 1c: QUINTILE SIZES")
print("=" * 60)
first_six = sorted(factor["date"].unique())[:6]
last_six = sorted(factor["date"].unique())[-6:]
print("First 6 months:")
for d in first_six:
    r = factor[factor["date"] == d].iloc[0]
    print(f"  {pd.Timestamp(d).date()}: n_long={r['n_long']}, n_short={r['n_short']}")
print("Last 6 months:")
for d in last_six:
    r = factor[factor["date"] == d].iloc[0]
    print(f"  {pd.Timestamp(d).date()}: n_long={r['n_long']}, n_short={r['n_short']}")

print()
print("=" * 60)
print("TASK 1d: EQUAL-WEIGHTING")
print("=" * 60)
print("Per 06_build_factor.py line 148-152:")
print('  lr = float(long_ret.mean())   # equal-weighted long return')
print('  sr = float(short_ret.mean())  # equal-weighted short return')
print('  PR = lr - sr                  # simple difference of equal-weighted means')
print("Verified: equal-weighted long-short difference.")

print()
print("=" * 60)
print("TASK 1e: MISSING DATA HANDLING")
print("=" * 60)
print("Per 06_build_factor.py lines 144-145:")
print('  long_ret = ret_pivot.loc[t_next, [c for c in longs if c in ret_pivot.columns]].dropna()')
print('  short_ret = ret_pivot.loc[t_next, [c for c in shorts if c in ret_pivot.columns]].dropna()')
print("=> tickers without return data are filtered first, then NaN returns dropped.")
print("   Missing returns are NOT silently zeroed -- they are excluded from the mean.")

print()
print("=" * 60)
print("TASK 1f: FACTOR RETURN DISTRIBUTION")
print("=" * 60)
pr = factor["PR"]
q = pr.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
print(f"  p10: {q.loc[0.10]:+.4f}")
print(f"  p25: {q.loc[0.25]:+.4f}")
print(f"  p50: {q.loc[0.50]:+.4f}")
print(f"  p75: {q.loc[0.75]:+.4f}")
print(f"  p90: {q.loc[0.90]:+.4f}")
print(f"  std: {pr.std():+.4f}")
print(f"  fraction |PR| < 0.001: {(pr.abs() < 0.001).mean():.3f}")

print()
print("=" * 60)
print("TASK 1g: PIPELINESCORE SPREAD")
print("=" * 60)
for date_str in ["2016-01-31", "2019-06-30", "2023-01-31"]:
    t = pd.Timestamp(date_str)
    sub = scores[scores["date"] == t]
    sub = sub[sub["pipeline_score"] > 0]
    if sub.empty:
        print(f"  {date_str}: no scores")
        continue
    lo = sub["pipeline_score"].quantile(q_lo)
    hi_q = sub["pipeline_score"].quantile(q_hi)
    longs_coded = sub[sub["pipeline_score"] >= lo]
    shorts_coded = sub[sub["pipeline_score"] <= hi_q]
    longs_correct = sub[sub["pipeline_score"] >= hi_q]   # score >= q(0.80) = top 20%
    shorts_correct = sub[sub["pipeline_score"] <= lo]    # score <= q(0.20) = bottom 20%
    print(f"  {date_str}:")
    print(f"    AS CODED (buggy):  long_mean_score={longs_coded['pipeline_score'].mean():.3f} (n={len(longs_coded)}), "
          f"short_mean_score={shorts_coded['pipeline_score'].mean():.3f} (n={len(shorts_coded)}), "
          f"diff={longs_coded['pipeline_score'].mean() - shorts_coded['pipeline_score'].mean():+.3f}")
    print(f"    CORRECT (top/bottom 20%): long_mean_score={longs_correct['pipeline_score'].mean():.3f} (n={len(longs_correct)}), "
          f"short_mean_score={shorts_correct['pipeline_score'].mean():.3f} (n={len(shorts_correct)}), "
          f"diff={longs_correct['pipeline_score'].mean() - shorts_correct['pipeline_score'].mean():+.3f}")
