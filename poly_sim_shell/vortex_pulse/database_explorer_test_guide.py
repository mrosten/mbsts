#!/usr/bin/env python3
"""
Database Explorer Test Guide
Complete guide for testing all database explorer functions.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def show_test_guide():
    """Show comprehensive test guide for database explorer."""
    print("🎯 DATABASE EXPLORER TEST GUIDE")
    print("=" * 70)
    print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("✅ PRE-REQUISITES CHECKLIST:")
    print("   ✓ Restart the trading application")
    print("   ✓ Database path is fixed")
    print("   ✓ Tick logging is enabled")
    print("   ✓ Database contains test data")
    print()
    
    print("🖱️  DATABASE EXPLORER OPTIONS TO TEST:")
    print("=" * 50)
    
    options = [
        {
            "name": "ticks (last 100)",
            "description": "Shows the most recent 100 price ticks",
            "expected": "Should show 2 test ticks with timestamps and prices",
            "columns": "id, timestamp, price, source, window_id, created_at"
        },
        {
            "name": "ticks (last 1000)",
            "description": "Shows up to 1000 most recent price ticks",
            "expected": "Should show same 2 test ticks (more data when trading)",
            "columns": "id, timestamp, price, source, window_id, created_at"
        },
        {
            "name": "windows (last 50)",
            "description": "Shows the most recent 50 trading windows",
            "expected": "Should show 2 test windows with start/end times",
            "columns": "id, window_id, start_time, end_time, start_price, end_price, resolution, created_at"
        },
        {
            "name": "trades (last 50)",
            "description": "Shows the most recent 50 trade executions",
            "expected": "Should show 2 test trades with P&L data",
            "columns": "id, window_id, direction, entry_price, exit_price, pnl, status, created_at"
        },
        {
            "name": "all data",
            "description": "Shows summary statistics for all tables",
            "expected": "Should show row counts for each table",
            "format": "Summary format: ticks: 2 rows, windows: 2 rows, trades: 2 rows"
        }
    ]
    
    for i, option in enumerate(options, 1):
        print(f"{i}. 📊 {option['name']}")
        print(f"   📝 Description: {option['description']}")
        print(f"   ✅ Expected: {option['expected']}")
        print(f"   📋 Columns: {option['columns']}")
        print()
    
    print("🧪 ADDITIONAL TESTS:")
    print("=" * 30)
    print("• Test with trading app running - should see real-time data")
    print("• Test during active trading windows - should see live ticks")
    print("• Test after trades execute - should see P&L data")
    print("• Test database performance with large datasets")
    print()
    
    print("🔧 TROUBLESHOOTING:")
    print("=" * 25)
    print("• If 'file not found' - Restart application to reload config")
    print("• If no data - Check tick logging is enabled")
    print("• If errors appear - Check database file permissions")
    print("• If slow loading - Database may need optimization")
    print()
    
    print("📈 EXPECTED BEHAVIOR WITH LIVE TRADING:")
    print("=" * 45)
    print("• Ticks table: Updates every second when trading is active")
    print("• Windows table: Updates every 5 minutes (per trading window)")
    print("• Trades table: Updates when trades are executed")
    print("• Performance: Should handle thousands of ticks efficiently")
    print()
    
    print("🎯 SUCCESS CRITERIA:")
    print("=" * 30)
    print("✅ All options load without 'file not found' error")
    print("✅ Data displays in proper table format")
    print("✅ Columns are correctly labeled")
    print("✅ Timestamps and prices are readable")
    print("✅ No connection errors or timeouts")
    print()
    
    print("📞 NEXT STEPS AFTER TESTING:")
    print("=" * 35)
    print("1. Test all options listed above")
    print("2. Run trading app for 5+ minutes to generate real data")
    print("3. Re-test options to see live data")
    print("4. Verify tick logging is working in real-time")
    print("5. Check audit website for database integration")

def show_database_status():
    """Show current database status."""
    print("📊 CURRENT DATABASE STATUS")
    print("=" * 40)
    
    try:
        from config import DB_PATH
        import sqlite3
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get table stats
        cursor.execute("SELECT 'ticks', COUNT(*) FROM ticks UNION ALL SELECT 'windows', COUNT(*) FROM windows UNION ALL SELECT 'trades', COUNT(*) FROM trades;")
        stats = cursor.fetchall()
        
        for table, count in stats:
            print(f"   📋 {table}: {count} rows")
        
        # Get latest activity
        cursor.execute("SELECT MAX(timestamp) FROM ticks;")
        latest_tick = cursor.fetchone()[0]
        
        if latest_tick:
            import time
            age_minutes = (time.time() - latest_tick) / 60
            print(f"   🕐 Latest tick: {age_minutes:.0f} minutes ago")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Error checking status: {e}")

def main():
    show_database_status()
    print()
    show_test_guide()

if __name__ == "__main__":
    main()
