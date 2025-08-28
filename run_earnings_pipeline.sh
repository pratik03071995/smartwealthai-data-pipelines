#!/bin/bash

echo "🚀 Running SmartWealth Earnings Pipeline"
echo "========================================"

# Activate virtual environment
source venv/bin/activate

# Set your Databricks credentials here
export DATABRICKS_HOST="your-databricks-host"
export DATABRICKS_TOKEN="your-databricks-token"
export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"

echo "✅ Environment activated"
echo "✅ Databricks credentials set"
echo ""

# Run the earnings pipeline
echo "📊 Fetching earnings data for AAPL, MSFT, NVDA..."
python -m smartwealth_data.cli earnings --tickers "AAPL,MSFT,NVDA"

echo ""
echo "🎉 Pipeline completed!"
echo ""
echo "📋 To verify tables in Databricks:"
echo "   - Go to your Databricks workspace"
echo "   - Navigate to Data > sw_gold > earnings_calendar"
echo "   - Run: SELECT * FROM sw_gold.earnings_calendar ORDER BY earnings_date DESC"
