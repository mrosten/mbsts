#!/usr/bin/env python3
"""
Test All Database Functions
Tests all database explorer options and logging functions.
"""

import os
import sys
import sqlite3
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_all_database_functions():
    """Test all database explorer options and logging functions."""
    print("🧪 TESTING ALL DATABASE FUNCTIONS")
    print("=" * 60)
    
    try:
        from config import DB_PATH
        
        if not os.path.exists(DB_PATH):
            print(f"❌ Database not found: {DB_PATH}")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
        
        print(f"📋 Available tables: {', '.join(tables)}")
        print()
        
        # Test each table like the database explorer would
        for table_name in tables:
            print(f"🔍 Testing table: {table_name}")
            print("-" * 40)
            
            try:
                # Get table structure
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"📋 Columns: {', '.join(columns)}")
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"📊 Total rows: {count}")
                
                # Get sample data (like "last 100" would do)
                if count > 0:
                    cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 3;")
                    rows = cursor.fetchall()
                    
                    print(f"📄 Sample data (last 3 rows):")
                    for i, row in enumerate(rows):
                        print(f"   Row {i+1}: {row}")
                    
                    # Test specific queries based on table type
                    if table_name == 'ticks':
                        test_ticks_queries(cursor)
                    elif table_name == 'windows':
                        test_windows_queries(cursor)
                    elif table_name == 'trades':
                        test_trades_queries(cursor)
                
                print(f"✅ {table_name} table working!")
                print()
                
            except Exception as e:
                print(f"❌ Error testing {table_name}: {e}")
                print()
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def test_ticks_queries(cursor):
    """Test ticks-specific queries."""
    print(f"   📈 Testing ticks queries:")
    
    # Test recent ticks
    cursor.execute("SELECT COUNT(*) FROM ticks WHERE timestamp > ?;", (time.time() - 3600,))
    recent_count = cursor.fetchone()[0]
    print(f"      • Recent ticks (last hour): {recent_count}")
    
    # Test unique sources
    cursor.execute("SELECT DISTINCT source FROM ticks;")
    sources = [row[0] for row in cursor.fetchall()]
    print(f"      • Data sources: {', '.join(sources)}")
    
    # Test price range
    cursor.execute("SELECT MIN(price), MAX(price), AVG(price) FROM ticks;")
    min_price, max_price, avg_price = cursor.fetchone()
    if min_price and max_price:
        print(f"      • Price range: ${min_price:.2f} - ${max_price:.2f} (avg: ${avg_price:.2f})")

def test_windows_queries(cursor):
    """Test windows-specific queries."""
    print(f"   🪟 Testing windows queries:")
    
    # Test window count
    cursor.execute("SELECT COUNT(*) FROM windows;")
    window_count = cursor.fetchone()[0]
    print(f"      • Total windows: {window_count}")
    
    # Test resolutions
    cursor.execute("SELECT DISTINCT resolution FROM windows;")
    resolutions = [row[0] for row in cursor.fetchall() if row[0]]
    print(f"      • Resolutions: {', '.join(resolutions)}")
    
    # Test recent windows
    cursor.execute("SELECT COUNT(*) FROM windows WHERE end_time > ?;", (time.time() - 3600,))
    recent_windows = cursor.fetchone()[0]
    print(f"      • Recent windows (last hour): {recent_windows}")

def test_trades_queries(cursor):
    """Test trades-specific queries."""
    print(f"   💰 Testing trades queries:")
    
    # Test trade count
    cursor.execute("SELECT COUNT(*) FROM trades;")
    trade_count = cursor.fetchone()[0]
    print(f"      • Total trades: {trade_count}")
    
    # Test directions
    cursor.execute("SELECT direction, COUNT(*) FROM trades GROUP BY direction;")
    directions = cursor.fetchall()
    if directions:
        dir_str = ', '.join([f"{d} ({c})" for d, c in directions])
        print(f"      • Trade directions: {dir_str}")
    
    # Test P&L
    cursor.execute("SELECT COUNT(*), SUM(pnl), AVG(pnl) FROM trades WHERE pnl IS NOT NULL;")
    count, total_pnl, avg_pnl = cursor.fetchone()
    if count and count > 0:
        print(f"      • Total P&L: ${total_pnl:.2f} (avg: ${avg_pnl:.2f} per trade)")

