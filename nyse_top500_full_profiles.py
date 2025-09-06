#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NYSE Top 500 by Revenue — Full Company Profiles (FMP)
-----------------------------------------------------
- Get all NYSE symbols (stable/stock-list)
- Fetch latest ANNUAL revenue per symbol (stable/income-statement)
- Rank and keep top 500 (configurable with --limit)
- Fetch full profiles (stable/profile) for those symbols
- Save ALL profile fields to CSV (no column filtering) + include 'revenue' used for ranking

Usage:
  pip install pandas requests
  export FMP_API_KEY="YOUR_FMP_KEY"   # falls back to DEFAULT_API_KEY below if unset
  python nyse_top500_full_profiles.py --csv nyse_top500_profiles.csv --limit 500 --workers 8
"""
from __future__ import annotations

import os
import sys
import time
import json
import random
import argparse
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

# ---------- Config ----------
DEFAULT_API_KEY = "jFShbRJmQFEFneU6mL4rgQpkMat8DbRW"  # used if FMP_API_KEY env var not set
BASE = "https://financialmodelingprep.com"

ENDPOINT_STOCK_LIST = f"{BASE}/stable/stock-list"
ENDPOINT_INCOME     = f"{BASE}/stable/income-statement"
ENDPOINT_PROFILE    = f"{BASE}/stable/profile"

# ---------- Helpers ----------
def api_key() -> str:
    return os.getenv("FMP_API_KEY", DEFAULT_API_KEY).strip()

def backoff(attempt: int, cap: float = 20.0) -> None:
    """Exponential backoff with jitter (polite throttling)."""
    delay = min(cap, (1.6 ** attempt)) + random.uniform(0, 0.5)
    time.sleep(delay)

def get_json(url: str, params: Dict[str, Any], max_retries: int = 6) -> Any:
    """GET JSON with retries for 429/5xx/403 & JSON decode errors."""
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code in (429, 500, 502, 503, 504, 403):
                backoff(attempt)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_err = e
            backoff(attempt)
    raise RuntimeError(f"Failed GET {url} after retries: {last_err}")

def get_nyse_symbols(key: str) -> List[str]:
    """Retrieve all symbols and filter to NYSE."""
    js = get_json(ENDPOINT_STOCK_LIST, {"apikey": key})
    df = pd.DataFrame(js)
    # Prefer 'exchangeShortName', fallback to 'exchange'
    for col in ("exchangeShortName", "exchange"):
        if col in df.columns:
            mask = df[col].astype(str).str.upper().str.contains("NYSE", na=False)
            syms = df.loc[mask, "symbol"].astype(str).str.upper().dropna().unique().tolist()
            return syms
    # Fallback: return all symbols (edge case)
    return df["symbol"].astype(str).str.upper().dropna().unique().tolist()

def fetch_latest_annual_revenue(symbol: str, key: str) -> Tuple[str, Optional[float]]:
    """Return (symbol, latest annual revenue or None)."""
    try:
        js = get_json(ENDPOINT_INCOME, {"symbol": symbol, "period": "annual", "limit": 1, "apikey": key})
        if isinstance(js, list) and js:
            rev = js[0].get("revenue", None)
            try:
                return symbol, float(rev) if rev is not None else None
            except (TypeError, ValueError):
                return symbol, None
    except Exception:
        return symbol, None
    return symbol, None

def collect_revenues(symbols: List[str], key: str, workers: int = 8, stagger: float = 0.07) -> pd.DataFrame:
    """Concurrent revenue collection with gentle staggering to avoid bursts."""
    rows: List[Tuple[str, Optional[float]]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = []
        for i, sym in enumerate(symbols):
            if stagger and i > 0:
                time.sleep(stagger)
            futs.append(ex.submit(fetch_latest_annual_revenue, sym, key))
        for fut in as_completed(futs):
            rows.append(fut.result())
    return pd.DataFrame(rows, columns=["symbol", "revenue"])

def fetch_profiles_batched(symbols: List[str], key: str, chunk: int = 50) -> List[Dict[str, Any]]:
    """
    Try batched requests with comma-separated symbols (common FMP pattern).
    If a batch fails, fallback to single-symbol calls for that chunk.
    """
    all_rows: List[Dict[str, Any]] = []
    for i in range(0, len(symbols), chunk):
        batch = symbols[i:i+chunk]
        joined = ",".join(batch)
        params = {"symbol": joined, "apikey": key}
        try:
            js = get_json(ENDPOINT_PROFILE, params)
            # Normalize: list for multi, dict for single
            if isinstance(js, dict):
                js = [js]
            if isinstance(js, list):
                all_rows.extend(js)
            else:
                all_rows.extend(fetch_profiles_one_by_one(batch, key))
        except Exception:
            all_rows.extend(fetch_profiles_one_by_one(batch, key))
        time.sleep(0.2)  # polite pacing
    return all_rows

def fetch_profiles_one_by_one(symbols: List[str], key: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sym in symbols:
        try:
            js = get_json(ENDPOINT_PROFILE, {"symbol": sym, "apikey": key})
            if isinstance(js, list):
                rows.extend(js)
            elif isinstance(js, dict):
                rows.append(js)
        except Exception:
            pass
        time.sleep(0.1)
    return rows

def build_top_profiles_by_revenue(limit: int, csv_path: str, workers: int) -> pd.DataFrame:
    key = api_key()

    # 1) Universe: NYSE tickers
    print("Fetching NYSE symbol list...")
    syms = get_nyse_symbols(key)
    print(f"NYSE symbols found: {len(syms)}")

    # 2) Revenue for each (latest annual)
    print("Fetching latest annual revenue for each symbol (polite concurrency)...")
    rev_df = collect_revenues(syms, key, workers=workers)
    rev_df = rev_df.dropna(subset=["revenue"]).sort_values("revenue", ascending=False, kind="mergesort")
    rev_df = rev_df.reset_index(drop=True)

    # 3) Select top N by revenue
    top_df = rev_df.head(int(limit)).copy()
    top_syms = top_df["symbol"].tolist()
    print(f"Top {len(top_syms)} symbols selected by revenue.")

    # 4) Fetch profiles for top symbols
    print("Fetching FULL company profiles for top symbols...")
    prof_js = fetch_profiles_batched(top_syms, key, chunk=50)
    prof_df = pd.DataFrame(prof_js)

    # 5) Normalize join key & merge revenue
    if "symbol" in prof_df.columns:
        prof_df["symbol"] = prof_df["symbol"].astype(str).str.upper()
    else:
        prof_df["symbol"] = pd.NA

    merged = top_df.merge(prof_df, on="symbol", how="left")

    # 6) Save ALL fields to CSV (no column filtering)
    merged.to_csv(csv_path, index=False)
    print(f"Saved CSV -> {csv_path}  (rows: {len(merged)})")
    return merged

# ---------- CLI ----------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a CSV of FULL FMP profiles for top NYSE companies ranked by latest annual revenue.")
    parser.add_argument("--csv", type=str, default="nyse_top500_profiles.csv", help="Output CSV path")
    parser.add_argument("--limit", type=int, default=500, help="How many top-by-revenue companies to keep (default 500)")
    parser.add_argument("--workers", type=int, default=8, help="Max concurrent revenue requests (default 8)")
    args = parser.parse_args(argv)

    try:
        df = build_top_profiles_by_revenue(limit=args.limit, csv_path=args.csv, workers=args.workers)
        print("Preview columns:", list(df.columns)[:20], "...")
        print(df.head(10).to_string(index=False))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
