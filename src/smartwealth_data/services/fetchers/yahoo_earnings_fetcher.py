from datetime import datetime, timedelta
import time, logging, pandas as pd, yfinance as yf
log = logging.getLogger(__name__)

class YahooEarningsFetcher:
    def __init__(self, months_back: int = 12, polite_sleep_s: float = 0.2):
        # Create timezone-aware cutoff to avoid timezone comparison issues
        self.cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=30*months_back)
        self.sleep = polite_sleep_s

    @staticmethod
    def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        colmap = {c.lower(): c for c in df.columns}
        def pick(*opts):
            for o in opts:
                if o.lower() in colmap: return colmap[o.lower()]
            return None

        if "Earnings Date" in df.columns:
            df = df.set_index(pd.to_datetime(df["Earnings Date"]))
        else:
            df.index = pd.to_datetime(df.index)

        eps_est = pick("EPS Estimate","Eps Estimate")
        eps_act = pick("Reported EPS","Reported Eps","Actual EPS","Actual Eps")
        surpr   = pick("EPS Surprise %","Surprise(%)","Eps Surprise %","Earnings Surprise %")
        qtr     = pick("Quarter","Fiscal Quarter","FQ")

        out = pd.DataFrame(index=df.index.copy())
        out["eps_estimate"] = pd.to_numeric(df[eps_est], errors="coerce") if eps_est else None
        out["eps_actual"]   = pd.to_numeric(df[eps_act], errors="coerce") if eps_act else None
        out["surprise_pct"] = pd.to_numeric(df[surpr],   errors="coerce") if surpr else None
        out["fiscal_quarter_label"] = df[qtr].astype(str) if qtr else None
        return out.reset_index(names=["earnings_ts"])

    @staticmethod
    def _company_info(tk: yf.Ticker) -> dict:
        try:
            info = tk.get_info() or {}
        except Exception:
            try: info = tk.info or {}
            except Exception: info = {}
        return {
            "company_name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

    def fetch(self, tickers: list[str]) -> pd.DataFrame:
        rows = []
        for t in tickers:
            tk = yf.Ticker(t)
            df = None
            try: df = tk.get_earnings_dates(limit=100)
            except Exception: pass
            if df is None:
                try: df = tk.earnings_dates
                except Exception: df = None
            if df is None or df.empty:
                log.warning("No earnings for %s", t); continue

            norm = self._normalize_df(df)
            # Convert earnings_ts to timezone-naive for comparison if needed
            earnings_ts_naive = norm["earnings_ts"].dt.tz_localize(None) if norm["earnings_ts"].dt.tz is not None else norm["earnings_ts"]
            cutoff_naive = self.cutoff.tz_localize(None) if self.cutoff.tz is not None else self.cutoff
            norm = norm[earnings_ts_naive >= cutoff_naive]
            if norm.empty:
                log.warning("Only old earnings for %s", t); continue

            meta = self._company_info(tk)
            for _, r in norm.iterrows():
                rows.append({
                    "ticker": t,
                    "earnings_date": r["earnings_ts"].date().isoformat(),
                    "eps_estimate": None if pd.isna(r["eps_estimate"]) else float(r["eps_estimate"]),
                    "eps_actual": None if pd.isna(r["eps_actual"]) else float(r["eps_actual"]),
                    "surprise_pct": None if pd.isna(r["surprise_pct"]) else float(r["surprise_pct"]),
                    "fiscal_year": int(r["earnings_ts"].year),
                    "fiscal_quarter": int(((r["earnings_ts"].month-1)//3)+1),
                    "company_name": meta["company_name"],
                    "sector": meta["sector"],
                    "industry": meta["industry"],
                    "source": "yfinance",
                })
            time.sleep(self.sleep)
        return pd.DataFrame(rows)
