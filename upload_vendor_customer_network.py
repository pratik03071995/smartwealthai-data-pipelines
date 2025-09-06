#!/usr/bin/env python3
"""
Script to upload top20_us_companies_vendor_customer_network.csv to Databricks table in sw_gold schema
"""
import os
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smartwealth_data.clients.dbfs_client import DBFSClient
from smartwealth_data.clients.sql_client import SQLClient
from smartwealth_data.config import settings

def upload_vendor_customer_network():
    """Upload vendor-customer network CSV to Databricks table"""
    
    # CSV file path
    csv_file = "fmp_datafetch/top20_us_companies_vendor_customer_network.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ Error: {csv_file} not found!")
        return False
    
    try:
        # Initialize clients
        dbfs_client = DBFSClient()
        sql_client = SQLClient()
        
        print("✅ Connected to Databricks successfully!")
        
        # Create table and load data using direct SQL approach
        table_name = "vendor_customer_network"
        full_table_name = f"{settings.target_db}.{table_name}"
        
        # Read CSV data and create INSERT statements
        import pandas as pd
        
        print(f"📊 Reading CSV data...")
        df = pd.read_csv(csv_file)
        print(f"✅ Read {len(df)} rows from CSV")
        
        # SQL to create table with all columns
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {full_table_name} (
            company STRING,
            ticker STRING,
            relation_type STRING,
            counterparty_name STRING,
            counterparty_type STRING,
            tier STRING,
            category STRING,
            component_or_product STRING,
            region STRING,
            relationship_strength DOUBLE,
            est_contract_value_usd_m DOUBLE,
            start_year DOUBLE,
            notes STRING,
            is_dummy BOOLEAN
        )
        """
        
        print(f"🏗️ Creating table {full_table_name}...")
        sql_client.execute(create_table_sql)
        print("✅ Table created successfully!")
        
        # Insert data row by row
        print(f"📊 Inserting data into {full_table_name}...")
        for index, row in df.iterrows():
            # Handle NULL values and escape single quotes in strings
            def escape_string(val):
                if pd.notna(val):
                    val_str = str(val)
                    val_str = val_str.replace("'", "''")
                    return f"'{val_str}'"
                return 'NULL'
            
            company = escape_string(row['company'])
            ticker = escape_string(row['ticker'])
            relation_type = escape_string(row['relation_type'])
            counterparty_name = escape_string(row['counterparty_name'])
            counterparty_type = escape_string(row['counterparty_type'])
            tier = escape_string(row['tier'])
            category = escape_string(row['category'])
            component_or_product = escape_string(row['component_or_product'])
            region = escape_string(row['region'])
            relationship_strength = str(row['relationship_strength']) if pd.notna(row['relationship_strength']) else 'NULL'
            est_contract_value_usd_m = str(row['est_contract_value_usd_m']) if pd.notna(row['est_contract_value_usd_m']) else 'NULL'
            start_year = str(row['start_year']) if pd.notna(row['start_year']) else 'NULL'
            notes = escape_string(row['notes'])
            is_dummy = str(row['is_dummy']).lower() if pd.notna(row['is_dummy']) else 'NULL'
            
            insert_sql = f"""
            INSERT INTO {full_table_name} (
                company, ticker, relation_type, counterparty_name, counterparty_type, tier, 
                category, component_or_product, region, relationship_strength, est_contract_value_usd_m, 
                start_year, notes, is_dummy
            )
            VALUES (
                {company}, {ticker}, {relation_type}, {counterparty_name}, {counterparty_type}, {tier},
                {category}, {component_or_product}, {region}, {relationship_strength}, {est_contract_value_usd_m},
                {start_year}, {notes}, {is_dummy}
            )
            """
            
            try:
                sql_client.execute(insert_sql)
                if (index + 1) % 20 == 0:
                    print(f"   Inserted {index + 1} rows...")
            except Exception as e:
                print(f"⚠️ Error inserting row {index + 1}: {str(e)}")
                continue
        
        print("✅ Data insertion completed!")
        
        # Verify the data
        count_sql = f"SELECT COUNT(*) as row_count FROM {full_table_name}"
        count_result = sql_client.execute(count_sql)
        row_count = count_result['result']['data_array'][0][0]
        print(f"📈 Loaded {row_count} rows into {full_table_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Starting vendor-customer network data upload to Databricks...")
    success = upload_vendor_customer_network()
    if success:
        print("🎉 Upload completed successfully!")
    else:
        print("💥 Upload failed!")
        sys.exit(1)
