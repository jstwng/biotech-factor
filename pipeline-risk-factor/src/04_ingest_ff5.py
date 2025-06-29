"""Download and parse Fama-French 5-factor monthly data."""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import requests

from common import DATA_RAW, get_logger, load_config

log = get_logger("ingest_ff5")

FF5_DIR = DATA_RAW / "ff5"


def main() -> None:
    cfg = load_config()
    FF5_DIR.mkdir(parents=True, exist_ok=True)

    resp = requests.get(cfg["ff_url"], timeout=60)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    csv_name = next(n for n in zf.namelist() if n.endswith(".CSV") or n.endswith(".csv"))
    raw_text = zf.read(csv_name).decode("latin-1")

    lines = raw_text.splitlines()
    # Find header row: contains "Mkt-RF" token
    header_idx = next(i for i, line in enumerate(lines) if "Mkt-RF" in line)
    # Monthly section ends at the first blank line after header
    end_idx = len(lines)
    for i in range(header_idx + 1, len(lines)):
        if not lines[i].strip():
            end_idx = i
            break

    block = "\n".join(lines[header_idx:end_idx])
    df = pd.read_csv(io.StringIO(block))
    df = df.rename(columns={df.columns[0]: "date"})
    df = df.dropna(subset=["date"])
    df = df[df["date"].astype(str).str.match(r"^\d{6}$")]
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)

    for col in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]:
        df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0

    df = df[(df["date"] >= pd.Timestamp(cfg["start_date"])) & (df["date"] <= pd.Timestamp(cfg["end_date"]))]
    df = df[["date", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]].reset_index(drop=True)

    out = FF5_DIR / "ff5_monthly.csv"
    df.to_csv(out, index=False)
    log.info("ff5: %d rows -> %s", len(df), out)


if __name__ == "__main__":
    main()
