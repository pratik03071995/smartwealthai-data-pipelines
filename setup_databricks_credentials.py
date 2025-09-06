#!/usr/bin/env python3
"""
Interactive script to set up Databricks credentials
"""
import os
import getpass

def setup_credentials():
    """Set up Databricks credentials interactively"""
    
    print("🔧 Setting up Databricks credentials...")
    print("=" * 50)
    
    # Get credentials from user
    host = input("Enter your Databricks workspace URL (e.g., https://adb-xxx.azuredatabricks.net): ").strip()
    token = getpass.getpass("Enter your Databricks personal access token: ").strip()
    warehouse_id = input("Enter your Databricks SQL warehouse ID: ").strip()
    
    # Set environment variables
    os.environ['DATABRICKS_HOST'] = host
    os.environ['DATABRICKS_TOKEN'] = token
    os.environ['DATABRICKS_WAREHOUSE_ID'] = warehouse_id
    os.environ['TARGET_DB'] = 'sw_gold'
    os.environ['TARGET_TABLE_EARNINGS'] = 'earnings_calendar'
    
    print("\n✅ Credentials set successfully!")
    print("You can now run: python upload_earnings_to_databricks.py")
    
    return True

if __name__ == "__main__":
    setup_credentials()
