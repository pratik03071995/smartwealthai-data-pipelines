
token ='d32b54pr01qn0gi37ek0d32b54pr01qn0gi37ekg'

import finnhub
import pandas as pd

finnhub_client = finnhub.Client(api_key="d32b54pr01qn0gi37ek0d32b54pr01qn0gi37ekg")

# Fetch filings data
filings_data = finnhub_client.filings(symbol='AAPL', _from="2020-01-01", to="2020-06-11")

# Convert to DataFrame
df = pd.DataFrame(filings_data)

# Display the DataFrame
print("AAPL Filings DataFrame:")
print(df)
print(f"\nDataFrame shape: {df.shape}")
print(f"\nColumns: {list(df.columns)}")

# Show first few rows with better formatting
if not df.empty:
    print(f"\nFirst 5 rows:")
    print(df.head())
else:
    print("\nNo data returned from API")
