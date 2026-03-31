#!/usr/bin/env python3
"""
Create Database Tables
Creates the required tables for tick logging.
"""

import os
import sys
import sqlite3
import time

def create_database_tables():
    """Create the required database tables."""
    print("🔨 CREATING DATABASE TABLES")
    print("=" * 50)
    
    # Database path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    db_path = os.path.join(parent_dir, "poly_history.db")
    
    print(f"📍 Database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create ticks table
        print("📋 Creating ticks table...")
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
        print("✅ ticks table created")
        
        # Create windows table
        print("📋 Creating windows table...")
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
        print("✅ windows table created")
        
        # Create trades table
        print("📋 Creating trades table...")
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
        print("✅ trades table created")
        
        # Create indexes
        print("📋 Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticks_timestamp ON ticks(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_windows_window_id ON windows(window_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_window_id ON trades(window_id)")
        print("✅ indexes created")
        
        # Insert test data
        print("🧪 Inserting test data...")
        current_time = time.time()
        
        # Test tick
        cursor.execute("""
            INSERT INTO ticks (timestamp, price, source, window_id) 
            VALUES (?, ?, ?, ?)
        """, (current_time, 50000.0, 'test', 'test_window_001'))
        
        # Test window
        cursor.execute("""
            INSERT INTO windows (window_id, start_time, end_time, start_price, end_price, resolution) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('test_window_001', current_time - 300, current_time, 49000.0, 51000.0, 'UP'))
        
        # Test trade
        cursor.execute("""
            INSERT INTO trades (window_id, direction, entry_price, exit_price, pnl, status) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('test_window_001', 'UP', 49000.0, 51000.0, 200.0, 'COMPLETED'))
        
        conn.commit()
        
        # Verify tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n✅ Database setup complete!")
        print(f"📊 Tables created: {[t[0] for t in tables]}")
        
        # Show table contents
        for table_name, in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"   {table_name}: {count} rows")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

def verify_database():
    """Verify the database is working correctly."""
    print(f"\n🧪 VERIFYING DATABASE")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    db_path = os.path.join(parent_dir, "poly_history.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📊 Tables found: {[t[0] for t in tables]}")
        
        # Show sample data
        for table_name, in tables:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
            rows = cursor.fetchall()
            
            print(f"\n📋 {table_name} (sample data):")
            for row in rows:
                print(f"   {row}")
        
        conn.close()
        
        print(f"\n✅ Database is ready!")
        print(f"🌐 Database explorer should now show:")
        print(f"   - Database file: {db_path}")
        print(f"   - Tables: ticks, windows, trades")
        print(f"   - Sample data in each table")
        
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

def main():
    print("🔨 DATABASE TABLES CREATION")
    print("=" * 60)
    
    if create_database_tables():
        if verify_database():
            print(f"\n🎉 SUCCESS! Database is ready for tick logging!")
            print(f"📋 Next steps:")
            print(f"1. Restart the trading application")
            print(f"2. Database explorer will now show tables and data")
            print(f"3. Tick logging will start populating the tables")
        else:
            print(f"\n❌ Verification failed")
    else:
        print(f"\n❌ Table creation failed")

if __name__ == "__main__":
    main()
