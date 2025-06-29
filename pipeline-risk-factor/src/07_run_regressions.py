"""Run FF5 and FF5+PR regressions on each ETF's monthly excess returns.
Writes results.json and a side-by-side regression table.
"""
from __future__ import annotations

import json
import pickle

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f as f_dist

from common import DATA_PROCESSED, DATA_RAW, OUTPUT_DIR, get_logger, load_config

log = get_logger("regressions")

ETF_RETS = DATA_RAW / "returns" / "etf_returns.csv"
FF5 = DATA_RAW / "ff5" / "ff5_monthly.csv"
FACTOR = DATA_PROCESSED / "factor_returns.csv"

RESULTS_JSON = OUTPUT_DIR / "results.json"
RESIDUALS_PKL = OUTPUT_DIR / "residuals.pkl"
TABLE_PATH = OUTPUT_DIR / "tables" / "regression_table.md"

FF5_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]


def _align(etf_col: str, etf: pd.DataFrame, ff5: pd.DataFrame, pr: pd.DataFrame) -> pd.DataFrame:
    df = etf[["date", etf_col]].rename(columns={etf_col: "ret"})
    df = df.merge(ff5, on="date", how="inner")
    df = df.merge(pr[["date", "PR"]], on="date", how="inner")
    df["excess"] = df["ret"] - df["RF"]
    return df.dropna().reset_index(drop=True)


def _fit(y: pd.Series, X: pd.DataFrame, nw_lag: int) -> sm.regression.linear_model.RegressionResultsWrapper:
    X = sm.add_constant(X)
    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lag})
    return model


def _model_summary(model) -> dict:
    params = model.params.to_dict()
    bse = model.bse.to_dict()
    tvals = model.tvalues.to_dict()
    pvals = model.pvalues.to_dict()
    return {
        "coefficients": {
            name: {
                "estimate": float(params[name]),
                "std_error": float(bse[name]),
                "t_stat": float(tvals[name]),
                "p_value": float(pvals[name]),
            } for name in params
        },
        "adj_r_squared": float(model.rsquared_adj),
        "r_squared": float(model.rsquared),
        "aic": float(model.aic),
        "bic": float(model.bic),
        "f_statistic": float(model.fvalue) if model.fvalue is not None else None,
        "f_p_value": float(model.f_pvalue) if model.f_pvalue is not None else None,
        "n_obs": int(model.nobs),
        "ssr": float(model.ssr),
        "df_model": int(model.df_model),
    }


def _partial_f(restricted, unrestricted, n: int) -> dict:
    ssr_r = restricted.ssr
    ssr_u = unrestricted.ssr
    q = 1
    k = unrestricted.df_model + 1
    f_stat = ((ssr_r - ssr_u) / q) / (ssr_u / (n - k))
    p_val = 1 - f_dist.cdf(f_stat, q, n - k)
    return {"f_stat": float(f_stat), "p_value": float(p_val), "df_num": q, "df_den": int(n - k)}


def _fmt(v: float, stars: str = "") -> str:
    return f"{v:+.4f}{stars}"


def _stars(p: float) -> str:
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def _render_table(results: dict) -> str:
    etfs = list(results.keys())
    header = "| Factor | " + " | ".join(
        f"{e} (FF5) | {e} (FF5+PR)" for e in etfs
    ) + " |"
    sep = "|" + "---|" * (1 + 2 * len(etfs))
    rows = [header, sep]

    def row(name: str, key: str) -> None:
        cells = [name]
        for e in etfs:
            for m in ("model1", "model2"):
                coefs = results[e][m]["coefficients"]
                if key not in coefs:
                    cells.append("--")
                    continue
                c = coefs[key]
                cells.append(f"{_fmt(c['estimate'], _stars(c['p_value']))} (t={c['t_stat']:.2f})")
        rows.append("| " + " | ".join(cells) + " |")

    row("Alpha", "const")
    for f in FF5_FACTORS:
        row(f, f)
    row("PR", "PR")

    def stat_row(label: str, getter) -> None:
        cells = [label]
        for e in etfs:
            for m in ("model1", "model2"):
                cells.append(getter(results[e][m]))
        rows.append("| " + " | ".join(cells) + " |")

    stat_row("Adj R2", lambda d: f"{d['adj_r_squared']:.4f}")
    stat_row("AIC", lambda d: f"{d['aic']:.2f}")
    stat_row("BIC", lambda d: f"{d['bic']:.2f}")
    stat_row("N", lambda d: f"{d['n_obs']}")

    rows.append("")
    rows.append("Significance: * p<0.10, ** p<0.05, *** p<0.01. Newey-West t-statistics in parentheses.")
    return "\n".join(rows)


def main() -> None:
    cfg = load_config()
    nw_lag = cfg["stats"]["newey_west_lag"]
    bonferroni_k = cfg["stats"]["bonferroni_tests"]

    etf = pd.read_csv(ETF_RETS, parse_dates=["date"])
    ff5 = pd.read_csv(FF5, parse_dates=["date"])
    pr = pd.read_csv(FACTOR, parse_dates=["date"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "tables").mkdir(parents=True, exist_ok=True)

    results: dict = {}
    residuals: dict = {}
    for spec in cfg["etfs"]:
        t = spec["ticker"]
        col = f"{t}_return"
        if col not in etf.columns:
            log.warning("missing %s in etf_returns", col)
            continue
        df = _align(col, etf, ff5, pr)
        y = df["excess"]
        X1 = df[FF5_FACTORS]
        X2 = df[FF5_FACTORS + ["PR"]]
        m1 = _fit(y, X1, nw_lag)
        m2 = _fit(y, X2, nw_lag)

        r1 = _model_summary(m1)
        r2 = _model_summary(m2)
        comparison = {
            "delta_adj_r_squared": r2["adj_r_squared"] - r1["adj_r_squared"],
            "delta_aic": r2["aic"] - r1["aic"],
            "delta_bic": r2["bic"] - r1["bic"],
            "partial_f_test": _partial_f(m1, m2, len(df)),
        }
        pr_p = r2["coefficients"]["PR"]["p_value"]
        comparison["pr_p_raw"] = pr_p
        comparison["pr_p_bonferroni"] = min(pr_p * bonferroni_k, 1.0)

        results[t] = {"model1": r1, "model2": r2, "comparison": comparison, "n_obs": len(df)}
        residuals[t] = {
            "dates": df["date"].tolist(),
            "model1": m1.resid.tolist(),
            "model2": m2.resid.tolist(),
        }
        log.info("%s: n=%d, beta_PR=%.4f (p=%.4f)", t, len(df), r2["coefficients"]["PR"]["estimate"], pr_p)

    RESULTS_JSON.write_text(json.dumps(results, indent=2, default=str))
    RESIDUALS_PKL.write_bytes(pickle.dumps(residuals))
    TABLE_PATH.write_text(_render_table(results) + "\n")
    log.info("wrote %s, %s, %s", RESULTS_JSON, RESIDUALS_PKL, TABLE_PATH)


if __name__ == "__main__":
    main()
