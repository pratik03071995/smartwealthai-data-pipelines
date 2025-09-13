import os, requests, datetime, re
from urllib.parse import urlencode
import pandas as pd

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "d32b54pr01qn0gi37ek0d32b54pr01qn0gi37ekg")
BASE = "https://finnhub.io/api/v1/stock/filings"

def fh(params):
    q = dict(params)
    q["token"] = FINNHUB_KEY
    url = f"{BASE}?{urlencode(q)}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def list_filings(symbol, form=None, days=30):
    to = datetime.date.today()
    frm = to - datetime.timedelta(days=days)
    params = {"symbol": symbol, "from": str(frm), "to": str(to)}
    if form:
        params["form"] = form
    return fh(params)

def insider_filings(symbol, days=60):
    data = []
    for f in ["3", "4", "5"]:
        data += list_filings(symbol, form=f, days=days)
    # Sort newest first
    return sorted(data, key=lambda x: x.get("filedDate",""), reverse=True)

def ownership_filings(symbol, days=180):
    data = []
    for f in ["13D", "13G", "13D/A", "13G/A", "13F-HR", "13F-HR/A", "144"]:
        data += list_filings(symbol, form=f, days=days)
    return sorted(data, key=lambda x: x.get("filedDate",""), reverse=True)

# --- Vendor / supplier signals via 8-K and 10-K keyword scan ----
import bs4, requests

VENDOR_KEYWORDS = [
    "supplier", "suppliers", "vendor", "vendors", "customer", "customers",
    "contract manufacturer", "foundry", "supply agreement", "master supply",
    "manufacturing agreement", "exclusive supply", "sole-source", "reseller",
    "distribution agreement", "cloud agreement", "procurement"
]

def fetch_text(url):
    """Best-effort: fetch an SEC filing page and return visible text."""
    try:
        html = requests.get(url, timeout=30).text
        soup = bs4.BeautifulSoup(html, "html.parser")
        # Remove scripts/styles
        for tag in soup(["script","style","noscript"]): tag.decompose()
        return soup.get_text(separator=" ")
    except Exception:
        return ""

def vendor_hits_for(symbol, days=365):
    hits = []
    # scan 8-K and 10-K filings for vendor/supplier words
    for form in ["8-K", "10-K"]:
        filings = list_filings(symbol, form=form, days=days)
        for f in filings:
            url = f.get("reportUrl") or f.get("url") or ""
            if not url:
                continue
            text = fetch_text(url).lower()
            found = sorted({kw for kw in VENDOR_KEYWORDS if kw in text})
            if found:
                hits.append({
                    "symbol": symbol,
                    "form": f.get("form"),
                    "filedDate": f.get("filedDate"),
                    "accessionNumber": f.get("accessionNumber"),
                    "reportUrl": url,
                    "keywords_found": found[:15]
                })
    return hits

if __name__ == "__main__":
    symbol = "NVDA"

    # === INSIDER FILINGS ===
    print("\n=== Latest INSIDER filings (Forms 3/4/5) ===")
    insider_data = insider_filings(symbol)
    insider_df = pd.DataFrame(insider_data)
    print(insider_df)
    insider_csv = f"{symbol}_insider_filings.csv"
    insider_df.to_csv(insider_csv, index=False)
    print(f"✅ Insider filings saved to {insider_csv}")

    # === OWNERSHIP FILINGS ===
    print("\n=== Major ownership filings (13D/13G/13F/144) ===")
    ownership_data = ownership_filings(symbol)
    ownership_df = pd.DataFrame(ownership_data)
    print(ownership_df)
    ownership_csv = f"{symbol}_ownership_filings.csv"
    ownership_df.to_csv(ownership_csv, index=False)
    print(f"✅ Ownership filings saved to {ownership_csv}")

    # === VENDOR / SUPPLIER SIGNALS ===
    print("\n=== Vendor/supplier mentions in 8-K/10-K (keyword hits) ===")
    vendor_data = vendor_hits_for(symbol)
    vendor_df = pd.DataFrame(vendor_data)
    print(vendor_df)
    vendor_csv = f"{symbol}_vendor_hits.csv"
    vendor_df.to_csv(vendor_csv, index=False)
    print(f"✅ Vendor hits saved to {vendor_csv}")

    # === SUMMARY ===
    print(f"\n=== SUMMARY ===")
    print(f"Symbol: {symbol}")
    print(f"Insider filings: {len(insider_data)}")
    print(f"Ownership filings: {len(ownership_data)}")
    print(f"Vendor/supplier hits: {len(vendor_data)}")