import requests
import pandas as pd
from datetime import datetime, timedelta

# Your FMP API key
API_KEY = "jFShbRJmQFEFneU6mL4rgQpkMat8DbRW"

# Set date range (today → +60 days)
today = datetime.today().strftime("%Y-%m-%d")
end_date = (datetime.today() + timedelta(days=60)).strftime("%Y-%m-%d")

# Build URL
url = f"https://financialmodelingprep.com/api/v3/earning_calendar?from={today}&to={end_date}&apikey={API_KEY}"

# Request data
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    if data:
        df = pd.DataFrame(data)
        print("✅ Earnings calendar data received!")
        print(df.head(10))  # show first 10 rows
    else:
        print("⚠️ No data returned. Try adjusting the date range.")
else:
    print(f"❌ Request failed: {response.status_code}")
    print(response.text)
