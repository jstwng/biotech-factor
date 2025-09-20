# Phase 1 Results Summary

Sample period: 2015-01 through 2024-12 (120 calendar months; 119 monthly return observations after the 1-month look-ahead lag).

All numerical results below reflect the re-run after the Phase 2 audit fix described in Section 6. Pre-audit numbers that appeared in the original `phase1` commit history are not reproduced here; the fixed pipeline supersedes them.

## Section 1 — Data Summary

| Item | Value |
|---|---|
| ETFs studied | IBB, XBI |
| Constituents (union) | 275 |
| IBB constituents | 252 |
| XBI constituents | 147 |
| Clinical trials queried | 9,506 unique NCT IDs (1,882 API calls) |
| Entity resolution match rate | 71.9% (6,766 exact / 367 excluded / 2,272 unmatched / 0 manual-review) |
| Constituent alias coverage | 71.7% of tickers have ≥1 matched trial |
| Pipeline-score-month pairs | 13,026 across 190 tickers |

**PipelineScore distribution (across all company-month pairs):**
mean = 1.74, std = 4.90, min = 0, 25% = 0.19, median = 0.49, 75% = 1.28, max = 50.77.

## Section 2 — Factor Characteristics

| Statistic | PR |
|---|---|
| n (monthly) | 119 |
| mean | −0.0110 |
| std | 0.0984 |
| skew | −1.17 |
| kurtosis | 2.82 |
| min / max | −0.426 / +0.190 |
| autocorrelation(1) | 0.221 |
| autocorrelation(3) | 0.029 |
| Sharpe (annualized) | −0.39 |
| Avg companies long | 21.6 |
| Avg companies short | 17.7 |

**Correlations with FF5 factors (using the PR series):**

| Mkt-RF | SMB | HML | RMW | CMA |
|---|---|---|---|---|
| −0.41 | −0.30 | +0.04 | +0.15 | +0.20 |

## Section 3 — Primary Results

Regressions of each ETF's monthly excess return on FF5 alone (Model 1) and FF5+PR (Model 2). Newey-West HAC standard errors, lag = 3 (pre-registered).

### Regression table

| Factor | IBB (FF5) | IBB (FF5+PR) | XBI (FF5) | XBI (FF5+PR) |
|---|---|---|---|---|
| Alpha | −0.0051 (t=−1.50) | −0.0046 (t=−1.36) | −0.0011 (t=−0.28) | −0.0010 (t=−0.25) |
| Mkt-RF | +0.8676*** (t=8.94) | +0.9329*** (t=8.75) | +1.0149*** (t=7.93) | +1.0352*** (t=7.25) |
| SMB | +0.6456*** (t=4.92) | +0.6987*** (t=5.44) | +1.1236*** (t=5.65) | +1.1401*** (t=5.69) |
| HML | −0.5951*** (t=−5.69) | −0.6032*** (t=−6.16) | −0.6917*** (t=−4.79) | −0.6942*** (t=−4.78) |
| RMW | −0.2302 (t=−1.26) | −0.2606 (t=−1.38) | −0.9076*** (t=−4.07) | −0.9170*** (t=−4.09) |
| CMA | +0.3747* (t=1.78) | +0.3374* (t=1.66) | +0.0704 (t=0.26) | +0.0587 (t=0.22) |
| PR | — | +0.0906* (t=1.96) | — | +0.0282 (t=0.48) |
| Adj R² | 0.6084 | 0.6219 | 0.6943 | 0.6924 |
| AIC | −430.81 | −434.05 | −382.84 | −381.18 |
| BIC | −414.13 | −414.59 | −366.17 | −361.72 |
| N | 119 | 119 | 119 | 119 |

Stars: * p<0.10, ** p<0.05, *** p<0.01 (raw p-values). Bonferroni threshold for the PR test at α=0.05 across two ETFs is **0.025**.

### Model comparison

| ETF | ΔAdj R² | Partial F | Partial F p | ΔAIC | ΔBIC | PR p (raw) | PR p (Bonferroni) |
|---|---|---|---|---|---|---|---|
| IBB | +0.014 | 5.043 | 0.0267 | −3.24 | −0.46 | 0.0501 | 0.1001 |
| XBI | −0.002 | 0.313 | 0.5772 | +1.67 | +4.45 | 0.6286 | 1.0000 |

### Pre-registered hypothesis outcomes (α = 0.025 Bonferroni)

- **H1 (β_PR ≠ 0 on at least one ETF):** IBB raw p = 0.0501, Bonferroni p = 0.1001. XBI raw p = 0.6286. **H1 is not rejected.**
- **H2 (Adj R² improvement when adding PR):** IBB improves by +0.014; XBI decreases by 0.002. No formal joint test is pre-registered; the change is economically small on IBB and negative on XBI.
- **H3 (IBB and XBI PR loadings differ):** β_PR = +0.091 (IBB) vs. +0.028 (XBI); t-stats 1.96 vs. 0.48. A formal equality test is not pre-registered and is not computed here.

## Section 4 — Diagnostics

### Residual tests (FF5+PR model)

| Test | IBB | XBI |
|---|---|---|
| Jarque-Bera p | 0.736 | 0.711 |
| Ljung-Box(1) p | 0.449 | 0.484 |
| Ljung-Box(3) p | **0.011** | **0.010** |
| Ljung-Box(6) p | **0.015** | **0.007** |
| Ljung-Box(12) p | **1.0e-4** | **7.0e-4** |
| Breusch-Pagan p | 0.900 | 0.645 |
| Max VIF (FF5+PR, any regressor) | 2.25 | 2.25 |
| VIF on PR | 1.29 | 1.29 |

Residual autocorrelation is present. See Section 6 and the NW lag=6 sensitivity in Section 5.

