# Pipeline Risk Factor -- Phase 1 Results

## Table 1. Pipeline Risk Factor Summary Statistics

| Statistic | Value |
|---|---|
| n | 119 |
| mean | -0.0036 |
| std | 0.0237 |
| skew | -1.1865 |
| kurtosis | 3.7254 |
| min | -0.1160 |
| max | 0.0409 |
| ac_1 | 0.2238 |
| ac_3 | 0.0414 |
| ac_6 | -0.0731 |
| sharpe_annualized | -0.5291 |
| avg_n_long | 79.1933 |
| avg_n_short | 73.3277 |

## Table 2. Regression Results

| Factor | IBB (FF5) | IBB (FF5+PR) | XBI (FF5) | XBI (FF5+PR) |
|---|---|---|---|---|
| Alpha | -0.0051 (t=-1.50) | -0.0043 (t=-1.27) | -0.0011 (t=-0.28) | -0.0012 (t=-0.29) |
| Mkt-RF | +0.8676*** (t=8.94) | +0.9166*** (t=8.77) | +1.0149*** (t=7.93) | +1.0123*** (t=7.26) |
| SMB | +0.6456*** (t=4.92) | +0.6957*** (t=5.18) | +1.1236*** (t=5.65) | +1.1209*** (t=5.52) |
| HML | -0.5951*** (t=-5.69) | -0.5977*** (t=-6.03) | -0.6917*** (t=-4.79) | -0.6915*** (t=-4.79) |
| RMW | -0.2302 (t=-1.26) | -0.2668 (t=-1.40) | -0.9076*** (t=-4.07) | -0.9056*** (t=-4.06) |
| CMA | +0.3747* (t=1.78) | +0.3237 (t=1.56) | +0.0704 (t=0.26) | +0.0731 (t=0.27) |
| PR | -- | +0.2992 (t=1.58) | -- | -0.0159 (t=-0.06) |
| Adj R2 | 0.6084 | 0.6149 | 0.6943 | 0.6916 |
| AIC | -430.81 | -431.87 | -382.84 | -380.85 |
| BIC | -414.13 | -412.42 | -366.17 | -361.40 |
| N | 119 | 119 | 119 | 119 |

Significance: * p<0.10, ** p<0.05, *** p<0.01. Newey-West t-statistics in parentheses.


## Table 3. Model Comparison

| ETF | dAdjR2 | PartF | PartF p | dAIC | dBIC | PR p (raw) | PR p (Bonf) |
|---|---|---|---|---|---|---|---|
| IBB | +0.0066 | 2.923 | 0.0901 | -1.066 | +1.713 | 0.1130 | 0.2261 |
| XBI | -0.0027 | 0.005 | 0.9416 | +1.994 | +4.773 | 0.9483 | 1.0000 |

## Table 4. Diagnostic Tests

| ETF | Model | JB p | LB(3) p | BP p | max VIF |
|---|---|---|---|---|---|
| IBB | FF5 | 0.786 | 0.011 | 0.925 | 2.24 |
| IBB | FF5+PR | 0.751 | 0.010 | 0.944 | 2.24 |
| XBI | FF5 | 0.792 | 0.009 | 0.555 | 2.24 |
| XBI | FF5+PR | 0.802 | 0.009 | 0.681 | 2.24 |

## Table 5. Robustness Checks

| ETF | Spec | beta_PR | p | n |
|---|---|---|---|---|
| IBB | tercile | +0.2159 | 0.0729 | 119 |
| IBB | uniform_rates | +0.3544 | 0.2996 | 119 |
| IBB | subperiod_2015_2019 | +0.1925 | 0.5196 | 59 |
| IBB | subperiod_2020_2024 | +0.1204 | 0.5313 | 60 |
| XBI | tercile | +0.0605 | 0.7099 | 119 |
| XBI | uniform_rates | -0.1315 | 0.7606 | 119 |
| XBI | subperiod_2015_2019 | -0.2164 | 0.5909 | 59 |
| XBI | subperiod_2020_2024 | -0.1959 | 0.4333 | 60 |


## Data Quality Summary

- Total trials: 9405
- Match rate: 0.719
- Unique tickers matched: 198
- Alias coverage: 0.717
- Matched by type: {'exact': 6766, 'unmatched': 2272, 'excluded': 367}
