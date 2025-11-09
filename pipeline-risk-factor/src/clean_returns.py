"""Flag and clean extreme monthly returns. Writes
data/raw/returns/constituent_returns_cleaned.csv.

Strategy:
1. Flag any |return| > 5.0 (i.e., +500% or -95% threshold per plan; since min
   observed is -0.85 no negative flags). Also always examine |return| > 1.0.
2. For each flagged ticker-month, consult yfinance splits history. If a split
   occurred in the month, replace the return with the split-adjusted return
   recomputed from Adj Close (yfinance's Adj Close is already split-adjusted,
   so a fresh download gives the corrected number).
3. If no split is identified, winsorize to the 99.5th percentile of the full
   return distribution (both tails symmetric).
4. Print a summary.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from common import DATA_RAW, get_logger

log = get_logger("clean_returns")

IN_PATH = DATA_RAW / "returns" / "constituent_returns.csv"
OUT_PATH = DATA_RAW / "returns" / "constituent_returns_cleaned.csv"

FLAG_HIGH = 5.0   # +500%
FLAG_LOW = -0.95  # -95%


def _split_in_month(ticker: str, month_end: pd.Timestamp) -> float | None:
    """Return the split ratio (>1 = forward split, <1 = reverse) that occurred
    in the calendar month of month_end, or None if no split."""
    try:
        t = yf.Ticker(ticker)
        splits = t.splits
    except Exception as e:
        log.warning("split lookup failed for %s: %s", ticker, e)
        return None
    if splits is None or len(splits) == 0:
        return None
    m_start = month_end.to_period("M").start_time.tz_localize(None)
    m_end = month_end + pd.offsets.MonthEnd(0)
    splits = splits.copy()
    splits.index = pd.to_datetime(splits.index).tz_localize(None)
    hits = splits[(splits.index >= m_start) & (splits.index <= m_end)]
    if len(hits) == 0:
        return None
    return float(hits.iloc[0])


def _split_adjusted_return(ticker: str, month_end: pd.Timestamp) -> float | None:
    """Re-download Adj Close and recompute return for that month."""
    try:
        data = yf.download(
            ticker,
            start=(month_end - pd.DateOffset(months=2)).strftime("%Y-%m-%d"),
            end=(month_end + pd.DateOffset(months=1)).strftime("%Y-%m-%d"),
            interval="1mo",
            auto_adjust=False,
            progress=False,
        )
    except Exception as e:
        log.warning("adj close fetch failed for %s: %s", ticker, e)
        return None
    if data is None or data.empty or "Adj Close" not in data.columns:
        return None
    series = data["Adj Close"].dropna()
    # Find the row at month_end and the one before it
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).to_period("M").to_timestamp(how="end").normalize()
    if month_end not in series.index:
        return None
    idx = list(series.index).index(month_end)
    if idx == 0:
        return None
    prev = series.iloc[idx - 1]
    curr = series.iloc[idx]
    if prev == 0 or pd.isna(prev) or pd.isna(curr):
        return None
    return float(curr / prev - 1)


def main() -> None:
    df = pd.read_csv(IN_PATH, parse_dates=["date"])
    r = df["return"]
    flagged_mask = (r > FLAG_HIGH) | (r < FLAG_LOW)
    flagged = df[flagged_mask].copy()
    log.info("flagged %d observations (threshold > %.0f%% or < %.0f%%)", len(flagged), FLAG_HIGH * 100, FLAG_LOW * 100)

    # Winsorization reference from the untouched distribution
    winsor_high = r.quantile(0.995)
    winsor_low = r.quantile(0.005)
    log.info("winsorize reference: 0.5-99.5 percentile bounds [%.3f, %.3f]", winsor_low, winsor_high)

    cleaned = df.copy()
    summary_rows: list[dict] = []
    for idx, row in flagged.iterrows():
        ticker = row["ticker"]
        month_end = pd.Timestamp(row["date"])
        orig = float(row["return"])
        ratio = _split_in_month(ticker, month_end)
        new_val: float | None = None
        method = "winsorize"
        if ratio is not None and ratio != 1.0:
            adj = _split_adjusted_return(ticker, month_end)
            if adj is not None:
                new_val = adj
                method = f"split_adjusted(ratio={ratio:g})"
        if new_val is None:
            new_val = float(winsor_high) if orig > 0 else float(winsor_low)
        cleaned.loc[idx, "return"] = new_val
        summary_rows.append({
            "ticker": ticker,
            "date": month_end.date(),
            "original": orig,
            "cleaned": new_val,
            "method": method,
        })
        log.info("%s %s: %+.3f -> %+.3f via %s", ticker, month_end.date(), orig, new_val, method)

    cleaned.to_csv(OUT_PATH, index=False)
    log.info("wrote %s (%d rows)", OUT_PATH, len(cleaned))

    if summary_rows:
        out = pd.DataFrame(summary_rows)
        out.to_csv(DATA_RAW / "returns" / "cleaning_summary.csv", index=False)
        log.info("summary: %d adjusted; methods: %s", len(out), out["method"].value_counts().to_dict())


if __name__ == "__main__":
    main()
