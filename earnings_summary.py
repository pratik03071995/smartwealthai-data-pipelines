#!/usr/bin/env python3
"""
Summary script to show loaded earnings data and provide useful queries
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

def show_earnings_summary():
    """Show a comprehensive summary of the loaded earnings data"""
    print("📊 NYSE Earnings Calendar Summary")
    print("=" * 50)
    
    try:
        from smartwealth_data.clients.sql_client import SQLClient
        sql_client = SQLClient()
        
        # 1. Overall statistics
        print("\n📈 Overall Statistics:")
        print("-" * 30)
        
        total_count = sql_client.execute("SELECT COUNT(*) as total FROM sw_gold.earnings_calendar")
        print(f"Total records: {total_count}")
        
        upcoming_count = sql_client.execute("SELECT COUNT(*) as upcoming FROM sw_gold.earnings_calendar WHERE earnings_date >= CURRENT_DATE()")
        print(f"Upcoming earnings: {upcoming_count}")
        
        companies_count = sql_client.execute("SELECT COUNT(DISTINCT ticker) as companies FROM sw_gold.earnings_calendar")
        print(f"Unique companies: {companies_count}")
        
        sectors_count = sql_client.execute("SELECT COUNT(DISTINCT sector) as sectors FROM sw_gold.earnings_calendar")
        print(f"Unique sectors: {sectors_count}")
        
        # 2. Date range
        print("\n📅 Date Range:")
        print("-" * 30)
        
        date_range = sql_client.execute("SELECT MIN(earnings_date) as min_date, MAX(earnings_date) as max_date FROM sw_gold.earnings_calendar")
        print(f"Earliest date: {date_range['min_date']}")
        print(f"Latest date: {date_range['max_date']}")
        
        # 3. Upcoming earnings (next 30 days)
        print("\n🔮 Upcoming Earnings (Next 30 Days):")
        print("-" * 50)
        
        upcoming = sql_client.execute("""
            SELECT ticker, earnings_date, eps_estimate, company_name, sector 
            FROM sw_gold.earnings_calendar 
            WHERE earnings_date >= CURRENT_DATE() 
            AND earnings_date <= DATE_ADD(CURRENT_DATE(), 30)
            ORDER BY earnings_date ASC
        """)
        
        if upcoming:
            for row in upcoming:
                print(f"  {row['earnings_date']} | {row['ticker']:6} | {row['company_name'][:30]:30} | {row['sector']}")
        else:
            print("  No upcoming earnings in the next 30 days")
        
        # 4. Earnings by sector
        print("\n🏭 Earnings by Sector:")
        print("-" * 30)
        
        sector_stats = sql_client.execute("""
            SELECT sector, COUNT(*) as count 
            FROM sw_gold.earnings_calendar 
            WHERE earnings_date >= CURRENT_DATE() 
            GROUP BY sector 
            ORDER BY count DESC
        """)
        
        for row in sector_stats:
            print(f"  {row['sector']}: {row['count']} earnings")
        
        # 5. Top companies by earnings frequency
        print("\n🏢 Top Companies by Earnings Frequency:")
        print("-" * 45)
        
        company_stats = sql_client.execute("""
            SELECT ticker, company_name, COUNT(*) as earnings_count 
            FROM sw_gold.earnings_calendar 
            WHERE earnings_date >= CURRENT_DATE() 
            GROUP BY ticker, company_name 
            ORDER BY earnings_count DESC 
            LIMIT 10
        """)
        
        for row in company_stats:
            print(f"  {row['ticker']:6} | {row['company_name'][:30]:30} | {row['earnings_count']} earnings")
        
        # 6. Useful queries
        print("\n💡 Useful Queries:")
        print("-" * 30)
        print("1. All upcoming earnings:")
        print("   SELECT * FROM sw_gold.earnings_calendar WHERE earnings_date >= CURRENT_DATE() ORDER BY earnings_date ASC")
        
        print("\n2. Earnings by specific sector:")
        print("   SELECT * FROM sw_gold.earnings_calendar WHERE sector = 'Technology' AND earnings_date >= CURRENT_DATE()")
        
        print("\n3. Earnings for specific company:")
        print("   SELECT * FROM sw_gold.earnings_calendar WHERE ticker = 'AAPL' ORDER BY earnings_date DESC")
        
        print("\n4. Earnings with EPS estimates:")
        print("   SELECT ticker, earnings_date, eps_estimate, company_name FROM sw_gold.earnings_calendar WHERE eps_estimate IS NOT NULL AND earnings_date >= CURRENT_DATE()")
        
        print("\n5. Sector distribution:")
        print("   SELECT sector, COUNT(*) as count FROM sw_gold.earnings_calendar WHERE earnings_date >= CURRENT_DATE() GROUP BY sector ORDER BY count DESC")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("Make sure your Databricks credentials are set correctly")

def main():
    """Main function"""
    show_earnings_summary()

if __name__ == "__main__":
    main()
