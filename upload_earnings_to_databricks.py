#!/usr/bin/env python3
"""
Script to upload earnings_next3m_full.csv to Databricks table in sw_gold schema
"""
import os
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smartwealth_data.clients.dbfs_client import DBFSClient
from smartwealth_data.clients.sql_client import SQLClient
from smartwealth_data.config import settings

def upload_earnings_to_databricks():
    """Upload earnings CSV to Databricks table"""
    
    # CSV file path
    csv_file = "earnings_next3m_full.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ Error: {csv_file} not found!")
        return False
    
    try:
        # Initialize clients
        dbfs_client = DBFSClient()
        sql_client = SQLClient()
        
        print("✅ Connected to Databricks successfully!")
        
        # Create table and load data using direct SQL approach
        table_name = "earnings_calendar_new"
        full_table_name = f"{settings.target_db}.{table_name}"
        
        # Read CSV data and create INSERT statements
        import pandas as pd
        
        print(f"📊 Reading CSV data...")
        df = pd.read_csv(csv_file)
        print(f"✅ Read {len(df)} rows from CSV")
        
        # SQL to create table
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {full_table_name} (
            symbol STRING,
            date DATE,
            time STRING,
            eps DOUBLE,
            epsEstimated DOUBLE,
            revenue DOUBLE,
            revenueEstimated DOUBLE
        )
        """
        
        print(f"🏗️ Creating table {full_table_name}...")
        sql_client.execute(create_table_sql)
        print("✅ Table created successfully!")
        
        # Insert data row by row
        print(f"📊 Inserting data into {full_table_name}...")
        for index, row in df.iterrows():
            # Handle NULL values
            symbol = f"'{row['symbol']}'" if pd.notna(row['symbol']) else 'NULL'
            date = f"'{row['date']}'" if pd.notna(row['date']) else 'NULL'
            time = f"'{row['time']}'" if pd.notna(row['time']) else 'NULL'
            eps = str(row['eps']) if pd.notna(row['eps']) else 'NULL'
            epsEstimated = str(row['epsEstimated']) if pd.notna(row['epsEstimated']) else 'NULL'
            revenue = str(row['revenue']) if pd.notna(row['revenue']) else 'NULL'
            revenueEstimated = str(row['revenueEstimated']) if pd.notna(row['revenueEstimated']) else 'NULL'
            
            insert_sql = f"""
            INSERT INTO {full_table_name} (symbol, date, time, eps, epsEstimated, revenue, revenueEstimated)
            VALUES ({symbol}, {date}, {time}, {eps}, {epsEstimated}, {revenue}, {revenueEstimated})
            """
            
            try:
                sql_client.execute(insert_sql)
                if (index + 1) % 10 == 0:
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
    print("🚀 Starting earnings data upload to Databricks...")
    success = upload_earnings_to_databricks()
    if success:
        print("🎉 Upload completed successfully!")
    else:
        print("💥 Upload failed!")
        sys.exit(1)
