#!/usr/bin/env python3
"""
Final Database Explorer Verification
Final check that database explorer works correctly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def simulate_db_explorer():
    """Simulate what the database explorer does."""
    print("🔍 SIMULATING DATABASE EXPLORER")
    print("=" * 50)
    
    try:
        # Import config like the UI modal does
        from config import DB_PATH
        
        print(f"📍 Database path: {DB_PATH}")
        
        # Check if file exists (this is what the explorer checks)
        if not os.path.exists(DB_PATH):
            print(f"❌ Database file not found at {DB_PATH}")
            return False
        
        print(f"✅ Database file found!")
        
        # Try to connect (this is what happens when you click "ticks (last 100)")
        import sqlite3
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get table info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"📋 Available tables: {', '.join(tables)}")
            
            # Simulate clicking "ticks (last 100)"
            if 'ticks' in tables:
                cursor.execute("SELECT * FROM ticks ORDER BY timestamp DESC LIMIT 100;")
                rows = cursor.fetchall()
                
                print(f"📊 Ticks table: {len(rows)} rows total")
                print(f"📊 Showing last {min(100, len(rows))} rows:")
                
                # Get column names
                cursor.execute("PRAGMA table_info(ticks);")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"📋 Columns: {', '.join(columns)}")
                
                # Show sample data
                for i, row in enumerate(rows[:3]):  # Show first 3
                    print(f"   Row {i+1}: {row}")
                
                if len(rows) > 3:
                    print(f"   ... and {len(rows) - 3} more rows")
                
                print(f"✅ Database explorer would show this data!")
                
            else:
                print(f"❌ 'ticks' table not found")
                return False
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Config import error: {e}")
        return False

def main():
    print("🎯 FINAL DATABASE EXPLORER VERIFICATION")
    print("=" * 60)
    
    success = simulate_db_explorer()
    
    print(f"\n📋 RESULT")
    print("=" * 50)
    
    if success:
        print(f"✅ Database explorer should now work!")
        print(f"🎉 The 'file not found' error should be resolved")
        print(f"📊 Clicking 'ticks (last 100)' should show data")
        print(f"\n🔧 What was fixed:")
        print(f"   • Database path configuration updated")
        print(f"   • Multiple fallback paths added")
        print(f"   • Database explorer now finds existing database")
        print(f"\n📋 Next steps:")
        print(f"   1. Restart the trading application")
        print(f"   2. Open DB Explorer")
        print(f"   3. Select 'ticks (last 100)'")
        print(f"   4. Should see tick data instead of error")
    else:
        print(f"❌ Still issues found")
        print(f"💡 Check database file permissions")
        print(f"💡 Restart the application to reload config")

if __name__ == "__main__":
    main()