### Structural stability

- **CUSUM (FF5+PR residuals):** IBB = 0.420, XBI = 0.448. No evidence of a structural break (conventional 5% critical value ≈ 0.95).
- **Rolling 36-month β_PR:** 84 windows each; IBB range [−0.122, +0.199]; XBI range [−0.117, +0.139]. See `output/figures/rolling_beta_pr_IBB.png` and `rolling_beta_pr_XBI.png`.

## Section 5 — Sensitivity Analysis

All specifications use the bug-fixed factor construction. None pass the 0.025 Bonferroni threshold on either ETF.

| Specification | β_PR (IBB) | t (IBB) | p (IBB) | β_PR (XBI) | t (XBI) | p (XBI) | ΔAdj R² (IBB) |
|---|---|---|---|---|---|---|---|
| Baseline (quintile, monthly, NW=3) | +0.0906 | 1.96 | 0.0501 | +0.0282 | 0.48 | 0.6286 | +0.0135 |
| Decile sort (top/bottom 10%) | +0.0459 | 1.77 | 0.0766 | +0.0175 | 0.51 | 0.6122 | +0.0060 |
| Include zero-score in sort | +0.0868 | 1.91 | 0.0560 | +0.0198 | 0.34 | 0.7359 | +0.0123 |
| Quarterly rebalancing (3-month hold) | +0.0731 | 1.60 | 0.1101 | −0.0113 | −0.20 | 0.8414 | +0.0075 |
| Raw count of Phase 2+ trials | +0.0435 | 0.91 | 0.3634 | −0.0427 | −0.73 | 0.4652 | −0.0013 |
| Sign-flipped factor | −0.0906 | −1.96 | 0.0501 | −0.0282 | −0.48 | 0.6286 | +0.0135 |
| Baseline factor, NW lag = 6 | +0.0906 | 1.82 | 0.0681 | — | — | — | — |

Note on the "exclude-zero" specification requested in the plan: the baseline already filters score > 0 before computing quantiles, so the pre-registered baseline *is* the exclude-zero specification. The row above labelled "Include zero-score in sort" reports the opposite variant to bracket the choice.

The flipped factor is the mirror image of baseline (same |t|, same Adj R² contribution) by construction.

## Section 6 — Audit Findings

### Implementation audit (Tasks 1-2)

| Check | Result |
|---|---|
| Sign convention (long = high PipelineScore) | Long portfolio does have higher mean score than short. |
| Quintile cutoff construction | **Bug found and fixed.** See detail below. |
| Return lag alignment | Correct. First factor date = 2015-02-28, pairing January 2015 scores with February 2015 returns. |
| Equal-weighting | Correct. `mean(long) − mean(short)`. |
| Missing return handling | Correct. Tickers without return data are filtered before averaging; NaN returns are dropped, not zero-filled. |
| FF5 date alignment | Correct. Inner join on month-end dates. |
| Dependent variable | Correct. `excess = ret − RF`; `Mkt-RF` is an RHS regressor, not double-subtracted. |
| Newey-West HAC | Correct. `cov_type="HAC"`, `maxlags=3` from config. |
| Observation count | 119 for all four models. Matches the expectation from the 1-month lag. |

**Quintile cutoff bug (src/06_build_factor.py, lines 138-139 pre-fix).** The pre-fix code was:

```python
lo = sub["pipeline_score"].quantile(q_lo)       # q_lo = 0.20 → 20th percentile VALUE
hi_q = sub["pipeline_score"].quantile(q_hi)     # q_hi = 0.80 → 80th percentile VALUE
longs = sub[sub["pipeline_score"] >= lo]         # everyone above q20 = top 80%
shorts = sub[sub["pipeline_score"] <= hi_q]      # everyone below q80 = bottom 80%
```

The variable names were misleading and the comparisons were inverted. Instead of two non-overlapping 20% tails, the "long" and "short" sets were each ~80% of non-zero-score companies with heavy overlap (anyone scoring between the 20th and 80th percentile was in both). Symptoms: avg_n_long = 79.2, avg_n_short = 73.3 (expected ~20 each); PR std compressed to 0.024 (post-fix: 0.098); long-short PipelineScore spread on 2020-06 = 1.57 (post-fix: ~11.2).

**Fix** (06_build_factor.py and the equivalent helper in 08_diagnostics.py):

```python
short_cut = sub["pipeline_score"].quantile(q_lo)   # 20th percentile
long_cut  = sub["pipeline_score"].quantile(q_hi)   # 80th percentile
longs  = sub[sub["pipeline_score"] >= long_cut]    # top 20%
shorts = sub[sub["pipeline_score"] <= short_cut]   # bottom 20%
```

All results in Sections 1-5 reflect the fixed pipeline. Existing unit tests continued to pass.

### Ljung-Box investigation (Task 3)

- IBB FF5+PR residual ACF shows the largest deviations at lag 3 (−0.30) and lag 8 (−0.41). Other lags are within ±0.20.
- Ljung-Box is rejected at every pre-registered lag (1 is borderline; 3, 6, 12 all reject). The rejection at lag 12 is driven largely by the lag-8 autocorrelation, not by a seasonal (12-month) pattern.
- Re-fitting with NW lag = 6 widens the PR standard error modestly (0.0462 → 0.0497). The PR t-statistic moves from 1.96 to 1.82; p from 0.050 to 0.068. The substantive conclusion (no rejection at 0.025 Bonferroni) is unchanged.
- No evidence of a calendar-seasonal component at lags 6 or 12 beyond what the lag-8 spike produces.

### No other bugs found

The regression, Fama-French parsing, return assembly, entity resolution, and exclusion logic were verified end-to-end. No further implementation concerns remain for the baseline specification.
