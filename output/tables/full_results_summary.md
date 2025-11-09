## Pipeline Risk Factor — Phase 3 dual-spec results summary

## Table 1. Factor Summary Statistics

| Statistic | Uniform | Adjusted |
|---|---|---|
| n | 119 | 119 |
| mean | -0.0156 | -0.0119 |
| std | 0.1037 | 0.1005 |
| skew | -1.4336 | -1.1392 |
| kurtosis | 4.5248 | 3.0675 |
| sharpe_annualized | -0.5199 | -0.4108 |
| ac_1 | 0.2420 | 0.2783 |
| avg_n_long | 21.1008 | 20.9580 |
| avg_n_short | 18.8824 | 17.3025 |

## Table 2a. Regression Results (Uniform (primary))

| Factor | IBB (FF5) | IBB (FF5+PR) | XBI (FF5) | XBI (FF5+PR) |
|---|---|---|---|---|
| Alpha | -0.0051 (t=-1.50) | -0.0041 (t=-1.20) | -0.0011 (t=-0.28) | -0.0008 (t=-0.19) |
| Mkt-RF | +0.8676*** (t=8.94) | +0.9355*** (t=8.87) | +1.0149*** (t=7.93) | +1.0397*** (t=7.34) |
| SMB | +0.6456*** (t=4.92) | +0.6929*** (t=5.45) | +1.1236*** (t=5.65) | +1.1408*** (t=5.67) |
| HML | -0.5951*** (t=-5.69) | -0.6159*** (t=-6.49) | -0.6917*** (t=-4.79) | -0.6993*** (t=-4.82) |
| RMW | -0.2302 (t=-1.26) | -0.2882 (t=-1.47) | -0.9076*** (t=-4.07) | -0.9287*** (t=-4.03) |
| CMA | +0.3747* (t=1.78) | +0.3588* (t=1.74) | +0.0704 (t=0.26) | +0.0646 (t=0.24) |
| PR | -- | +0.0912** (t=2.47) | -- | +0.0333 (t=0.67) |
| Adj R2 | 0.6084 | 0.6245 | 0.6943 | 0.6930 |
| AIC | -430.81 | -434.88 | -382.84 | -381.37 |
| BIC | -414.13 | -415.42 | -366.17 | -361.92 |
| N | 119 | 119 | 119 | 119 |

Significance: * p<0.10, ** p<0.05, *** p<0.01. Newey-West t-statistics in parentheses.


## Table 2b. Regression Results (Disease-adjusted (secondary))

| Factor | IBB (FF5) | IBB (FF5+PR) | XBI (FF5) | XBI (FF5+PR) |
|---|---|---|---|---|
| Alpha | -0.0051 (t=-1.50) | -0.0047 (t=-1.39) | -0.0011 (t=-0.28) | -0.0011 (t=-0.29) |
| Mkt-RF | +0.8676*** (t=8.94) | +0.9219*** (t=8.52) | +1.0149*** (t=7.93) | +1.0147*** (t=7.07) |
| SMB | +0.6456*** (t=4.92) | +0.6866*** (t=5.21) | +1.1236*** (t=5.65) | +1.1234*** (t=5.62) |
| HML | -0.5951*** (t=-5.69) | -0.5993*** (t=-6.01) | -0.6917*** (t=-4.79) | -0.6917*** (t=-4.79) |
| RMW | -0.2302 (t=-1.26) | -0.2523 (t=-1.34) | -0.9076*** (t=-4.07) | -0.9075*** (t=-4.06) |
| CMA | +0.3747* (t=1.78) | +0.3468* (t=1.71) | +0.0704 (t=0.26) | +0.0705 (t=0.26) |
| PR | -- | +0.0692 (t=1.61) | -- | -0.0002 (t=-0.00) |
| Adj R2 | 0.6084 | 0.6150 | 0.6943 | 0.6916 |
| AIC | -430.81 | -431.91 | -382.84 | -380.84 |
| BIC | -414.13 | -412.46 | -366.17 | -361.39 |
| N | 119 | 119 | 119 | 119 |

