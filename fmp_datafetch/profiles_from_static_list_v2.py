#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch FULL company profiles from a STATIC list of symbols (FMP) — resilient v2
------------------------------------------------------------------------------
- Uses FMP stable endpoint: /stable/profile
- First tries comma-batched requests; if zero rows, auto-falls back to per-symbol.
- Per-symbol mode retries with exponential backoff and tries symbol variants:
    BRK.B <-> BRK-B (both are attempted).
- Saves ALL fields returned by the endpoint to CSV (no column filtering).

Usage:
  pip install pandas requests
  export FMP_API_KEY="YOUR_KEY"
  python profiles_from_static_list_v2.py --csv nyse_top500_profiles.csv \
      --symbols-file top500_symbols.txt --batch 40 --workers 6
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

API_BASE = "https://financialmodelingprep.com"
EP_PROFILE = f"{API_BASE}/stable/profile"

# --------------------------------------------------------------------
# Replace/extend this list to your full 500 if not using --symbols-file
# --------------------------------------------------------------------
DEFAULT_SYMBOLS = [
    "AAPL","MSFT","AMZN","BRK.B","NVDA","GOOGL","GOOG","META","LLY","JPM",
    "XOM","V","UNH","WMT","JNJ","PG","MA","HD","AVGO","CVX",
    "MRK","ABBV","KO","PEP","BAC","COST","ADBE","TMO","NFLX","WFC",
    "CSCO","ACN","CRM","ORCL","LIN","MCD","AMD","INTC","TXN","VZ",
    "T","AMAT","PM","IBM","GS","CAT","HON","GE","BKNG","SPGI",
    "RTX","QCOM","LOW","DE","AXP","CVS","SCHW","NOW","PFE","MS",
    "UPS","BA","ELV","PLD","UNP","INTU","AMT","NEE","BLK","AMGN",
    "MU","MDT","COP","C","DELL","LMT","ADP","MDLZ","TJX","ISRG",
    "SYK","PAYX","CB","DHR","PNC","GILD","BDX","MMC","CL","HCA",
    "TGT","SO","DUK","EL","GM","F","NKE","SHW","CMCSA","SPY"  # add/replace until you hit 500
]

DEFAULT_API_KEY = os.getenv("FMP_API_KEY", "jFShbRJmQFEFneU6mL4rgQpkMat8DbRW").strip()

# -------------------- Utilities -------------------- #

def backoff(attempt: int, cap: float = 20.0) -> None:
    """Exponential backoff with jitter."""
    delay = min(cap, (1.6 ** attempt)) + random.uniform(0, 0.6)
    time.sleep(delay)

def get_json(url: str, params: Dict[str, Any], max_retries: int = 6) -> Any:
    """GET JSON with retries for 429/5xx/403/402 & JSON decode errors."""
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, params=params, timeout=40)
            if r.status_code in (429, 500, 502, 503, 504, 403, 402):
                backoff(attempt)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_err = e
            backoff(attempt)
    # Let caller decide how to handle; return empty sentinel
    return {"__error__": str(last_err) if last_err else "unknown_error"}

def load_symbols(symbols_file: Optional[str]) -> List[str]:
    if symbols_file and os.path.isfile(symbols_file):
        txt = open(symbols_file, "r", encoding="utf-8").read()
        parts = [p.strip().upper() for p in txt.replace("\n", ",").split(",")]
        syms = [p for p in parts if p]
        # de-dup, preserve order
        return list(dict.fromkeys(syms))
    return list(dict.fromkeys([s.upper() for s in DEFAULT_SYMBOLS if s.strip()]))

# -------------------- Fetchers -------------------- #

def fetch_profiles_batched(symbols: List[str], api_key: str, batch: int = 40, pause: float = 0.25) -> pd.DataFrame:
    """Try batched calls: /stable/profile?symbol=SYM1,SYM2,..."""
    frames: List[pd.DataFrame] = []
    for i in range(0, len(symbols), batch):
        chunk = symbols[i:i+batch]
        joined = ",".join(chunk)
        js = get_json(EP_PROFILE, {"symbol": joined, "apikey": api_key})
        if isinstance(js, dict) and "__error__" in js:
            # On hard errors keep going; we'll fallback later if needed
            js = []
        if isinstance(js, dict):
            js = [js]
        if isinstance(js, list) and js:
            df = pd.DataFrame(js)
            if "symbol" in df.columns:
                df["symbol"] = df["symbol"].astype(str).str.upper()
            frames.append(df)
        time.sleep(pause)  # polite pacing
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

