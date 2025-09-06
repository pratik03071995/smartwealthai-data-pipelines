#!/usr/bin/env python3
"""
Script to upload nyse_top500_profiles.csv to Databricks table in sw_gold schema
"""
import os
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smartwealth_data.clients.dbfs_client import DBFSClient
from smartwealth_data.clients.sql_client import SQLClient
from smartwealth_data.config import settings

def upload_nyse_profiles_to_databricks():
    """Upload NYSE profiles CSV to Databricks table"""
    
    # CSV file path
    csv_file = "fmp_datafetch/nyse_top500_profiles.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ Error: {csv_file} not found!")
        return False
    
    try:
        # Initialize clients
        dbfs_client = DBFSClient()
        sql_client = SQLClient()
        
        print("✅ Connected to Databricks successfully!")
        
        # Create table and load data using direct SQL approach
        table_name = "nyse_profiles"
        full_table_name = f"{settings.target_db}.{table_name}"
        
        # Read CSV data and create INSERT statements
        import pandas as pd
        
        print(f"📊 Reading CSV data...")
        df = pd.read_csv(csv_file)
        print(f"✅ Read {len(df)} rows from CSV")
        
        # SQL to create table with all columns
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {full_table_name} (
            symbol STRING,
            price DOUBLE,
            marketCap DOUBLE,
            beta DOUBLE,
            lastDividend DOUBLE,
            range STRING,
            change DOUBLE,
            changePercentage DOUBLE,
            volume DOUBLE,
            averageVolume DOUBLE,
            companyName STRING,
            currency STRING,
            cik STRING,
            isin STRING,
            cusip STRING,
            exchangeFullName STRING,
            exchange STRING,
            industry STRING,
            website STRING,
            description STRING,
            ceo STRING,
            sector STRING,
            country STRING,
            fullTimeEmployees DOUBLE,
            phone STRING,
            address STRING,
            city STRING,
            state STRING,
            zip STRING,
            image STRING,
            ipoDate STRING,
            defaultImage BOOLEAN,
            isEtf BOOLEAN,
            isActivelyTrading BOOLEAN,
            isAdr BOOLEAN,
            isFund BOOLEAN,
            symbol_queried STRING,
            symbol_original STRING
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
            
            symbol = escape_string(row['symbol'])
            price = str(row['price']) if pd.notna(row['price']) else 'NULL'
            marketCap = str(row['marketCap']) if pd.notna(row['marketCap']) else 'NULL'
            beta = str(row['beta']) if pd.notna(row['beta']) else 'NULL'
            lastDividend = str(row['lastDividend']) if pd.notna(row['lastDividend']) else 'NULL'
            range_val = escape_string(row['range'])
            change = str(row['change']) if pd.notna(row['change']) else 'NULL'
            changePercentage = str(row['changePercentage']) if pd.notna(row['changePercentage']) else 'NULL'
            volume = str(row['volume']) if pd.notna(row['volume']) else 'NULL'
            averageVolume = str(row['averageVolume']) if pd.notna(row['averageVolume']) else 'NULL'
            companyName = escape_string(row['companyName'])
            currency = escape_string(row['currency'])
            cik = escape_string(row['cik'])
            isin = escape_string(row['isin'])
            cusip = escape_string(row['cusip'])
            exchangeFullName = escape_string(row['exchangeFullName'])
            exchange = escape_string(row['exchange'])
            industry = escape_string(row['industry'])
            website = escape_string(row['website'])
            description = escape_string(row['description'])
            ceo = escape_string(row['ceo'])
            sector = escape_string(row['sector'])
            country = escape_string(row['country'])
            fullTimeEmployees = str(row['fullTimeEmployees']) if pd.notna(row['fullTimeEmployees']) else 'NULL'
            phone = escape_string(row['phone'])
            address = escape_string(row['address'])
            city = escape_string(row['city'])
            state = escape_string(row['state'])
            zip_code = escape_string(row['zip'])
            image = escape_string(row['image'])
            ipoDate = escape_string(row['ipoDate'])
            defaultImage = str(row['defaultImage']).lower() if pd.notna(row['defaultImage']) else 'NULL'
            isEtf = str(row['isEtf']).lower() if pd.notna(row['isEtf']) else 'NULL'
            isActivelyTrading = str(row['isActivelyTrading']).lower() if pd.notna(row['isActivelyTrading']) else 'NULL'
            isAdr = str(row['isAdr']).lower() if pd.notna(row['isAdr']) else 'NULL'
            isFund = str(row['isFund']).lower() if pd.notna(row['isFund']) else 'NULL'
            symbol_queried = escape_string(row['symbol_queried'])
            symbol_original = escape_string(row['symbol_original'])
            
            insert_sql = f"""
            INSERT INTO {full_table_name} (
                symbol, price, marketCap, beta, lastDividend, range, change, changePercentage, 
                volume, averageVolume, companyName, currency, cik, isin, cusip, exchangeFullName, 
                exchange, industry, website, description, ceo, sector, country, fullTimeEmployees, 
                phone, address, city, state, zip, image, ipoDate, defaultImage, isEtf, isActivelyTrading, 
                isAdr, isFund, symbol_queried, symbol_original
            )
            VALUES (
                {symbol}, {price}, {marketCap}, {beta}, {lastDividend}, {range_val}, {change}, {changePercentage},
                {volume}, {averageVolume}, {companyName}, {currency}, {cik}, {isin}, {cusip}, {exchangeFullName},
                {exchange}, {industry}, {website}, {description}, {ceo}, {sector}, {country}, {fullTimeEmployees},
                {phone}, {address}, {city}, {state}, {zip_code}, {image}, {ipoDate}, {defaultImage}, {isEtf}, {isActivelyTrading},
                {isAdr}, {isFund}, {symbol_queried}, {symbol_original}
            )
            """
            
            try:
                sql_client.execute(insert_sql)
                if (index + 1) % 50 == 0:
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
    print("🚀 Starting NYSE profiles data upload to Databricks...")
    success = upload_nyse_profiles_to_databricks()
    if success:
        print("🎉 Upload completed successfully!")
    else:
        print("💥 Upload failed!")
        sys.exit(1)
