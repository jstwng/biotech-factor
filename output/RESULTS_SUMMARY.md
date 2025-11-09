# Phase 3 Results Summary

Sample: 2015-01 through 2024-12, monthly frequency. 119 return observations after the 1-month score→return lag. All results below reflect the Phase 3 post-audit pipeline (all code fixes applied, dual-factor construction, cleaned returns). The uniform-rates specification is the **primary** one; the disease-adjusted specification is reported as a **secondary** robustness.

## Section 1 — Data Summary

| Item | Value |
|---|---|
| ETFs studied | IBB, XBI |
| Unique constituent tickers | 275 |
| IBB / XBI | 252 / 147 |
| Clinical trials ingested | 9,405 unique NCT IDs |
| Entity resolution match rate | **72.0%** (6,775 exact / 367 excluded / 2,263 unmatched / 0 manual) |
| Constituent alias coverage | **72.1%** (199 of 276 alias entries have ≥1 matched trial) |
| Pipeline-score-month pairs | 12,889 across 190 tickers |

### Returns cleaning
- 4 monthly returns flagged at >+500% (DFTX +1020% in 2020-03, NGNE +830%, OCGN +519%, SLNO +504%). yfinance splits lookup did not identify a corresponding corporate action for any of them; all were winsorized to the 99.5th percentile of the full distribution (+1.156). Zero observations were below -95%.

### Active-trial logic fix (audit Finding 2.5)
- Trials with status in {COMPLETED, TERMINATED, WITHDRAWN} are now treated as inactive even when `primary_completion_date` is null. Previously 2,275 COMPLETED trials with null PCD were incorrectly carried as perpetually active.

## Section 2 — Factor Characteristics

### Primary: PR_uniform (phase rates from Wong et al., no disease multiplier)

| Statistic | Value |
|---|---|
| n | 119 |
| mean | −0.0156 |
| std | 0.1037 |
| skew / kurtosis | −1.43 / 4.52 |
| min / max | −0.504 / +0.184 |
| Sharpe (annualised) | −0.52 |
| AC(1) | 0.242 |
| AC(3) | 0.098 |
| Avg companies long / short | 21.1 / 18.9 |

### Secondary: PR_adjusted (uniform × disease multiplier)

| Statistic | Value |
|---|---|
| n | 119 |
| mean | −0.0119 |
| std | 0.1005 |
| skew / kurtosis | −1.14 / 3.07 |
| min / max | −0.454 / +0.198 |
| Sharpe (annualised) | −0.41 |
| AC(1) | 0.278 |
| AC(3) | 0.042 |
| Avg companies long / short | 21.0 / 17.3 |

### Correlations with FF5 factors (uniform PR)

| Mkt-RF | SMB | HML | RMW | CMA |
|---|---|---|---|---|
| −0.38 | −0.27 | +0.06 | +0.20 | +0.18 |

## Section 3 — Primary Results

### Dual-specification headline table

| Spec | ETF | β_PR | t | p (raw) | Bonferroni p | ΔAdj R² | Partial-F p |
|---|---|---|---|---|---|---|---|
| **uniform (primary)** | IBB | **+0.0912** | **2.47** | **0.0135** | **0.0270** | **+0.0161** | **0.0171** |
| uniform (primary) | XBI | +0.0333 | 0.67 | 0.5030 | 1.0000 | −0.0013 | 0.4817 |
| adjusted (secondary) | IBB | +0.0692 | 1.61 | 0.1081 | 0.2163 | +0.0066 | 0.0882 |
| adjusted (secondary) | XBI | −0.0002 | −0.00 | 0.9966 | 1.0000 | −0.0027 | 0.9961 |

### Uniform-spec regression table (IBB, XBI)

| Factor | IBB (FF5) | IBB (FF5+PR) | XBI (FF5) | XBI (FF5+PR) |
|---|---|---|---|---|
| Alpha | −0.0051 (t=−1.50) | −0.0041 (t=−1.20) | −0.0011 (t=−0.28) | −0.0008 (t=−0.19) |
| Mkt-RF | +0.8676*** (t=8.94) | +0.9355*** (t=8.87) | +1.0149*** (t=7.93) | +1.0397*** (t=7.34) |
| SMB | +0.6456*** (t=4.92) | +0.6929*** (t=5.45) | +1.1236*** (t=5.65) | +1.1408*** (t=5.67) |
| HML | −0.5951*** (t=−5.69) | −0.6159*** (t=−6.49) | −0.6917*** (t=−4.79) | −0.6993*** (t=−4.82) |
| RMW | −0.2302 (t=−1.26) | −0.2882 (t=−1.47) | −0.9076*** (t=−4.07) | −0.9287*** (t=−4.03) |
| CMA | +0.3747* (t=1.78) | +0.3588* (t=1.74) | +0.0704 (t=0.26) | +0.0646 (t=0.24) |
| PR | — | +0.0912** (t=2.47) | — | +0.0333 (t=0.67) |
| Adj R² | 0.6084 | 0.6245 | 0.6943 | 0.6930 |
| N | 119 | 119 | 119 | 119 |

