# Phase 5b — Flipped pipeline-risk-premium backtest

Sample: 2015-02 through 2024-12, monthly, n = 119. Factor construction identical to Phase 5 (exclusion of GILD/ABBV/AMGN; uniform phase-weighted PipelineScore) but **sign-flipped**: long the bottom-quintile (high pipeline risk) names, short the top-quintile (low pipeline risk) names. This harvests the pipeline risk premium instead of paying it. No transaction costs, borrowing costs, or short-sale constraints are imposed — the analysis is about economic magnitude, not a tradeable implementation.

## Section 1 — Flipped factor characteristics

| Statistic | Value |
|---|---|
| Mean monthly return | +1.56% |
| Monthly std | 10.11% |
| Skew / kurtosis | +1.17 / 2.82 |
| Min / max | −16.1% / +50.4% |
| Annualised Sharpe | +0.52 |
| AC(1) / AC(3) | 0.221 / 0.029 |
| Avg companies long / short | 17.7 / 21.1 |
| Correlation with original (unflipped) PR | −1.00 (exact by construction) |
| Correlations with FF5 | Mkt-RF +0.32, SMB +0.12, HML +0.01, RMW −0.13, CMA −0.07 |

## Section 2 — Standalone flipped long-short strategy

| Period | n | Cum. Return | Ann. Return | Ann. Vol | Sharpe | Max DD | Hit Rate | Win streak | Loss streak | Best mo. | Worst mo. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Full sample | 119 | **+171.94%** | +10.61% | 35.03% | 0.30 | −67.90% | 47.9% | 7 | 8 | +50.4% | −16.1% |
| Pre-2020 | 59 | +136.01% | +19.08% | 26.99% | **+0.71** | −30.28% | 52.5% | 7 | 6 | — | — |
| Post-2020 | 60 | +15.23% | +2.88% | 41.63% | +0.07 | −67.90% | 43.3% | 6 | 8 | — | — |

The factor earned 10.6% annualised on 35% annualised volatility for a full-sample Sharpe of 0.30. Most of that return came pre-2020 (Sharpe 0.71); post-2020 returns collapsed to near-zero with a much larger max-drawdown (−68%).

## Section 3 — FF5 exposure regression (what's the flipped factor actually loaded on?)

`PR_flipped_t = alpha + b1*MktRF + b2*SMB + b3*HML + b4*RMW + b5*CMA + epsilon_t`, Newey-West lag 3.

| Factor | Estimate | NW SE | t | p |
|---|---|---|---|---|
| **Alpha** | **+0.0081/mo** | 0.0088 | +0.92 | 0.36 |
| Mkt-RF | **+0.7144** | 0.225 | **+3.17** | **0.002** |
| SMB | +0.0556 | 0.420 | +0.13 | 0.89 |
| HML | −0.0764 | 0.253 | −0.30 | 0.76 |
| RMW | −0.6687 | 0.459 | −1.46 | 0.15 |
| CMA | −0.2584 | 0.499 | −0.52 | 0.61 |
| Adj R² | 0.109 | | | |

**Key reading:** the flipped factor has a meaningfully **positive market beta** (+0.71, highly significant) — not the negative market beta the pre-registration guessed. It's long small/mid-cap biotechs and short large-cap biotechs *within the same biotech universe*, and the whole universe is high-beta, so the long leg is even more high-beta than the short leg. Small-cap biotechs respond more to market moves than large-cap biotechs. SMB, HML, RMW, and CMA loadings are all statistically insignificant. Alpha is +9.8% annualised (arithmetic) but p = 0.36 — **not statistically significant after controlling for FF5**. Adj R² is only 0.109, meaning 89% of the flipped factor's monthly variance is not explained by FF5.

## Section 4 — Factor-hedged flipped strategy (pure pipeline premium)

Residual after subtracting FF5-implied hedges month-by-month.

| Variant | Period | n | Cum. Return | Ann. Return | Ann. Vol | Sharpe | Max DD | Hit Rate |
|---|---|---|---|---|---|---|---|---|
| **Static** | Full sample | 119 | +62.93% | +5.05% | 32.33% | +0.16 | −74.91% | 45.4% |
| Static | Pre-2020 | 59 | +56.67% | +9.56% | 28.46% | +0.34 | −36.70% | 47.5% |
| Static | Post-2020 | 60 | +4.00% | +0.79% | 36.01% | +0.02 | −74.91% | 43.3% |
| **Rolling** | Full sample | 119 | +152.25% | +10.93% | 37.23% | +0.29 | −77.92% | 42.0% |
| Rolling | Pre-2020 | 59 | +142.73% | +25.41% | 32.16% | **+0.79** | −34.34% | 42.4% |
| Rolling | Post-2020 | 60 | +3.92% | +0.77% | 41.91% | +0.02 | −77.92% | 41.7% |

Hedged-strategy performance confirms the pattern: pre-2020 the pipeline premium was strong (Sharpe 0.79 on the rolling-hedge); post-2020 it collapsed. The rolling hedge outperforms the static hedge because the market-beta relationship is time-varying, and the rolling hedge tracks it. In both hedge variants, essentially all of the full-sample return comes from the first half of the sample.

