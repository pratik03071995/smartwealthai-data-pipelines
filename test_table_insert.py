#!/usr/bin/env python3
"""
Test script to insert sample earnings data directly into the Databricks table
"""
import os
import sys
from pathlib import Path

# Set Databricks credentials as environment variables
# Note: Set these environment variables before running the script
# export DATABRICKS_HOST="your-databricks-host"
# export DATABRICKS_TOKEN="your-databricks-token"
# export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_direct_table_insert():
    """Test inserting data directly into the table using SQL"""
    print("🧪 Testing Direct Table Insert")
    print("=" * 40)
    
    try:
        from smartwealth_data.clients.sql_client import SQLClient
        
        # Create SQL client
        sql_client = SQLClient()
        
        # Sample earnings data
        sample_data = [
            ("AAPL", "2025-05-01", 1.63, 1.65, 1.41, 2025, 2, "Apple Inc.", "Technology", "Consumer Electronics", "yfinance"),
            ("MSFT", "2025-04-30", 3.22, 3.25, 0.93, 2025, 2, "Microsoft Corporation", "Technology", "Software - Infrastructure", "yfinance"),
            ("NVDA", "2025-06-26", 5.57, 5.60, 0.54, 2025, 2, "NVIDIA Corporation", "Technology", "Semiconductors", "yfinance"),
            ("AAPL", "2025-01-30", 2.35, 2.40, 2.15, 2025, 1, "Apple Inc.", "Technology", "Consumer Electronics", "yfinance"),
            ("MSFT", "2025-01-29", 3.11, 3.15, 1.29, 2025, 1, "Microsoft Corporation", "Technology", "Software - Infrastructure", "yfinance"),
        ]
        
        # Create INSERT statements
        insert_sql = """
        INSERT INTO sw_gold.earnings_calendar 
        (ticker, earnings_date, eps_estimate, eps_actual, surprise_pct, fiscal_year, fiscal_quarter, company_name, sector, industry, source, ingested_at_utc)
        VALUES 
        """
        
        values = []
        for row in sample_data:
            values.append(f"('{row[0]}', '{row[1]}', {row[2]}, {row[3]}, {row[4]}, {row[5]}, {row[6]}, '{row[7]}', '{row[8]}', '{row[9]}', '{row[10]}', CURRENT_TIMESTAMP())")
        
        insert_sql += ",\n".join(values)
        
        print("📝 Inserting sample data...")
        print(f"   Rows to insert: {len(sample_data)}")
        
        # Execute the INSERT
        result = sql_client.execute(insert_sql)
        print("✅ Data inserted successfully!")
        
        # Query the data to verify
        print("\n🔍 Verifying data...")
        query_result = sql_client.execute("SELECT COUNT(*) as row_count FROM sw_gold.earnings_calendar")
        print(f"   Total rows in table: {query_result}")
        
        # Show sample data
        sample_query = sql_client.execute("SELECT ticker, earnings_date, eps_estimate, eps_actual, company_name FROM sw_gold.earnings_calendar ORDER BY earnings_date DESC LIMIT 5")
        print(f"   Sample data: {sample_query}")
        
        return True
        
    except Exception as e:
        print(f"❌ Insert failed: {e}")
        return False

def test_table_structure():
    """Test the table structure"""
    print("\n🏗️  Testing Table Structure")
    print("=" * 40)
    
    try:
        from smartwealth_data.clients.sql_client import SQLClient
        
        sql_client = SQLClient()
        
        # Describe the table
        describe_result = sql_client.execute("DESCRIBE sw_gold.earnings_calendar")
        print("✅ Table structure:")
        print(f"   {describe_result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Structure test failed: {e}")
        return False

def main():
    print("🚀 Databricks Table Insert Test")
    print("=" * 50)
    
    # Test 1: Table structure
    if not test_table_structure():
        print("❌ Cannot proceed without table structure")
        return
    
    # Test 2: Direct insert
    if test_direct_table_insert():
        print("\n🎉 All tests completed successfully!")
        print("\n📋 To verify in Databricks:")
        print("   - Go to your Databricks workspace")
        print("   - Navigate to Data > sw_gold > earnings_calendar")
        print("   - You should see the test data loaded")
        print("   - Run: SELECT * FROM sw_gold.earnings_calendar ORDER BY earnings_date DESC")
    else:
        print("\n❌ Insert test failed")

if __name__ == "__main__":
    main()