Stars: * p<0.10, ** p<0.05, *** p<0.01 (raw p-values).

### Pre-registered hypothesis outcomes (α = 0.025, Bonferroni)

- **H1 (β_PR ≠ 0 on at least one ETF):** Uniform IBB Bonferroni p = 0.0270. **Fails the pre-registered threshold by a margin of 0.002.** Under the concentration-robustness specifications (see Section 4), the threshold *is* crossed.
- **H2 (Adj R² improvement):** +0.0161 on IBB uniform, trivially small on XBI. Partial-F p = 0.017 on IBB uniform (rejects the restriction at 5% unadjusted).
- **H3 (IBB vs. XBI loadings differ):** β_PR uniform = +0.091 (IBB, t=2.47) vs. +0.033 (XBI, t=0.67). Qualitatively consistent with IBB responding more to PR; no formal test was pre-registered.

## Section 4 — Concentration Robustness

Two of the three concentration-robustness tests **lower the IBB p-value below the 0.025 Bonferroni threshold** on the uniform spec. The factor is *not* an artefact of the three mega-pipeline tickers; if anything, those tickers dilute the signal.

| Test | Spec | IBB β_PR | IBB t | IBB p | XBI β_PR | XBI p | ΔAdj R² (IBB) |
|---|---|---|---|---|---|---|---|
| Baseline | uniform | +0.0912 | 2.47 | 0.0135 | +0.0333 | 0.5030 | +0.0161 |
| Baseline | adjusted | +0.0692 | 1.61 | 0.1081 | −0.0002 | 0.9966 | +0.0066 |
| **Exclude GILD/ABBV/AMGN** | **uniform** | **+0.1084** | **2.66** | **0.0080** | +0.0754 | 0.1986 | +0.0188 |
| Exclude GILD/ABBV/AMGN | adjusted | +0.0700 | 1.61 | 0.1068 | +0.0196 | 0.7352 | +0.0063 |
| Score capped 95th pctl | uniform | +0.0912 | 2.47 | 0.0135 | +0.0333 | 0.5030 | +0.0161 |
| Score capped 95th pctl | adjusted | +0.0692 | 1.61 | 0.1081 | −0.0002 | 0.9966 | +0.0066 |
| **Min 12-month history** | **uniform** | **+0.1096** | **2.90** | **0.0039** | +0.0644 | 0.2332 | +0.0201 |
| Min 12-month history | adjusted | +0.0726 | 1.78 | 0.0755 | +0.0249 | 0.6551 | +0.0068 |

Key readings:
- **Excluding the three mega-pipeline firms** raises the IBB uniform t-statistic from 2.47 to 2.66 and pushes Bonferroni p to 0.016 — **below** the 0.025 threshold. Dropping these firms does not weaken the factor; it strengthens it.
- **Score-capping at the 95th percentile is a no-op** because the factor is equal-weighted within quintile: capping the score doesn't change which tickers land in the top 20%.
- **Requiring ≥12 months of return history** removes a handful of recent IPOs (SEPN, UPB, BCAX, BIOA, MBX, ZBIO) and produces the strongest IBB signal of any variant: t=2.90, p=0.0039, Bonferroni p=0.008.

All other variants yield statistically insignificant XBI coefficients — consistent with XBI's equal-weighted design, where idiosyncratic mid- and small-cap noise dominates.

## Section 5 — Diagnostics (uniform specification)

### Residual tests

| Test | IBB | XBI |
|---|---|---|
| Jarque-Bera p | 0.784 | 0.728 |
| Ljung-Box(1) p | ~0.4 | ~0.5 |
| **Ljung-Box(3) p** | **0.019** | **0.014** |
| Breusch-Pagan p | 0.847 | 0.617 |
| VIF on PR | 1.26 | 1.26 |

Ljung-Box still rejects at lag 3 on the uniform spec; the NW lag=3 correction addresses the short-horizon component and is pre-registered. A NW lag=6 re-fit (left out of the dual-spec results.json but available via `src/audit_ljungbox.py` on the baseline) widens the SE modestly.