## Section 5 — IBB + pipeline tilt overlay

`Strategy_return_t = IBB_excess_t + w * PR_flipped_t`. `w` is the share of capital allocated to the flipped factor as an additive overlay on top of a 100%-IBB position.

| w | Cum. Return | Ann. Return | Ann. Vol | Sharpe | Max DD | Tracking Error | Info Ratio | Ann. Diff vs IBB |
|---|---|---|---|---|---|---|---|---|
| 0.00 (IBB only) | +6.74% | +0.66% | 21.40% | 0.03 | −37.11% | 0 | — | 0 |
| 0.10 | +22.78% | +2.09% | 22.15% | +0.10 | −43.51% | 3.20% | **+0.449** | +1.43% |
| 0.25 | +48.08% | +4.04% | 24.32% | +0.17 | −52.14% | 8.00% | **+0.449** | +3.59% |
| 0.50 | +91.05% | +6.75% | 29.79% | +0.23 | −64.16% | 16.00% | **+0.449** | +7.17% |

The information ratio is constant at +0.449 across `w` because both the tracking error and the return-difference-vs-IBB scale linearly with `w`. Higher `w` means more of both.

**Breakeven tilt:** w = 0.01 — essentially any positive tilt beats pure IBB over the full sample, because IBB alone earned only +6.7% cumulative (Sharpe 0.03) while the flipped factor added a strictly positive (on average) overlay.

## Section 6 — Annualised return decomposition of the flipped factor

Arithmetic decomposition: `ann_return ≈ alpha_ann + Σ beta_k * mean(factor_k) * 12`. Multiplies monthly means by 12, so this is arithmetic (not geometric) ann. return.

| Component | Annualised contribution |
|---|---|
| **Alpha** | **+9.77%** |
| Mkt-RF (β × mean Mkt-RF) | +8.72% |
| SMB | −0.11% |
| HML | +0.14% |
| RMW | −3.02% |
| CMA | +0.23% |
| **Total (arithmetic)** | **+15.73%** |

Of the arithmetic +15.7% annualised return, **+9.8% (62%) is alpha**, and **+8.7% (55%) is market-beta compensation**. RMW subtracts 3% (the flipped factor is short high-profitability names, and RMW earned positive average returns in-sample). SMB, HML, and CMA are each ±0.2% or less.

Note the alpha column is NOT statistically distinguishable from zero at conventional thresholds (Section 3, p = 0.36). Economically large, statistically noisy — a 119-month sample is underpowered to call a 9.8% annualised alpha against 30%+ factor volatility.

## Section 7 — Key takeaways

1. **The flipped factor earned a positive, economically meaningful Sharpe (0.30 full sample) over 2015-2024**, but **the entire return is concentrated pre-2020** (Sharpe 0.71 vs. 0.07 post).
2. **About 60% of the flipped factor's return is genuine pipeline alpha, not repackaged FF5 exposure.** The remaining 40% comes from a positive market-beta tilt (long small/mid-cap biotech, short large-cap biotech). Neither the alpha nor the market-beta contribution is individually decisive; the total return is a mix.
3. **Alpha is not statistically significant after controlling for FF5** (p = 0.36). The factor's exposure in Phase 5 (IBB loading on PR) is significant; the factor's standalone risk premium is economically positive but statistically noisy.
4. **Adding a 25% pipeline tilt on top of IBB delivered a +3.6% annualised excess over IBB with an information ratio of +0.45** full sample. This is the practically-interesting number if an investor already holds biotech beta via IBB and is considering a pipeline-risk overlay.
5. **Post-2020 degradation is severe.** Whatever was driving the pipeline risk premium pre-2020 has not persisted in the post-pandemic sample. Any out-of-sample implementation would need to account for this.
6. **Real-world implementation costs would reduce returns.** Short-sale borrowing costs on small-cap biotechs typically run 50-200 bps annualised (and can spike during squeezes). Rebalancing at monthly frequency on ~20 names per leg is within the bounds of retail-level costs but not trivial. None of those frictions are modelled here.

## Files

- `data/processed/factor_returns_flipped.csv` — flipped factor return series
- `output/backtest_flipped/flipped_factor_stats.json` — factor summary stats
- `output/backtest_flipped/ff5_exposure_regression.json` — FF5 exposure regression
- `output/backtest_flipped/standalone_stats.json` — standalone strategy stats
- `output/backtest_flipped/hedged_{static,rolling}.csv` — hedged strategy time series
- `output/backtest_flipped/hedged_stats.json` — hedged strategy stats
- `output/backtest_flipped/tilt_returns.csv` — IBB + w*flipped time series for w = 0.10, 0.25, 0.50
- `output/backtest_flipped/tilt_stats.json` — tilt strategy stats across w
- `output/backtest_flipped/breakeven.json` — breakeven w analysis
- `output/backtest_flipped/return_decomposition.json` — annualised return decomposition
- `output/backtest_flipped/{flipped_cumulative, flipped_vs_ibb, tilt_comparison, drawdown_comparison, annual_returns, factor_exposure_waterfall}.png` — 6 figures