Significance: * p<0.10, ** p<0.05, *** p<0.01. Newey-West t-statistics in parentheses.


## Table 3. Model Comparison

| Spec | ETF | dAdjR2 | PartF | PartF p | dAIC | dBIC | PR p (raw) | PR p (Bonf) |
|---|---|---|---|---|---|---|---|---|
| uniform | IBB | +0.0162 | 5.861 | 0.0171 | -4.070 | -1.291 | 0.0135 | 0.0270 |
| uniform | XBI | -0.0014 | 0.498 | 0.4817 | +1.472 | +4.251 | 0.5030 | 1.0000 |
| adjusted | IBB | +0.0067 | 2.959 | 0.0882 | -1.103 | +1.676 | 0.1081 | 0.2163 |
| adjusted | XBI | -0.0027 | 0.000 | 0.9961 | +2.000 | +4.779 | 0.9966 | 1.0000 |

## Table 4. Diagnostic Tests

| Spec | ETF | Model | JB p | LB(3) p | BP p | max VIF |
|---|---|---|---|---|---|---|
| uniform | IBB | FF5 | 0.786 | 0.011 | 0.925 | 2.25 |
| uniform | IBB | FF5+PR | 0.784 | 0.019 | 0.847 | 2.25 |
| uniform | XBI | FF5 | 0.792 | 0.009 | 0.555 | 2.25 |
| uniform | XBI | FF5+PR | 0.728 | 0.014 | 0.617 | 2.25 |
| adjusted | IBB | FF5 | 0.786 | 0.011 | 0.925 | 2.25 |
| adjusted | IBB | FF5+PR | 0.758 | 0.012 | 0.933 | 2.25 |
| adjusted | XBI | FF5 | 0.792 | 0.009 | 0.555 | 2.25 |
| adjusted | XBI | FF5+PR | 0.792 | 0.009 | 0.678 | 2.25 |

## Table 5. Concentration Robustness

| Test | Spec | IBB beta | IBB t | IBB p | XBI beta | XBI t | XBI p | dAdjR2 IBB |
|---|---|---|---|---|---|---|---|---|
| Baseline | uniform | +0.0912 | 2.47 | 0.0135 | +0.0333 | 0.67 | 0.5030 | +0.0162 |
| Baseline | adjusted | +0.0692 | 1.61 | 0.1081 | -0.0002 | -0.00 | 0.9966 | +0.0067 |
| Exclude top-3 (GILD/ABBV/AMGN) | uniform | +0.1084 | 2.65 | 0.0080 | +0.0754 | 1.29 | 0.1986 | +0.0249 |
| Exclude top-3 (GILD/ABBV/AMGN) | adjusted | +0.0700 | 1.61 | 0.1068 | +0.0196 | 0.34 | 0.7352 | +0.0083 |
| Score capped 95th pctl | uniform | +0.0912 | 2.47 | 0.0135 | +0.0333 | 0.67 | 0.5030 | +0.0162 |
| Score capped 95th pctl | adjusted | +0.0692 | 1.61 | 0.1081 | -0.0002 | -0.00 | 0.9966 | +0.0067 |
| Min 12m history | uniform | +0.1096 | 2.89 | 0.0039 | +0.0644 | 1.19 | 0.2332 | +0.0271 |
| Min 12m history | adjusted | +0.0726 | 1.78 | 0.0755 | +0.0249 | 0.45 | 0.6551 | +0.0104 |


## Data Quality Summary

- Total trials: 9405
- Match rate: 0.720
- Unique tickers matched: 199
- Alias coverage: 0.721
- Matched by type: {'exact': 6775, 'unmatched': 2263, 'excluded': 367}

See `RESULTS_SUMMARY.md` and `survivorship_analysis.md` for the full writeup.
