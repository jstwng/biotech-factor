"""Task 3: Ljung-Box investigation on IBB FF5+PR residuals.

- Saves ACF/PACF figure to output/figures/acf_pacf_ibb.png
- Re-fits IBB FF5+PR with Newey-West lag=6, writes output/nw_lag_sensitivity.json
- Tests Ljung-Box at lags 1, 3, 6, 12
"""
from __future__ import annotations

import json
import pickle

import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR

ETF_RETS = DATA_RAW / "returns" / "etf_returns.csv"
FF5 = DATA_RAW / "ff5" / "ff5_monthly.csv"
FACTOR = DATA_PROCESSED / "factor_returns.csv"

FF5_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]


def _merge(etf_col: str) -> pd.DataFrame:
    etf = pd.read_csv(ETF_RETS, parse_dates=["date"])
    ff5 = pd.read_csv(FF5, parse_dates=["date"])
    pr = pd.read_csv(FACTOR, parse_dates=["date"])
    df = etf[["date", etf_col]].rename(columns={etf_col: "ret"})
    df = df.merge(ff5, on="date").merge(pr[["date", "PR"]], on="date")
    df["excess"] = df["ret"] - df["RF"]
    return df.dropna().reset_index(drop=True)


def main() -> None:
    df = _merge("IBB_return")
    X = df[FF5_FACTORS + ["PR"]]
    y = df["excess"]

    # Baseline (NW lag=3)
    m3 = sm.OLS(y, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    resid = m3.resid

    # 3a: ACF / PACF up to lag 12
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), dpi=300)
    sm.graphics.tsa.plot_acf(resid, ax=axes[0], lags=12)
    axes[0].set_title("ACF of IBB FF5+PR residuals")
    sm.graphics.tsa.plot_pacf(resid, ax=axes[1], lags=12, method="ywm")
    axes[1].set_title("PACF of IBB FF5+PR residuals")
    fig.tight_layout()
    (OUTPUT_DIR / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / "figures" / "acf_pacf_ibb.png")
    plt.close(fig)

    # 3b: NW lag=6
    m6 = sm.OLS(y, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 6})

    # 3c: Ljung-Box at lags 1, 3, 6, 12
    lb = acorr_ljungbox(resid, lags=[1, 3, 6, 12], return_df=True)

    out = {
        "model": "IBB FF5+PR",
        "n_obs": int(m3.nobs),
        "nw_lag_3": {
            "beta_PR": float(m3.params["PR"]),
            "se_PR": float(m3.bse["PR"]),
            "t_PR": float(m3.tvalues["PR"]),
            "p_PR": float(m3.pvalues["PR"]),
        },
        "nw_lag_6": {
            "beta_PR": float(m6.params["PR"]),
            "se_PR": float(m6.bse["PR"]),
            "t_PR": float(m6.tvalues["PR"]),
            "p_PR": float(m6.pvalues["PR"]),
        },
        "ljung_box": {
            int(lag): {"Q": float(lb.loc[lag, "lb_stat"]), "p": float(lb.loc[lag, "lb_pvalue"])}
            for lag in [1, 3, 6, 12]
        },
        "acf_lags_1_12": [float(resid.autocorr(lag=k)) for k in range(1, 13)],
    }

    (OUTPUT_DIR / "nw_lag_sensitivity.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