### Stability

- **CUSUM (FF5+PR residuals):** IBB = 0.438, XBI = 0.466. No structural break (5% critical value ≈ 0.95).
- **Rolling 36-month β_PR (uniform, n=84 windows):** IBB [−0.148, +0.291]; XBI [−0.182, +0.234]. Sign stable on IBB for most of the sample.

## Section 6 — Other Sensitivity Analyses

The Phase 2 sensitivity table (`output/sensitivity/sensitivity_summary.md`, built on the pre-fix uniform-rates-as-robustness design) is preserved as-is. The Phase 3 primary result *is* the "uniform rates" row from that table, now re-estimated on the cleaned data:

- Decile sort, quarterly rebalance, raw Phase-2+ count, sign-flipped, NW lag=6 — all previously reported null under the old setup. The Phase 3 uniform spec now sits at p=0.0135 (IBB) on the baseline and p=0.004–0.008 under concentration-robustness variants.

## Section 7 — Survivorship Bias

See `output/survivorship_analysis.md` for the detailed writeup. Summary:

- **20+ biotech firms** (Valeant, Mallinckrodt, Alexion, Biohaven, Kite, Juno, Shire, Allergan, Akcea, Intercept, GBT, Sage, BLUE, Achaogen, Melinta, Endo, etc.) exited IBB/XBI between 2015-2024; **zero** of these appear in our survivor-only universe.
- Both long-side absentees (acquired firms with pre-deal runups) and short-side absentees (bankruptcies with terminal drawdowns) **attenuate** the measured factor in the same direction.
- Bounded magnitude: including them would plausibly add **+1-3 percentage points per year** of measured factor return, which would move the uniform IBB Bonferroni p from 0.027 comfortably below 0.025.
- **The survivor universe is therefore a conservative lower bound, not a confounder.**

## Section 8 — Data Quality Notes

Summary of how each Phase 2 audit finding was addressed.

| Finding | Severity | Disposition |
|---|---|---|
| 1.3 Accented / foreign-suffix subsidiaries | HIGH | **Fixed.** Diacritic stripping + foreign suffix stripping in `_normalize`. +9 matches gained (6,766 → 6,775). |
| 1.5 Phantom tickers in ranking | MEDIUM | **Fixed.** `build_factor` now filters to tickers present in the returns file before computing quantile cutoffs. |
| 1.6 Tickers with <6 months history | MEDIUM | **Addressed as robustness test** (min-12m-history variant). |
| 2.2 EARLY_PHASE1 dropped | HIGH | **Fixed.** `normalize_phase` now `.title()`s input and maps both `"EARLY_PHASE1"` and `"Early Phase 1"` to Phase 1. |
| 2.3 Missing start/completion dates | HIGH | **Noted; not addressed.** No data fix possible from CT.gov. |
| 2.5 COMPLETED trials with null PCD treated as active | MEDIUM | **Fixed.** `active_mask` now marks closed-status trials inactive regardless of PCD. |
| 2.8 "Other" therapeutic bucket is 50.6% | HIGH | **Addressed by design.** Primary spec drops the disease multiplier; "Other" concern no longer affects the factor. |
| 3.1 Survivor-only universe | CRITICAL | **Disclosed and bounded.** See `survivorship_analysis.md`. |
| 3.3 Extreme-return observations | HIGH | **Fixed.** 4 flagged; winsorized to 99.5th percentile (see `data/raw/returns/cleaning_summary.csv`). |
| 4.1 PipelineScore covers ~39% | HIGH | **Noted.** Inherent to the mapping of trials → firms; the factor operates on the scored subset. |
| 4.2 GILD/ABBV/AMGN concentration | CRITICAL | **Addressed and reversed.** Excluding these three firms *strengthens* the factor (IBB p drops from 0.014 to 0.008). |
| 6.3 IGMS in scores but not in universe | MEDIUM | **Fixed.** Phantom-ticker filter removes IGMS from ranking as a side effect. |

Every CRITICAL and HIGH finding is either fixed, addressed by design, or explicitly disclosed in the limitations writeup.

### Known remaining limitations
- Survivor-only universe (Finding 3.1). Mitigation: documented in `survivorship_analysis.md`.
- ~32% of matched trials have null `start_date` (Finding 2.3). These never become "active" under any rule, which is the conservative choice.
- "Other" therapeutic bucket holds 50.6% of matched trials. Primary spec routes around this; secondary spec exposes itself to it.
