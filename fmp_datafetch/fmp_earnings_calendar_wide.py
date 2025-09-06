#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FMP Earnings Calendar — Wide Coverage (Next 2–3 Months)
------------------------------------------------------
- Uses Financial Modeling Prep "stable/earnings-calendar" endpoint.
- Expands coverage by splitting the window into weekly chunks and merging.
- Captures key fields: symbol, date, time, eps, epsEstimated, revenue, revenueEstimated.
- Robust retry with exponential backoff + jitter for 429/5xx/403.
- Deduplicates by (symbol, date).
- Saves to CSV when --csv is provided.

Usage:
    export FMP_API_KEY="your_key_here"
    python fmp_earnings_calendar_wide.py --months 3 --csv earnings_next3m.csv

Requirements:
    pip install pandas requests
"""
from __future__ import annotations

import os
import sys
import time
import json
import random
import argparse
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import requests

BASE_URL = "https://financialmodelingprep.com/stable/earnings-calendar"


# ------------------ helpers ------------------ #

def _iso(d: date) -> str:
    return d.isoformat()

def _daterange_week_slices(start: date, end: date, step_days: int = 7) -> List[Tuple[date, date]]:
    """Generate [start, min(start+step, end)] slices; inclusive behavior compatible with FMP."""
    slices: List[Tuple[date, date]] = []
    cur = start
    while cur <= end:
        nxt = cur + timedelta(days=step_days)
        chunk_end = min(end, nxt)
        slices.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return slices

def _sleep_backoff(attempt: int) -> None:
    """Exponential backoff with jitter (polite throttling)."""
    base = 1.6
    cap = 20.0
    delay = min(cap, (base ** attempt)) + random.uniform(0, 0.7)
    time.sleep(delay)

def _fetch_chunk(api_key: str, d_from: date, d_to: date, max_retries: int = 7) -> List[Dict[str, Any]]:
    params = {"from": _iso(d_from), "to": _iso(d_to), "apikey": api_key}
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(BASE_URL, params=params, timeout=30)
            # Retry on common transient errors or throttle
            if r.status_code in (429, 500, 502, 503, 504, 403):
                _sleep_backoff(attempt)
                continue
            r.raise_for_status()
            js = r.json()
            # If API returns an error payload as JSON
            if isinstance(js, dict) and any(k in js for k in ("Error", "Error Message", "message")):
                last_err = RuntimeError(json.dumps(js))
                _sleep_backoff(attempt)
                continue
            if not isinstance(js, list):
                return []
            return js
        except requests.RequestException as e:
            last_err = e
            _sleep_backoff(attempt)
        except json.JSONDecodeError as e:
            last_err = e
            _sleep_backoff(attempt)
    sys.stderr.write(f"WARN: failed slice {d_from}..{d_to} after retries: {last_err}\n")
    return []

def collect_earnings(api_key: str, months: int = 3, week_step: int = 7) -> pd.DataFrame:
    """Collect upcoming earnings over the next `months` (1–3)."""
    months = max(1, min(3, int(months)))
    today = datetime.utcnow().date()
    # 30 * months is a simple approximation for 2–3 months windows
    end = today + timedelta(days=30 * months)
    slices = _daterange_week_slices(today, end, week_step)

    frames: List[pd.DataFrame] = []
    for idx, (d_from, d_to) in enumerate(slices, 1):
        chunk = _fetch_chunk(api_key, d_from, d_to)
        if not chunk:
            # small, polite pause even when empty
            time.sleep(0.25)
            continue

        df = pd.DataFrame(chunk)

        # Ensure expected columns exist even if missing in some rows
        for col in ["symbol", "date", "time", "eps", "epsEstimated", "revenue", "revenueEstimated"]:
            if col not in df.columns:
                df[col] = pd.NA

        df = df[["symbol", "date", "time", "eps", "epsEstimated", "revenue", "revenueEstimated"]]
        frames.append(df)

        # polite pacing between chunks
        time.sleep(0.25)

    if not frames:
        return pd.DataFrame(columns=["symbol", "date", "time", "eps", "epsEstimated", "revenue", "revenueEstimated"])

    out = pd.concat(frames, ignore_index=True)
    # Parse/clean
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date
    # Deduplicate by (symbol, date)
    out.drop_duplicates(subset=["symbol", "date"], keep="first", inplace=True, ignore_index=True)
    # Sort
    out.sort_values(["date", "symbol"], inplace=True, kind="mergesort")
    out.reset_index(drop=True, inplace=True)
    return out


# ------------------ CLI ------------------ #

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch wide-coverage earnings calendar from FMP for next 2–3 months.")
    parser.add_argument("--months", type=int, default=3, help="Months ahead (1-3). Default 3.")
    parser.add_argument("--csv", type=str, default="", help="CSV output path (e.g., earnings_next3m.csv).")
    args = parser.parse_args(argv)

    api_key = os.getenv("FMP_API_KEY", "").strip()
    if not api_key:
        print("ERROR: Please set FMP_API_KEY environment variable.", file=sys.stderr)
        return 2

    df = collect_earnings(api_key=api_key, months=args.months)
    print(f"Rows: {len(df)} in next {args.months} month(s).")
    if not df.empty:
        print(df.head(15).to_string(index=False))
    else:
        print("No rows returned. Consider widening the window or retrying later.")

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"\nSaved CSV -> {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
