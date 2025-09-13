#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Filings & Vendor/Partner Extractor

Outputs per symbol:
  - {sym}_insider_filings.csv
  - {sym}_form4_trades.csv
  - {sym}_ownership_filings.csv
  - {sym}_vendor_hits.csv
  - {sym}_vendor_contexts.csv
  - {sym}_vendor_counterparties.csv
  - {sym}_8k_items.csv               # extracted Items (1.01, 2.02, 7.01, 8.01 by default)
  - {sym}_8k_items_hits.csv          # those Items filtered by agreement/partner keywords

Usage examples:
  FINNHUB_API_KEY=YOUR_KEY \
  python finhub_vendor_multi.py --symbols NVDA ORCL --days 365 \
    --sec-user-agent "Your Name YourCo your@email.com" \
    --items "1.01,2.02,7.01,8.01"

  # If you have no Finnhub key, the SEC parts still run:
  python finhub_vendor_multi.py --symbols NVDA --days 365 --sec-user-agent "..." --items "1.01,7.01,8.01"
"""

import os
import re
import time
import random
import argparse
import datetime
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, urljoin
from bs4 import BeautifulSoup

# ---------- Optional: load .env ----------
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Config ----------
FINNHUB_KEY  = os.getenv("FINNHUB_API_KEY", "")
FINNHUB_BASE = "https://finnhub.io/api/v1/stock/filings"

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "SmartWealthAI SmartWealthAI smartwealthai15@gmail.com")
SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

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

# Guess orgs by capitalized phrases with common suffixes
ORG_SUFFIXES = r"(inc\.?|corp\.?|corporation|ltd\.?|llc|llp|plc|co\.?|company|gmbh|nv|sa|sas|spa|ab|oy|bv|pte\.?|kk|ag)"
ORG_CAND_RE = re.compile(
    r"([A-Z][A-Za-z0-9&\-\.\']+(?:\s+[A-Z][A-Za-z0-9&\-\.\']+){0,6}\s+(?:" + ORG_SUFFIXES + r"))"
)

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

def insider_filings(symbol, days=90):
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
        time.sleep(sleep + random.random()*0.5)
    if last_exc:
        raise last_exc
    return None

def get_primary_doc_url_from_index(index_url: str) -> str | None:
    """
    From an SEC index (...-index.html), return the actual 8-K/8-K/A body (.htm),
    not the exhibits. If not found, fallback to first .htm/.html, then full .txt.
    """
    try:
        resp = _get(index_url)
        if not resp or not resp.text:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        # The filing index has a table with columns: Seq | Description | Document | Type | Size
        # We'll walk table rows and find the row where Type is exactly 8-K or 8-K/A
        best = None

        # 1) Prefer the row with type 8-K / 8-K/A
        for tr in soup.select("table tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            doc_link = tds[2].find("a") or tds[1].find("a")  # SEC layouts vary
            doc_type = (tds[3].get_text(strip=True) if len(tds) > 3 else "").upper()
            if doc_link and doc_type in {"8-K", "8-K/A"}:
                href = doc_link.get("href", "")
                if href.lower().endswith((".htm", ".html")):
                    best = urljoin(index_url, href)
                    break

        if best:
            return best

        # 2) Otherwise, choose the first .htm/.html whose text hints "form 8-k"
        candidates = []
        for a in soup.select("a"):
            href = a.get("href", "")
            text = (a.get_text() or "").lower()
            if href.lower().endswith((".htm", ".html")):
                score = 0
                if "8-k" in text or "form 8-k" in text:
                    score += 10
                score += len(text)
                candidates.append((score, urljoin(index_url, href)))
        if candidates:
            candidates.sort(reverse=True, key=lambda x: x[0])
            return candidates[0][1]

        # 3) Last resort: full submission text
        if index_url.endswith("-index.html"):
            return index_url.replace("-index.html", ".txt")
    except Exception:
        pass
    return None


def fetch_filing_text_any(url: str) -> tuple[str, str, str]:
    """
    Accepts an index URL or direct .htm/.html/.txt; returns (final_url, raw_text, lowered).
    """
    final_url = url
    if final_url.endswith("-index.html"):
        primary = get_primary_doc_url_from_index(final_url)
        if primary:
            final_url = primary
    resp = _get(final_url)
    if not resp or not resp.text:
        return final_url, "", ""
    content_type = resp.headers.get("Content-Type", "").lower()
    text = resp.text
    if "html" in content_type or final_url.endswith((".htm", ".html")):
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)
    return final_url, text, text.lower()

# ---------- Vendor extraction over 10-K / 8-K ----------
def vendor_hits_for(symbol: str, days: int = 365) -> list[dict]:
    hits = []
    forms = ["8-K", "8-K/A", "10-K", "10-K/A"]
    for form in forms:
        try:
            filings = list_filings(symbol, form=form, days=days)
        except Exception:
            filings = []
        for f in filings:
            url = f.get("filingUrl") or f.get("reportUrl") or f.get("url") or ""
            if not url:
                continue
            try:
                primary_url, _, low = fetch_filing_text_any(url)
            except Exception:
                primary_url, low = url, ""
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
                    "primaryTextUrl": primary_url,
                    "keywords_found": found[:25],
                })
    return hits

def extract_contexts(raw_text: str, low_text: str, keywords: list[str], window: int = 180):
    rows = []
    for kw in keywords:
        start = 0
        while True:
            idx = low_text.find(kw, start)
            if idx == -1:
                break
            s = max(0, idx - window)
            e = min(len(low_text), idx + len(kw) + window)
            snippet = raw_text[s:e]
            rows.append((kw, snippet))
            start = idx + len(kw)
    return rows

def build_vendor_contexts(symbol: str, days: int = 365) -> pd.DataFrame:
    rows = []
    for hit in vendor_hits_for(symbol, days=days):
        _, raw, low = fetch_filing_text_any(hit["indexUrl"])
        if not raw:
            continue
        for kw, snippet in extract_contexts(raw, low, hit["keywords_found"], window=180):
            rows.append({
                "symbol": hit["symbol"],
                "form": hit["form"],
                "filedDate": hit["filedDate"],
                "accessionNumber": hit["accessionNumber"],
                "keyword": kw,
                "context": re.sub(r"\s+", " ", snippet.strip()),
                "indexUrl": hit["indexUrl"],
                "primaryTextUrl": hit["primaryTextUrl"],
            })
    return pd.DataFrame(rows)

def guess_counterparties_from_snippet(snippet: str) -> list[str]:
    snip = re.sub(r"\s+", " ", snippet)
    cands = [m.group(1).strip() for m in ORG_CAND_RE.finditer(snip)]
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:8]

def extract_counterparties(df_contexts: pd.DataFrame, issuer_name: str = "") -> pd.DataFrame:
    if df_contexts.empty:
        return pd.DataFrame(columns=[
            "symbol","counterparty","relationship_guess","form","filedDate",
            "accessionNumber","indexUrl","primaryTextUrl","context"
        ])
    rows = []
    for _, r in df_contexts.iterrows():
        ctx = r["context"]
        orgs = guess_counterparties_from_snippet(ctx)
        l = ctx.lower()
        rel = "unsure"
        if any(w in l for w in ["supplier", "supply agreement", "contract manufacturer", "foundry"]):
            rel = "supplier"
        elif any(w in l for w in ["vendor", "procurement"]):
            rel = "vendor"
        elif any(w in l for w in ["reseller", "distribution", "distributor"]):
            rel = "reseller/distributor"
        elif "customer" in l:
            rel = "customer"
        elif any(w in l for w in ["cloud agreement", "strategic alliance", "partnership", "mou"]):
            rel = "partner"
        for org in orgs:
            if issuer_name and issuer_name.lower() in org.lower():
                continue
            rows.append({
                "symbol": r["symbol"],
                "counterparty": org,
                "relationship_guess": rel,
                "form": r["form"],
                "filedDate": r["filedDate"],
                "accessionNumber": r["accessionNumber"],
                "indexUrl": r["indexUrl"],
                "primaryTextUrl": r["primaryTextUrl"],
                "context": ctx,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["symbol","counterparty","form","filedDate","accessionNumber"])

# ---------- Multi-Item 8-K extractor ----------
def compile_item_regex(items_csv: str) -> re.Pattern:
    """
    Build a regex to capture chosen Items, e.g., "1.01,2.02,7.01,8.01".
    Extracts each Item body until the next Item/signature/exhibit/end.
    """
    items = [i.strip() for i in items_csv.split(",") if i.strip()]
    pat = "(" + "|".join([re.escape(i) for i in items]) + ")"
    return re.compile(
        rf"(item\s*(?P<num>{pat})\s*[-–—:\.]?.*?)"
        r"(?=(item\s*[0-9]{1,2}\.[0-9]{2}\b)|(\*\*\s*signature\s*\*\*)|(signatures)|(\bexhibit\b)|$)",
        flags=re.IGNORECASE | re.DOTALL
    )

def extract_items(raw_text: str, item_re: re.Pattern):
    out = []
    for m in item_re.finditer(raw_text):
        sec = re.sub(r"\s+", " ", m.group(1)).strip()
        num = m.group("num")
        out.append((num, sec))
    return out

def collect_8k_items(symbol: str, days: int, items_csv: str) -> pd.DataFrame:
    rows = []
    item_re = compile_item_regex(items_csv)
    for form in ["8-K", "8-K/A"]:
        try:
            filings = list_filings(symbol, form=form, days=days)
        except Exception:
            filings = []
        for f in filings:
            index_url = f.get("filingUrl") or f.get("url") or f.get("reportUrl") or ""
            if not index_url:
                continue
            # Always resolve via the index to avoid landing on exhibits
            if not index_url.endswith("-index.html"):
                # best-effort: some APIs give you the primary doc; try to infer the index:
                # e.g., .../000104581025000207/nvda-20250827.htm -> .../0001045810-25-000207-index.html
                # If you can’t infer reliably, still try the given URL.
                primary_url, raw, _ = fetch_filing_text_any(index_url)
            else:
                primary_doc = get_primary_doc_url_from_index(index_url)
                primary_url, raw, _ = fetch_filing_text_any(primary_doc or index_url)

            if not raw:
                continue

            for num, sec in extract_items(raw, item_re):
                rows.append({
                    "symbol": symbol,
                    "filedDate": f.get("filedDate"),
                    "accessionNumber": f.get("accessionNumber") or f.get("accessNumber"),
                    "indexUrl": index_url,
                    "primaryTextUrl": primary_url,
                    "item": num,
                    "section_len": len(sec),
                    "item_text": sec[:20000],
                })
    return pd.DataFrame(rows)

def filter_item_hits(df_items: pd.DataFrame) -> pd.DataFrame:
    if df_items.empty:
        return df_items
    needles = ["agreement","supply","supplier","vendor","partnership","strategic",
               "distribution","reseller","foundry","procurement","contract","alliance","mou"]
    mask = df_items["item_text"].str.lower().str.contains("|".join(needles), na=False)
    return df_items[mask].copy()

# ---------- Form 4 XML parsing ----------
def parse_form4_xml(url: str) -> list[dict]:
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
            "transaction_code": code,   # P,S,A,M...
            "shares": shares,
            "price": price,
            "shares_after": shares_after,
            "ownership_form": direct_indirect,
            "form4_url": url,
        })
    return trades

def collect_form4_trades_from_filings(filings: list[dict]) -> pd.DataFrame:
    rows = []
    for f in filings:
        if (f.get("form") or "").startswith("4"):
            xml_url = f.get("reportUrl") or ""
            if xml_url and xml_url.lower().endswith(".xml"):
                rows += parse_form4_xml(xml_url)
    return pd.DataFrame(rows)

# ---------- CSV helper ----------
def write_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)
    print(f"✔ Saved: {path}  ({df.shape[0]} rows)")

# ---------- Orchestration ----------
def run_for_symbol(symbol: str, days: int, items_csv: str):
    print(f"\n=== {symbol}: collecting filings ===")

    if "your@email.com" in SEC_HEADERS.get("User-Agent","").lower():
        print("WARNING: Set a real SEC User-Agent (name/company/email) to avoid SEC blocks.")

    # 1) Insider filings + trades (optional: needs Finnhub key)
    try:
        if not FINNHUB_KEY:
            raise RuntimeError("FINNHUB_API_KEY not set")
        insiders = insider_filings(symbol, days=min(90, days))
        write_csv(pd.DataFrame(insiders), f"{symbol}_insider_filings.csv")
        write_csv(collect_form4_trades_from_filings(insiders), f"{symbol}_form4_trades.csv")
    except Exception as e:
        print(f"[WARN] Insider pulls skipped for {symbol}: {e}")

    # 2) Ownership (optional: needs Finnhub key)
    try:
        if not FINNHUB_KEY:
            raise RuntimeError("FINNHUB_API_KEY not set")
        owners = ownership_filings(symbol, days=days)
        write_csv(pd.DataFrame(owners), f"{symbol}_ownership_filings.csv")
    except Exception as e:
        print(f"[WARN] Ownership pulls skipped for {symbol}: {e}")

    # 3) Vendor signals (10-K/8-K) + contexts + counterparties
    try:
        df_hits = pd.DataFrame(vendor_hits_for(symbol, days=days))
        write_csv(df_hits, f"{symbol}_vendor_hits.csv")
        df_ctx = build_vendor_contexts(symbol, days=days)
        write_csv(df_ctx, f"{symbol}_vendor_contexts.csv")
        df_ctp = extract_counterparties(df_ctx, issuer_name="")
        write_csv(df_ctp, f"{symbol}_vendor_counterparties.csv")
    except Exception as e:
        print(f"[WARN] Vendor extraction failed for {symbol}: {e}")

    # 4) Multi-Item 8-K extraction
    try:
        df_items = collect_8k_items(symbol, days=days, items_csv=items_csv)
        write_csv(df_items, f"{symbol}_8k_items.csv")
        df_hits_items = filter_item_hits(df_items)
        write_csv(df_hits_items, f"{symbol}_8k_items_hits.csv")
    except Exception as e:
        print(f"[WARN] 8-K Items extraction failed for {symbol}: {e}")

    print(f"=== DONE: {symbol} ===")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True, help="Tickers e.g. NVDA ORCL")
    ap.add_argument("--days", type=int, default=365, help="Lookback window (days)")
    ap.add_argument("--finnhub-key", default=None, help="Override FINNHUB_API_KEY")
    ap.add_argument("--sec-user-agent", default=None, help="Override SEC User-Agent header")
    ap.add_argument("--items", default="1.01,2.02,7.01,8.01",
                    help='Comma list of 8-K Items to extract (default "1.01,2.02,7.01,8.01")')
    args = ap.parse_args()

    global FINNHUB_KEY, SEC_HEADERS
    if args.finnhub_key:
        FINNHUB_KEY = args.finnhub_key
    if args.sec_user_agent:
        SEC_HEADERS["User-Agent"] = args.sec_user_agent

    for sym in args.symbols:
        try:
            run_for_symbol(sym.upper(), days=args.days, items_csv=args.items)
        except Exception as e:
            print(f"[ERROR] {sym}: {e}")

if __name__ == "__main__":
    main()
