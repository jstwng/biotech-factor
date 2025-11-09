"""Build monthly constituent list for IBB and XBI.

MVP uses the current holdings CSVs as a fixed universe (survivorship_bias_flag
is set). If iShares/SSGA block scripted downloads, place CSVs manually under
`data/raw/constituents/` with names `ibb_raw_*.csv` and `xbi_raw_*.csv` and the
script will detect and parse them.
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from common import DATA_RAW, get_logger, load_config

log = get_logger("ingest_constituents")

CONST_DIR = DATA_RAW / "constituents"

IBB_CSV_URL = (
    "https://www.ishares.com/us/products/239699/ishares-nasdaq-biotechnology-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IBB_holdings&dataType=fund"
)
XBI_CSV_URL = (
    "https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/"
    "etfs/us/holdings-daily-us-en-xbi.xlsx"
)


def _find_raw(prefix: str) -> Path | None:
    matches = sorted(CONST_DIR.glob(f"{prefix}_raw_*.*"))
    return matches[-1] if matches else None


def _download(url: str, dest: Path) -> None:
    headers = {"User-Agent": "Mozilla/5.0 pipeline-risk-factor research script"}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def _parse_ibb(path: Path) -> pd.DataFrame:
    # iShares CSVs have a ~9-line header block. Find the row with "Ticker".
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.lower().startswith('"ticker"') or line.lower().startswith("ticker,"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df.columns = [c.strip() for c in df.columns]
    rename = {"Ticker": "ticker", "Name": "company_name", "Weight (%)": "weight", "Sector": "sector"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df = df[df["ticker"].astype(str).str.match(r"^[A-Z][A-Z.\-]*$", na=False)]
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    return df[["ticker", "company_name", "weight"]].dropna(subset=["ticker"])


def _parse_xbi(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, header=None)
    else:
        df = pd.read_csv(path, header=None)
    # SSGA files have a ~4-line preamble before the header row. The header row
    # contains the literal token "Ticker" in some column (not always col 0).
    header_idx = None
    for i in range(min(20, len(df))):
        row_vals = [str(v).strip().lower() for v in df.iloc[i].values]
        if "ticker" in row_vals and "name" in row_vals:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"could not find header row in {path}")
    df.columns = df.iloc[header_idx].astype(str).str.strip()
    df = df.iloc[header_idx + 1 :].reset_index(drop=True)
    rename_map = {"Ticker": "ticker", "Name": "company_name", "Weight": "weight", "Sector": "sector"}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df = df[df["ticker"].astype(str).str.match(r"^[A-Z][A-Z.\-]*$", na=False)]
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    return df[["ticker", "company_name", "weight"]].dropna(subset=["ticker"])


def build(ticker: str, url: str, ext: str, parser) -> None:
    prefix = ticker.lower()
    raw = _find_raw(prefix)
    if raw is None:
        raw = CONST_DIR / f"{prefix}_raw_{date.today().isoformat()}.{ext}"
        log.info("downloading %s -> %s", url, raw)
        try:
            _download(url, raw)
        except Exception as e:
            log.error(
                "download failed for %s: %s. Drop the holdings file manually at %s",
                ticker, e, raw,
            )
            return
    df = parser(raw)
    df["as_of_date"] = date.today().isoformat()
    df["survivorship_bias_flag"] = True
    out = CONST_DIR / f"{prefix}_constituents.csv"
    df.to_csv(out, index=False)
    log.info("%s: %d tickers -> %s", ticker, len(df), out)


def main() -> None:
    _ = load_config()
    CONST_DIR.mkdir(parents=True, exist_ok=True)
    build("IBB", IBB_CSV_URL, "csv", _parse_ibb)
    build("XBI", XBI_CSV_URL, "xlsx", _parse_xbi)


if __name__ == "__main__":
    main()
