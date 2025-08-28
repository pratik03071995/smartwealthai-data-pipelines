#!/usr/bin/env python3
"""
Script to run the SmartWealth earnings pipeline with proper environment setup
"""
import os
import sys

# Set Databricks credentials as environment variables BEFORE importing any modules
# Note: Set these environment variables before running the script
# export DATABRICKS_HOST="your-databricks-host"
# export DATABRICKS_TOKEN="your-databricks-token"
# export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"

# Now import and run the CLI
from smartwealth_data.cli import app

if __name__ == "__main__":
    print("🚀 Running SmartWealth Earnings Pipeline")
    print("========================================")
    print("✅ Databricks credentials set")
    print("📊 Fetching earnings data for AAPL, MSFT, NVDA...")
    print("")
    
    # Run the CLI with the earnings command and a different DBFS path
    sys.argv = ["earnings", "--tickers", "AAPL,MSFT,NVDA", "--dbfs-staging-dir", "dbfs:/tmp/staging"]
    app()
    
    print("")
    print("🎉 Pipeline completed!")
    print("")
    print("📋 To verify tables in Databricks:")
    print("   - Go to your Databricks workspace")
    print("   - Navigate to Data > sw_gold > earnings_calendar")
    print("   - You should see the earnings data loaded")