def symbol_variants(sym: str) -> List[str]:
    """Try dot/hyphen class variants; e.g., BRK.B <-> BRK-B."""
    s = sym.upper().strip()
    cand = [s]
    if "." in s:
        cand.append(s.replace(".", "-"))
    if "-" in s:
        cand.append(s.replace("-", "."))
    # de-dup preserve order
    return list(dict.fromkeys(cand))

def fetch_profile_single(sym: str, api_key: str, max_retries: int = 6) -> List[Dict[str, Any]]:
    """Per-symbol fetch with retries + variant attempts. Returns list of profile rows (or empty)."""
    for variant in symbol_variants(sym):
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                js = get_json(EP_PROFILE, {"symbol": variant, "apikey": api_key})
                if isinstance(js, dict) and "__error__" in js:
                    last_err = js["__error__"]
                    backoff(attempt)
                    continue
                if isinstance(js, dict) and js:
                    js["symbol_queried"] = variant
                    js["symbol_original"] = sym
                    return [js]
                if isinstance(js, list) and js:
                    # annotate first row with original symbol for traceability
                    for row in js:
                        row["symbol_queried"] = variant
                        row["symbol_original"] = sym
                    return js
                # empty list/dict -> try next attempt or next variant
                backoff(attempt)
            except Exception as e:
                last_err = str(e)
                backoff(attempt)
        # exhausted this variant; try next variant
    # nothing worked
    return []

def fetch_profiles_per_symbol(symbols: List[str], api_key: str, workers: int = 6, stagger: float = 0.07) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    def _task(s: str) -> List[Dict[str, Any]]:
        return fetch_profile_single(s, api_key)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = []
        for i, sym in enumerate(symbols):
            if i and stagger:
                time.sleep(stagger)
            futs.append(ex.submit(_task, sym))
        for idx, fut in enumerate(as_completed(futs), 1):
            try:
                got = fut.result()
                if got:
                    rows.extend(got)
            except Exception:
                pass

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper()
    return df

# -------------------- Main -------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch full FMP profiles from a static symbols list, with auto-fallback to per-symbol mode.")
    ap.add_argument("--csv", type=str, default="profiles_static.csv", help="Output CSV path")
    ap.add_argument("--symbols-file", type=str, default="", help="Path to symbols file (newline or comma separated)")
    ap.add_argument("--batch", type=int, default=40, help="Batch size for initial multi-symbol calls (default 40)")
    ap.add_argument("--workers", type=int, default=6, help="Workers for per-symbol fallback (default 6)")
    ap.add_argument("--apikey", type=str, default=DEFAULT_API_KEY, help="FMP API key")
    args = ap.parse_args()

    symbols = load_symbols(args.symbols_file)
    if not symbols:
        print("ERROR: No symbols to fetch. Provide --symbols-file or extend DEFAULT_SYMBOLS.", file=sys.stderr)
        return 2

    print(f"Symbols to fetch: {len(symbols)}")

    # 1) Try batched first (fast path)
    df = fetch_profiles_batched(symbols, api_key=args.apikey, batch=args.batch)
    if df.empty:
        print("Batched call returned no rows. Falling back to per-symbol mode...")
        df = fetch_profiles_per_symbol(symbols, api_key=args.apikey, workers=args.workers)
        if df.empty:
            print("ERROR: Per-symbol mode also returned no rows. Check your key/plan.", file=sys.stderr)
            return 1

    # Save ALL columns as returned by FMP
    df.to_csv(args.csv, index=False)
    print(f"Saved CSV -> {args.csv} (rows: {len(df)})")

    # Quick glance
    show_cols = [c for c in ["symbol","companyName","exchange","exchangeFullName","sector","industry","marketCap","price"] if c in df.columns]
    if show_cols:
        print(df[show_cols].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
