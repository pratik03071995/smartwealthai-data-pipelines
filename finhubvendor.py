#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Company filings & vendor extraction pipeline

Outputs per symbol:
  - {sym}_insider_filings.csv          # Forms 3/4/5 (Finnhub)
  - {sym}_form4_trades.csv             # Parsed trade rows from Form 4 XML
  - {sym}_ownership_filings.csv        # 13D/13G/13F/144 (Finnhub)
  - {sym}_vendor_hits.csv              # Which 10-K/8-K had vendor keywords
  - {sym}_vendor_contexts.csv          # Context windows around the hits
  - {sym}_vendor_counterparties.csv    # First-pass extracted counterparty org names

Usage:
  FINNHUB_API_KEY=... python vendor_pipeline.py --symbols NVDA ORCL --days 365
"""

import os
import re
import time
import random
import argparse
import datetime
import requests
import pandas as pd
from urllib.parse import urlencode, urljoin
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# ==== CONFIG ====
FINNHUB_KEY = os.getenv("d32b54pr01qn0gi37ek0d32b54pr01qn0gi37ekg", "")
if not FINNHUB_KEY:
    print("WARNING: FINNHUB_API_KEY not set; set it in your environment.")

from dotenv import load_dotenv
load_dotenv()

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "SmartWealthAI SmartWealthAI smartwealthai15@gmail.com")
SEC_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


FINNHUB_BASE = "https://finnhub.io/api/v1/stock/filings"

# The SEC requires a descriptive User-Agent with contact info (your name/company/email)
SEC_HEADERS = {
    "User-Agent": "Your Name Your Company your.email@domain.com",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Keyword set (tune freely)
VENDOR_KEYWORDS = [
    # core
    "supplier", "suppliers", "vendor", "vendors", "customer", "customers",
    "supply agreement", "master supply", "manufacturing agreement",
    "exclusive supply", "sole-source", "sole source", "reseller",
    "distribution agreement", "cloud agreement", "procurement",
    "contract manufacturer", "foundry", "fab", "fabrication",
    # broaden
    "manufactur", "fabricat", "contract", "oem", "odm", "distributor",
    "partnership", "strategic alliance", "memorandum of understanding", "mou",
    "purchase commitment", "supply commitment",
]

# Simple organization “suffix” list to help the org extractor
ORG_SUFFIXES = r"(inc\.?|corp\.?|corporation|ltd\.?|llc|llp|plc|co\.?|company|gmbh|nv|sa|sas|spa|ab|oy|bv|pte\.?|kk|ag)"
# =================


# ---------- Finnhub helpers ----------
def fh(params):
    q = dict(params)
    q["token"] = FINNHUB_KEY
    url = f"{FINNHUB_BASE}?{urlencode(q)}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def list_filings(symbol, form=None, days=365):
    to = datetime.date.today()
    frm = to - datetime.timedelta(days=days)
    params = {"symbol": symbol, "from": str(frm), "to": str(to)}
    if form:
        params["form"] = form
    return fh(params)


def insider_filings(symbol, days=60):
    data = []
    for f in ["3", "4", "5", "3/A", "4/A", "5/A"]:
        data += list_filings(symbol, form=f, days=days)
    return sorted(data, key=lambda x: x.get("filedDate", ""), reverse=True)


def ownership_filings(symbol, days=180):
    data = []
    for f in ["13D", "13D/A", "13G", "13G/A", "13F-HR", "13F-HR/A", "144"]:
        data += list_filings(symbol, form=f, days=days)
    return sorted(data, key=lambda x: x.get("filedDate", ""), reverse=True)


# ---------- SEC fetch helpers ----------
def _get(url, headers=None, timeout=30, tries=3, sleep=1.0):
    last_exc = None
    for _ in range(tries):
        try:
            resp = requests.get(url, headers=headers or SEC_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                return resp
        except Exception as e:
            last_exc = e
        time.sleep(sleep + random.random() * 0.5)
    if last_exc:
        raise last_exc
    return None


def get_primary_doc_url_from_index(index_url: str) -> str | None:
    """
    From an SEC index page (...-index.html), pick a best candidate primary .htm/.html document.
    Fallback to the full submission .txt.
    """
    try:
        resp = _get(index_url)
        if not resp or not resp.text:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        candidates = []
        for a in soup.select("a"):
            href = a.get("href", "")
            text = (a.get_text() or "").lower()
            if href.lower().endswith((".htm", ".html")):
                score = 0
                if "10-k" in text or "form 10-k" in text or "8-k" in text or "form 8-k" in text:
                    score += 10
                score += len(text)
                candidates.append((score, urljoin(index_url, href)))

        if candidates:
            candidates.sort(reverse=True, key=lambda x: x[0])
            return candidates[0][1]

        if index_url.endswith("-index.html"):
            return index_url.replace("-index.html", ".txt")
    except Exception:
        pass
    return None


def fetch_filing_text_any(url: str) -> tuple[str, str]:
    """
    Fetch textual content for either:
      - a direct .htm/.html/.txt doc, or
      - an index page that we resolve to the primary doc.

    Returns: (raw_text_with_case, lowered_text)
    """
    final_url = url
    if final_url.endswith("-index.html"):
        primary = get_primary_doc_url_from_index(final_url)
        if primary:
            final_url = primary

    resp = _get(final_url)
    if not resp or not resp.text:
        return "", ""

    content_type = resp.headers.get("Content-Type", "").lower()
    text = resp.text

    if "html" in content_type or final_url.endswith((".htm", ".html")):
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")

    text = re.sub(r"\s+", " ", text)
    return text, text.lower()


# ---------- Vendor extraction ----------
def vendor_hits_for(symbol: str, days: int = 365) -> list[dict]:
    hits = []
    forms = ["8-K", "8-K/A", "10-K", "10-K/A"]

    for form in forms:
        filings = list_filings(symbol, form=form, days=days)
        for f in filings:
            # Prefer index page if provided
            url = f.get("filingUrl") or f.get("reportUrl") or f.get("url") or ""
            if not url:
                continue
            try:
                raw, low = fetch_filing_text_any(url)
            except Exception:
                raw, low = "", ""
            if not low:
                continue

            found = sorted({kw for kw in VENDOR_KEYWORDS if kw in low})
            if found:
                hits.append({
                    "symbol": symbol,
                    "form": f.get("form"),
                    "filedDate": f.get("filedDate"),
                    "accessionNumber": f.get("accessionNumber") or f.get("accessNumber"),
                    "indexUrl": f.get("filingUrl") or url,
                    "keywords_found": found[:25]
                })
    return hits


def extract_contexts(raw_text: str, low_text: str, keywords: list[str], window: int = 160):
    rows = []
    for kw in keywords:
        start = 0
        while True:
            idx = low_text.find(kw, start)
            if idx == -1:
                break
            s = max(0, idx - window)
            e = min(len(low_text), idx + len(kw) + window)
            # map to raw text (same indices because we only lowercased)
            snippet = raw_text[s:e]
            rows.append((kw, s, e, snippet))
            start = idx + len(kw)
    return rows


ORG_CAND_RE = re.compile(
    # capture capitalized word sequences + optional org suffix
    r"([A-Z][A-Za-z0-9&\-\.\']+(?:\s+[A-Z][A-Za-z0-9&\-\.\']+){0,6}\s+(?:"
    + ORG_SUFFIXES +
    r"))"
)


def guess_counterparties_from_snippet(snippet: str) -> list[str]:
    """
    Very rough heuristic: find capitalized sequences ending with an org suffix.
    """
    # Clean odd punctuation spacing
    snip = re.sub(r"\s+", " ", snippet)
    # Try to avoid matching the issuer name repeated constantly (handled later by filter)
    cands = [m.group(1).strip() for m in ORG_CAND_RE.finditer(snip)]
    # Deduplicate while preserving order
    seen, uniq = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq[:8]


def build_vendor_contexts(symbol: str, days: int = 365) -> pd.DataFrame:
    rows = []
    for hit in vendor_hits_for(symbol, days=days):
        raw, low = fetch_filing_text_any(hit["indexUrl"])
        if not raw:
            continue
        for kw, s, e, snippet in extract_contexts(raw, low, hit["keywords_found"], window=180):
            rows.append({
                "symbol": hit["symbol"],
                "form": hit["form"],
                "filedDate": hit["filedDate"],
                "accessionNumber": hit["accessionNumber"],
                "keyword": kw,
                "context": re.sub(r"\s+", " ", snippet.strip()),
                "indexUrl": hit["indexUrl"],
            })
    return pd.DataFrame(rows)


def extract_counterparties(df_contexts: pd.DataFrame, issuer_name: str = "") -> pd.DataFrame:
    """
    From context windows, guess organization names and attempt a relationship guess
    based on nearby words.
    """
    if df_contexts.empty:
        return pd.DataFrame(columns=[
            "symbol", "counterparty", "relationship_guess", "form", "filedDate", "accessionNumber", "indexUrl", "context"
        ])

    out = []
    for _, r in df_contexts.iterrows():
        context = r["context"]
        orgs = guess_counterparties_from_snippet(context)

        # crude relationship guess
        rel = ""
        ctx_low = context.lower()
        if "supplier" in ctx_low or "supply agreement" in ctx_low or "contract manufacturer" in ctx_low or "foundry" in ctx_low:
            rel = "supplier"
        elif "vendor" in ctx_low or "procurement" in ctx_low:
            rel = "vendor"
        elif "reseller" in ctx_low or "distribution" in ctx_low or "distributor" in ctx_low:
            rel = "reseller/distributor"
        elif "customer" in ctx_low:
            rel = "customer"
        elif "cloud agreement" in ctx_low or "strategic alliance" in ctx_low or "partnership" in ctx_low or "mou" in ctx_low:
            rel = "partner"

        for org in orgs:
            # Filter out the issuer name if passed
            if issuer_name and issuer_name.lower() in org.lower():
                continue
            out.append({
                "symbol": r["symbol"],
                "counterparty": org,
                "relationship_guess": rel or "unsure",
                "form": r["form"],
                "filedDate": r["filedDate"],
                "accessionNumber": r["accessionNumber"],
                "indexUrl": r["indexUrl"],
                "context": r["context"],
            })

    df = pd.DataFrame(out)
    if df.empty:
        return df

    # De-dup
    df = df.drop_duplicates(subset=["symbol", "counterparty", "form", "filedDate", "accessionNumber"])
    return df


# ---------- Form 4 XML parsing ----------
def parse_form4_xml(url: str) -> list[dict]:
    """
    Return a list of trade rows (non-derivative) from an xslF345 XML.
    """
    try:
        resp = _get(url)
        if not resp:
            return []
        root = ET.fromstring(resp.content)
    except Exception:
        return []

    def gx(path):
        el = root.find(path)
        return el.text if el is not None else None

    insider_name = gx(".//rptOwnerName")
    relation = gx(".//rptOwnerRelationship/relationshipTitle")

    trades = []
    for t in root.findall(".//nonDerivativeTransaction"):
        date = (t.findtext(".//transactionDate/value") or "").strip()
        code = (t.findtext(".//transactionCoding/transactionCode") or "").strip()
        shares = (t.findtext(".//transactionShares/value") or "").strip()
        price = (t.findtext(".//transactionPricePerShare/value") or "").strip()
        shares_after = (t.findtext(".//sharesOwnedFollowingTransaction/value") or "").strip()
        direct_indirect = (t.findtext(".//directOrIndirectOwnership/value") or "").strip()

        trades.append({
            "insider_name": insider_name,
            "relation": relation,
            "transaction_date": date,
            "transaction_code": code,         # e.g., P (purchase), S (sale), A (grant), M (option exercise)
            "shares": shares,
            "price": price,
            "shares_after": shares_after,
            "ownership_form": direct_indirect,
            "form4_url": url,
        })
    return trades


def collect_form4_trades_from_filings(filings: list[dict]) -> pd.DataFrame:
    """
    For a Finnhub filings list, find Form 4 items and parse their XML reportUrl.
    """
    rows = []
    for f in filings:
        if (f.get("form") or "").startswith("4"):
            xml_url = f.get("reportUrl") or ""
            if xml_url and xml_url.lower().endswith(".xml"):
                rows += parse_form4_xml(xml_url)
    return pd.DataFrame(rows)


# ---------- CSV writers ----------
def write_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)
    print(f"✔ Saved: {path}  ({df.shape[0]} rows)")


# ---------- Main ----------
def run_for_symbol(symbol: str, days: int):
    print(f"\n=== {symbol}: collecting filings ===")

    # 1) Insider filings (3/4/5)
    insiders = insider_filings(symbol, days=min(90, days))
    df_insiders = pd.DataFrame(insiders)
    write_csv(df_insiders, f"{symbol}_insider_filings.csv")

    # 1b) Parse Form 4 XML → trade rows
    df_form4_trades = collect_form4_trades_from_filings(insiders)
    write_csv(df_form4_trades, f"{symbol}_form4_trades.csv")

    # 2) Ownership (13D/G, 13F, 144)
    owners = ownership_filings(symbol, days=days)
    df_owners = pd.DataFrame(owners)
    write_csv(df_owners, f"{symbol}_ownership_filings.csv")

    # 3) Vendor/supplier signals in 10-K / 8-K (+ amendments)
    hits = vendor_hits_for(symbol, days=days)
    df_hits = pd.DataFrame(hits)
    write_csv(df_hits, f"{symbol}_vendor_hits.csv")

    # 4) Context windows for each keyword hit
    df_ctx = build_vendor_contexts(symbol, days=days)
    write_csv(df_ctx, f"{symbol}_vendor_contexts.csv")

    # 5) First-pass extraction of counterparties from contexts
    #    Optional: pass issuer/brand name to filter out self-matches; leave blank if unsure
    df_ctp = extract_counterparties(df_ctx, issuer_name="")
    write_csv(df_ctp, f"{symbol}_vendor_counterparties.csv")

    print(f"=== DONE: {symbol} ===")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols (e.g., NVDA ORCL)")
    ap.add_argument("--days", type=int, default=365, help="Lookback window in days (default 365)")
    args = ap.parse_args()

    for sym in args.symbols:
        try:
            run_for_symbol(sym.upper(), days=args.days)
        except Exception as e:
            print(f"[ERROR] {sym}: {e}")


if __name__ == "__main__":
    main()
