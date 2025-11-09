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


## Newey-West Lag Sensitivity: PR_uniform on IBB

| Variant | Lag | PR beta | NW t-stat | p-value |
|---|---|---|---|---|
| Baseline | 1 | +0.0912 | 2.71 | 0.0068 |
| Baseline | 3 | +0.0912 | 2.47 | 0.0135 |
| Baseline | 6 | +0.0912 | 2.17 | 0.0301 |
| Baseline | 12 | +0.0912 | 1.89 | 0.0588 |
| Excl. top 3 | 1 | +0.1084 | 2.84 | 0.0045 |
| Excl. top 3 | 3 | +0.1084 | 2.65 | 0.0080 |
| Excl. top 3 | 6 | +0.1084 | 2.36 | 0.0182 |
| Excl. top 3 | 12 | +0.1084 | 2.04 | 0.0410 |

**Flags (|t| < 1.96):** baseline lag 12 t=1.89



## Subsample Stability: PR_uniform on IBB

| Variant | Period | n | PR beta | NW SE | t-stat | p-value | 95% CI |
|---|---|---|---|---|---|---|---|
| Baseline | pre 2020 | 59 | +0.1033 | 0.0508 | 2.03 | 0.0421 | [+0.0037, +0.2029] |
| Baseline | post 2020 | 60 | +0.0147 | 0.0440 | 0.33 | 0.7385 | [-0.0715, +0.1008] |
| Baseline | full sample | 119 | +0.0912 | 0.0369 | 2.47 | 0.0135 | [+0.0188, +0.1635] |
| Excl. top 3 | pre 2020 | 59 | +0.1370 | 0.0631 | 2.17 | 0.0299 | [+0.0133, +0.2608] |
| Excl. top 3 | post 2020 | 60 | +0.0178 | 0.0410 | 0.43 | 0.6642 | [-0.0626, +0.0982] |
| Excl. top 3 | full sample | 119 | +0.1084 | 0.0409 | 2.65 | 0.0080 | [+0.0283, +0.1886] |

### Interpretation
- **Baseline:** beta sign consistent across sub-periods: YES. Magnitude ratio (larger/smaller): 7.04x. 95% CIs overlap: YES.
- **Excl. top 3:** beta sign consistent across sub-periods: YES. Magnitude ratio (larger/smaller): 7.70x. 95% CIs overlap: YES.

Power note: each sub-period has n≈60, half the full sample. A non-significant p-value in one sub-period does not demonstrate absence of effect; it may reflect lower power.

