"""Download monthly adjusted close prices for IBB, XBI, and all constituent
stocks. Produces etf_returns.csv and constituent_returns.csv.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from common import DATA_RAW, get_logger, load_config

log = get_logger("ingest_returns")

RET_DIR = DATA_RAW / "returns"
CONST_DIR = DATA_RAW / "constituents"


def _month_end(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Normalize any monthly-stamp index to calendar month-end."""
    return pd.DatetimeIndex(idx).tz_localize(None).to_period("M").to_timestamp(how="end").normalize()


def _monthly_returns(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Download monthly Adj Close, return long-form DataFrame [date, ticker, return]."""
    try:
        data = yf.download(
            tickers=tickers,
            start=start,
            end=end,
            interval="1mo",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception as e:  # network / bulk failure
        log.warning("yf.download failed for batch of %d: %s", len(tickers), e)
        return pd.DataFrame(columns=["date", "ticker", "return"])

    rows: list[pd.DataFrame] = []
    if data is None or data.empty:
        return pd.DataFrame(columns=["date", "ticker", "return"])

    def _push(ticker: str, series: pd.Series) -> None:
        s = pd.to_numeric(series, errors="coerce").dropna()
        if len(s) < 2:
            return
        ret = s.pct_change().dropna()
        if ret.empty:
            return
        rows.append(pd.DataFrame({
            "date": _month_end(ret.index),
            "ticker": ticker,
            "return": ret.values,
        }))

    if isinstance(data.columns, pd.MultiIndex):
        tickers_with_data = list({t for t, _ in data.columns})
        for tkr in tickers_with_data:
            try:
                _push(tkr, data[tkr]["Adj Close"])
            except KeyError:
                continue
    else:
        if "Adj Close" in data.columns:
            _push(tickers[0], data["Adj Close"])

    if not rows:
        return pd.DataFrame(columns=["date", "ticker", "return"])
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    cfg = load_config()
    RET_DIR.mkdir(parents=True, exist_ok=True)
    start, end = cfg["start_date"], cfg["end_date"]

    etf_tickers = [e["ticker"] for e in cfg["etfs"]]
    etf_long = _monthly_returns(etf_tickers, start, end)
    etf_wide = etf_long.pivot(index="date", columns="ticker", values="return")
    etf_wide.columns = [f"{c}_return" for c in etf_wide.columns]
    etf_wide = etf_wide.reset_index()
    etf_wide.to_csv(RET_DIR / "etf_returns.csv", index=False)
    log.info("etf_returns: %d rows", len(etf_wide))

    # Union of constituents across ETFs
    all_tickers: set[str] = set()
    for etf in etf_tickers:
        path = CONST_DIR / f"{etf.lower()}_constituents.csv"
        if not path.exists():
            log.warning("missing constituent file: %s", path)
            continue
        df = pd.read_csv(path)
        all_tickers.update(df["ticker"].dropna().astype(str).tolist())

    all_tickers -= set(etf_tickers)
    tickers = sorted(all_tickers)
    log.info("downloading returns for %d constituents", len(tickers))

    # yfinance handles batches internally, but chunk to keep failures local
    frames: list[pd.DataFrame] = []
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        chunk = tickers[i : i + batch_size]
        try:
            frames.append(_monthly_returns(chunk, start, end))
        except Exception as e:
            log.warning("batch starting at %d failed: %s", i, e)

    cons = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "ticker", "return"])
    cons.to_csv(RET_DIR / "constituent_returns.csv", index=False)
    n_valid = cons["ticker"].nunique()
    log.info("constituent_returns: %d rows, %d tickers with data (of %d requested)", len(cons), n_valid, len(tickers))


if __name__ == "__main__":
    main()
