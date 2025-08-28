#!/usr/bin/env python3
"""
Test script to verify Databricks connection and create test tables
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

def test_connection():
    """Test basic Databricks connection"""
    print("🔌 Testing Databricks connection...")
    
    try:
        from smartwealth_data.clients.sql_client import SQLClient
        from smartwealth_data.config import settings
        
        print(f"✅ Configuration loaded:")
        print(f"   Host: {settings.databricks_host}")
        print(f"   Warehouse ID: {settings.databricks_warehouse_id}")
        
        # Create SQL client
        sql_client = SQLClient()
        
        # Test simple query
        result = sql_client.execute("SELECT 1 as test")
        print(f"✅ Connection test successful: {result}")
        
        return sql_client
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return None

def test_table_creation(sql_client):
    """Test creating the databases and tables"""
    print("\n🏗️  Testing table creation...")
    
    try:
        # Read and execute schema creation
        schemas_sql = Path("sql/00_schemas.sql").read_text()
        print("📄 Creating databases...")
        
        # Split and execute each statement separately
        statements = [stmt.strip() for stmt in schemas_sql.split(';') if stmt.strip()]
        for stmt in statements:
            if stmt:
                sql_client.execute(stmt)
        print("✅ Databases created successfully")
        
        # Read and execute table creation
        table_sql = Path("sql/gold_ddl.sql").read_text()
        print("📄 Creating earnings_calendar table...")
        
        # Split and execute each statement separately
        statements = [stmt.strip() for stmt in table_sql.split(';') if stmt.strip()]
        for stmt in statements:
            if stmt:
                sql_client.execute(stmt)
        print("✅ Table created successfully")
        
        # Test querying the table
        print("🔍 Testing table query...")
        result = sql_client.execute("SHOW TABLES IN sw_gold")
        print("✅ Table query successful!")
        print(f"   Tables in sw_gold: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Table creation failed: {str(e)}")
        return False

def main():
    """Main function"""
    print("🧪 Databricks Connection and Table Creation Test")
    print("=" * 55)
    
    # Test connection
    sql_client = test_connection()
    if not sql_client:
        return
    
    # Test table creation
    success = test_table_creation(sql_client)
    
    if success:
        print("\n🎉 All tests passed!")
        print("✅ Databricks connection working")
        print("✅ Databases and tables created successfully")
        print("\n📋 Next steps:")
        print("   - Run load_real_earnings.py to load data")
        print("   - Run earnings_summary.py to view data")
    else:
        print("\n❌ Some tests failed")

if __name__ == "__main__":
    main()
