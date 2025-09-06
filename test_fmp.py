# test_fmp_stable_earnings.py
import requests
import pandas as pd
from datetime import datetime, timedelta

API_KEY = "jFShbRJmQFEFneU6mL4rgQpkMat8DbRW"  # <- your key

# 60-day window (adjust as needed)
today = datetime.utcnow().date()
end   = today + timedelta(days=60)

url = (
    "https://financialmodelingprep.com/stable/earnings-calendar"
    f"?from={today}&to={end}&apikey={API_KEY}"
)

resp = requests.get(url, timeout=30)

if resp.status_code != 200:
    print(f"❌ HTTP {resp.status_code}")
    print(resp.text)
else:
    data = resp.json()
    if not data:
        print("⚠️ No data returned. Try widening the date range.")
    else:
        df = pd.DataFrame(data)
        # Common fields returned: symbol, date, eps, epsEstimated, time, revenue, revenueEstimated
        print("✅ Received rows:", len(df))
        print(df.to_string(index=False))
