# Phase 5 — Beta-neutral backtest of the exclusion-top-3 uniform IBB specification

Sample: 2015-02 through 2024-12, monthly, n = 119. Universe excludes GILD, ABBV, and AMGN. Pipeline score is the uniform Wong-et-al phase-weighted score (no disease multiplier). Long-short factor is equal-weighted top-quintile minus bottom-quintile. Cleaned returns (Phase 3 winsorisation) used throughout.

## Section 1 — Full-sample regression

`IBB_excess ~ Mkt-RF + SMB + HML + RMW + CMA + PR_uniform_excl`, Newey-West HAC lag 3.

| Factor | Estimate | NW SE | t | p |
|---|---|---|---|---|
| Alpha | −0.0042 | 0.0034 | −1.25 | 0.210 |
| Mkt-RF | +0.9451 | 0.108 | +8.75 | <0.001 |
| SMB | +0.6517 | 0.131 | +4.99 | <0.001 |
| HML | −0.6034 | 0.094 | −6.46 | <0.001 |
| RMW | −0.3028 | 0.199 | −1.52 | 0.129 |
| CMA | +0.3467 | 0.203 | +1.71 | 0.087 |
| **PR_uniform_excl** | **+0.1084** | **0.041** | **+2.65** | **0.008** |

Adj R² = 0.6332, n = 119. PR coefficient passes the pre-registered 0.025 Bonferroni threshold (Bonferroni p = 0.016).

## Section 2 — Static-hedge strategy (full-sample betas, look-ahead)

| Period | n | Cum. Return | Ann. Return | Ann. Vol | Sharpe | Max DD | Hit Rate |
|---|---|---|---|---|---|---|---|
| Full sample | 119 | −53.19% | −7.37% | 13.18% | −0.56 | −57.43% | 45.4% |
| Pre-2020 | 59 | −28.94% | −6.71% | 13.74% | −0.49 | −40.81% | 42.4% |
| Post-2020 | 60 | −34.13% | −8.01% | 12.72% | −0.63 | −36.72% | 48.3% |

## Section 3 — Rolling-hedge strategy (out-of-sample 36-month betas; expanding window between months 12 and 36)

| Period | n | Cum. Return | Ann. Return | Ann. Vol | Sharpe | Max DD | Hit Rate |
|---|---|---|---|---|---|---|---|
| Full sample | 107 | −51.41% | −7.78% | 14.35% | −0.54 | −51.94% | 46.7% |
| Pre-2020 | 47 | −35.86% | −10.72% | 14.00% | −0.77 | −39.46% | 42.6% |
| Post-2020 | 60 | −24.25% | −5.40% | 14.69% | −0.37 | −29.27% | 50.0% |

## Section 4 — Annual returns

| Year | IBB excess | FF5-explained | Strategy (rolling) | Strategy (static) |
|---|---|---|---|---|
| 2015 | +5.2% | +1.6% | n/a (warmup) | +4.2% |
| 2016 | −21.6% | +7.3% | −2.4% | −25.6% |
| 2017 | +20.0% | +18.8% | −11.5% | +1.0% |
| 2018 | −11.1% | −3.1% | −11.9% | −7.6% |
| 2019 | +22.7% | +25.8% | −15.6% | −1.7% |
| 2020 | +25.5% | +52.9% | −23.5% | −20.0% |
| 2021 | +1.0% | +3.1% | +3.4% | −2.2% |
| 2022 | −14.9% | −29.5% | +20.9% | +18.7% |
| 2023 | −1.2% | +15.2% | −10.0% | −15.5% |
| 2024 | −7.3% | +9.7% | −12.0% | −16.1% |

## Section 5 — Cumulative attribution (static, full sample)

The decomposition `IBB_excess_t = alpha + ff5_explained_t + pr_attr_t + residual_t` holds month-by-month within float tolerance (max abs error < 1e-10). Cumulating the components compounds them as if they were independent return streams; the four series do not equal the total IBB cumulative return when compounded multiplicatively, but they do sum exactly when accumulated as monthly contributions.

**Multiplicative cumulation (real-money compounding of each stream):**

| Stream | Cumulative return |
|---|---|
| FF5-explained | +121.96% |
| PR-attributable | −16.18% |
| Alpha | −39.48% |
| Residual | −7.55% |
| Total IBB excess | +6.74% |

**Additive cumulation (sum of monthly contributions, used in fig 4a):** the four streams sum exactly to the cumulative monthly-contribution version of IBB excess at every horizon.

## Section 6 — Interpretation

The PR factor is **statistically significant** (Bonferroni p = 0.016) and **economically meaningful in beta**: a +0.108 loading on a factor with monthly std ~10% means a one-std PR move shifts IBB excess by about 1.1%/month. But the **factor itself earned negative returns** in this sample (cum factor return −16% over 119 months when scaled by beta_PR). Both the PR-attributable and alpha components contribute negatively to cumulative excess return. FF5 alone explains roughly 122% of the cumulative excess (compounded), with PR + alpha + residual together subtracting about 63 percentage points to land at the realised +6.7%.

The beta-neutral hedged strategies (both static and rolling) are deeply negative across the full sample and in both subperiods. This is the predicted consequence of (a) the negative in-sample PR-factor mean, and (b) the negative alpha. The hedge correctly strips Mkt/SMB/HML/RMW/CMA exposure; what's left is alpha plus PR exposure plus residual, and all three averaged negative.

The Phase 4 finding that the factor's t-statistic concentrates pre-2020 is visible here too: the rolling-hedge strategy lost 11%/year pre-2020 and only 5%/year post-2020, even though by point estimate β_PR is similar across windows.

**The take-away for the paper:** the factor is real (statistically distinguishable from zero exposure on IBB after controlling for FF5) but its risk-premium sign is negative in this sample. A PR-factor-mimicking long-short portfolio would have lost money over 2015-2024, even though the factor explains incremental variance in IBB beyond FF5.

## Files

- `data/processed/factor_returns_excl_top3.csv` — source factor series
- `output/backtest/attribution.csv` — monthly decomposition into alpha + FF5-explained + PR-attributable + residual
- `output/backtest/attribution_cumulative.csv` — both additive and multiplicative cumulation of each component
- `output/backtest/strategy_static.csv` — static-hedge strategy returns (look-ahead)
- `output/backtest/strategy_rolling.csv` — rolling-hedge strategy returns (out-of-sample) plus the rolling beta time series for each FF5 + PR factor
- `output/backtest/rolling_beta_pr_with_se.csv` — 36-month rolling β_PR + SE
- `output/backtest/annual_returns.csv` — annual return table
- `output/backtest/backtest_stats.json` — full regression + per-period summary stats
- `output/backtest/cumulative_attribution.png` — fig 4a
- `output/backtest/strategy_cumulative_return.png` — fig 4b
- `output/backtest/rolling_beta_pr_with_ci.png` — fig 4c
- `output/backtest/annual_returns_bar.png` — fig 4d
- `output/backtest/drawdown.png` — fig 4e