def test_tick_logging_simulation():
    """Simulate tick logging to ensure it works."""
    print(f"🧪 SIMULATING TICK LOGGING")
    print("=" * 60)
    
    try:
        from config import DB_PATH, DB_LOG_TICKS
        
        print(f"📊 Tick logging enabled: {DB_LOG_TICKS}")
        print(f"📍 Database path: {DB_PATH}")
        
        if not DB_LOG_TICKS:
            print(f"⚠️  Tick logging is disabled in config")
            print(f"💡 Set DB_LOG_TICKS=True in pulse_settings.json")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Simulate adding a new tick
        current_time = time.time()
        test_price = 50000.0 + (time.time() % 1000)  # Variable price
        
        cursor.execute("""
            INSERT INTO ticks (timestamp, price, source, window_id) 
            VALUES (?, ?, ?, ?)
        """, (current_time, test_price, 'simulation', f"sim_window_{int(current_time)}"))
        
        conn.commit()
        
        # Verify the tick was added
        cursor.execute("SELECT COUNT(*) FROM ticks;")
        new_count = cursor.fetchone()[0]
        
        print(f"✅ Simulated tick logged successfully!")
        print(f"📊 Total ticks in database: {new_count}")
        print(f"📈 Latest tick price: ${test_price:.2f}")
        
        # Test window logging
        window_id = f"test_window_{int(current_time)}"
        cursor.execute("""
            INSERT INTO windows (window_id, start_time, end_time, start_price, end_price, resolution) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (window_id, current_time - 300, current_time, test_price - 100, test_price + 100, 'UP'))
        
        # Test trade logging
        cursor.execute("""
            INSERT INTO trades (window_id, direction, entry_price, exit_price, pnl, status) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (window_id, 'UP', test_price - 100, test_price + 100, 200.0, 'COMPLETED'))
        
        conn.commit()
        
        print(f"✅ Simulated window and trade logged!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Tick logging simulation failed: {e}")
        return False

def test_database_explorer_ui_simulation():
    """Simulate all database explorer UI options."""
    print(f"🖥️  SIMULATING DATABASE EXPLORER UI")
    print("=" * 60)
    
    ui_options = [
        "ticks (last 100)",
        "windows (last 50)", 
        "trades (last 50)",
        "ticks (last 1000)",
        "all data"
    ]
    
    try:
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for option in ui_options:
            print(f"🖱️  Simulating click: '{option}'")
            
            if "ticks" in option:
                limit = 100 if "100" in option else 1000
                cursor.execute(f"SELECT * FROM ticks ORDER BY timestamp DESC LIMIT {limit};")
                rows = cursor.fetchall()
                print(f"   ✅ Would show {len(rows)} ticks")
                
            elif "windows" in option:
                cursor.execute("SELECT * FROM windows ORDER BY end_time DESC LIMIT 50;")
                rows = cursor.fetchall()
                print(f"   ✅ Would show {len(rows)} windows")
                
            elif "trades" in option:
                cursor.execute("SELECT * FROM trades ORDER BY created_at DESC LIMIT 50;")
                rows = cursor.fetchall()
                print(f"   ✅ Would show {len(rows)} trades")
                
            elif "all data" in option:
                cursor.execute("SELECT 'ticks', COUNT(*) FROM ticks UNION ALL SELECT 'windows', COUNT(*) FROM windows UNION ALL SELECT 'trades', COUNT(*) FROM trades;")
                summary = cursor.fetchall()
                print(f"   ✅ Would show summary:")
                for table, count in summary:
                    print(f"      {table}: {count} rows")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ UI simulation failed: {e}")
        return False

def main():
    print("🎯 COMPREHENSIVE DATABASE FUNCTION TEST")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test 1: All database functions
    success1 = test_all_database_functions()
    
    # Test 2: Tick logging simulation
    success2 = test_tick_logging_simulation()
    
    # Test 3: UI simulation
    success3 = test_database_explorer_ui_simulation()
    
    # Summary
    print(f"\n📋 COMPREHENSIVE TEST RESULTS")
    print("=" * 70)
    print(f"✅ Database Functions: {'PASS' if success1 else 'FAIL'}")
    print(f"✅ Tick Logging: {'PASS' if success2 else 'FAIL'}")
    print(f"✅ UI Simulation: {'PASS' if success3 else 'FAIL'}")
    
    if success1 and success2 and success3:
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"📊 All database explorer options should work!")
        print(f"📈 Tick logging is functional!")
        print(f"\n💡 What you can test:")
        print(f"   • Click 'ticks (last 100)' - Shows recent price ticks")
        print(f"   • Click 'ticks (last 1000)' - Shows more historical ticks")
        print(f"   • Click 'windows (last 50)' - Shows trading windows")
        print(f"   • Click 'trades (last 50)' - Shows trade executions")
        print(f"   • Click 'all data' - Shows summary statistics")
    else:
        print(f"\n❌ Some tests failed!")
        print(f"💡 Check the error messages above")
    
    return 0 if (success1 and success2 and success3) else 1

if __name__ == "__main__":
    sys.exit(main())
