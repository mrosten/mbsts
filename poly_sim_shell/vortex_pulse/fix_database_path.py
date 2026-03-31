#!/usr/bin/env python3
"""
Fix Database Path
Fixes the database path issue and creates the database.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_database_path():
    """Fix the database path and create the database."""
    print("🔧 FIXING DATABASE PATH ISSUE")
    print("=" * 50)
    
    # Current config path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    current_db_path = os.path.join(parent_dir, "poly_history.db")
    
    print(f"📍 Current database path: {current_db_path}")
    print(f"📍 Current directory: {current_dir}")
    print(f"📍 Parent directory: {parent_dir}")
    
    # Check if database exists at current path
    if os.path.exists(current_db_path):
        print(f"✅ Database exists at current path")
        print(f"📊 Size: {os.path.getsize(current_db_path) / 1024:.1f} KB")
    else:
        print(f"❌ Database not found at current path")
        
        # Create the database
        print(f"🔨 Creating database...")
        
        try:
            conn = sqlite3.connect(current_db_path)
            cursor = conn.cursor()
            
            # Create tick logging table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    price REAL NOT NULL,
                    source TEXT,
                    window_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create windows table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS windows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    window_id TEXT UNIQUE NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    start_price REAL,
                    end_price REAL,
                    resolution TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    window_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    pnl REAL,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticks_timestamp ON ticks(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_windows_window_id ON windows(window_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_window_id ON trades(window_id)")
            
            conn.commit()
            conn.close()
            
            print(f"✅ Database created successfully!")
            print(f"📁 Location: {current_db_path}")
            print(f"📊 Tables: ticks, windows, trades")
            
        except Exception as e:
            print(f"❌ Failed to create database: {e}")
            return False
    
    # Test database access
    print(f"\n🧪 Testing database access...")
    try:
        conn = sqlite3.connect(current_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"✅ Database accessible!")
        print(f"📊 Tables found: {[t[0] for t in tables]}")
        
        # Insert a test tick
        cursor.execute("""
            INSERT INTO ticks (timestamp, price, source, window_id) 
            VALUES (?, ?, ?, ?)
        """, (sys.time.time() if hasattr(sys, 'time') else 1648123456.0, 50000.0, 'test', 'test_window'))
        
        conn.commit()
        
        # Check the tick was inserted
        cursor.execute("SELECT COUNT(*) FROM ticks;")
        count = cursor.fetchone()[0]
        
        print(f"✅ Test tick inserted! Total ticks: {count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    
    return True

def update_pulse_settings():
    """Update pulse_settings.json to ensure tick logging is enabled."""
    print(f"\n⚙️  UPDATING PULSE SETTINGS")
    print("=" * 50)
    
    settings_file = "pulse_settings.json"
    
    if os.path.exists(settings_file):
        try:
            import json
            
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            
            # Ensure tick logging is enabled
            settings['db_log_ticks'] = True
            settings['db_tick_freq'] = 1
            settings['db_logging_enabled'] = True
            
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            
            print(f"✅ Updated {settings_file}")
            print(f"   db_log_ticks: {settings['db_log_ticks']}")
            print(f"   db_tick_freq: {settings['db_tick_freq']}")
            print(f"   db_logging_enabled: {settings['db_logging_enabled']}")
            
        except Exception as e:
            print(f"❌ Failed to update settings: {e}")
    else:
        print(f"⚠️  {settings_file} not found")

def main():
    print("🔧 DATABASE PATH FIX")
    print("=" * 60)
    
    # Fix database path and create database
    if fix_database_path():
        # Update settings
        update_pulse_settings()
        
        print(f"\n✅ DATABASE FIX COMPLETE!")
        print(f"📋 Next steps:")
        print(f"1. Restart the trading application")
        print(f"2. Check database explorer - it should now show tables")
        print(f"3. Tick logging should start working immediately")
        print(f"4. Database location: ../poly_history.db")
        
        print(f"\n🌐 Database Explorer:")
        print(f"   The database explorer should now find the database")
        print(f"   and show the tables: ticks, windows, trades")
    else:
        print(f"\n❌ DATABASE FIX FAILED!")
        print(f"💡 Check file permissions and disk space")

if __name__ == "__main__":
    import time
    main()
