# Pipeline Risk Factor -- Phase 1 Results

## Table 1. Pipeline Risk Factor Summary Statistics

| Statistic | Value |
|---|---|
| n | 119 |
| mean | -0.0110 |
| std | 0.0984 |
| skew | -1.1733 |
| kurtosis | 2.8228 |
| min | -0.4260 |
| max | 0.1896 |
| ac_1 | 0.2211 |
| ac_3 | 0.0286 |
| ac_6 | -0.0533 |
| sharpe_annualized | -0.3882 |
| avg_n_long | 21.5630 |
| avg_n_short | 17.7479 |

## Table 2. Regression Results

| Factor | IBB (FF5) | IBB (FF5+PR) | XBI (FF5) | XBI (FF5+PR) |
|---|---|---|---|---|
| Alpha | -0.0051 (t=-1.50) | -0.0046 (t=-1.36) | -0.0011 (t=-0.28) | -0.0010 (t=-0.25) |
| Mkt-RF | +0.8676*** (t=8.94) | +0.9329*** (t=8.75) | +1.0149*** (t=7.93) | +1.0352*** (t=7.25) |
| SMB | +0.6456*** (t=4.92) | +0.6987*** (t=5.44) | +1.1236*** (t=5.65) | +1.1401*** (t=5.69) |
| HML | -0.5951*** (t=-5.69) | -0.6032*** (t=-6.16) | -0.6917*** (t=-4.79) | -0.6942*** (t=-4.78) |
| RMW | -0.2302 (t=-1.26) | -0.2606 (t=-1.38) | -0.9076*** (t=-4.07) | -0.9170*** (t=-4.09) |
| CMA | +0.3747* (t=1.78) | +0.3374* (t=1.66) | +0.0704 (t=0.26) | +0.0587 (t=0.22) |
| PR | -- | +0.0906* (t=1.96) | -- | +0.0282 (t=0.48) |
| Adj R2 | 0.6084 | 0.6219 | 0.6943 | 0.6924 |
| AIC | -430.81 | -434.05 | -382.84 | -381.18 |
| BIC | -414.13 | -414.59 | -366.17 | -361.72 |
| N | 119 | 119 | 119 | 119 |

Significance: * p<0.10, ** p<0.05, *** p<0.01. Newey-West t-statistics in parentheses.


## Table 3. Model Comparison

| ETF | dAdjR2 | PartF | PartF p | dAIC | dBIC | PR p (raw) | PR p (Bonf) |
|---|---|---|---|---|---|---|---|
| IBB | +0.0135 | 5.043 | 0.0267 | -3.241 | -0.462 | 0.0501 | 0.1001 |
| XBI | -0.0019 | 0.313 | 0.5772 | +1.668 | +4.447 | 0.6286 | 1.0000 |

## Table 4. Diagnostic Tests

| ETF | Model | JB p | LB(3) p | BP p | max VIF |
|---|---|---|---|---|---|
| IBB | FF5 | 0.786 | 0.011 | 0.925 | 2.25 |
| IBB | FF5+PR | 0.736 | 0.011 | 0.900 | 2.25 |
| XBI | FF5 | 0.792 | 0.009 | 0.555 | 2.25 |
| XBI | FF5+PR | 0.711 | 0.010 | 0.645 | 2.25 |

## Table 5. Robustness Checks

| ETF | Spec | beta_PR | p | n |
|---|---|---|---|---|
| IBB | tercile | +0.1138 | 0.0381 | 119 |
| IBB | uniform_rates | +0.1558 | 0.0009 | 119 |
| IBB | subperiod_2015_2019 | +0.0964 | 0.2563 | 59 |
| IBB | subperiod_2020_2024 | +0.0293 | 0.5357 | 60 |
| XBI | tercile | +0.0439 | 0.5454 | 119 |
| XBI | uniform_rates | +0.1547 | 0.0054 | 119 |
| XBI | subperiod_2015_2019 | +0.0216 | 0.8194 | 59 |
| XBI | subperiod_2020_2024 | -0.0383 | 0.5123 | 60 |


## Data Quality Summary

- Total trials: 9405
- Match rate: 0.719
- Unique tickers matched: 198
- Alias coverage: 0.717
- Matched by type: {'exact': 6766, 'unmatched': 2272, 'excluded': 367}
