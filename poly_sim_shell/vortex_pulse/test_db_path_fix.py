#!/usr/bin/env python3
"""
Test Database Path Fix
Tests if the database explorer can now find the database.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_db_path():
    """Test the database path configuration."""
    print("🧪 TESTING DATABASE PATH FIX")
    print("=" * 50)
    
    try:
        from config import DB_PATH
        print(f"📍 DB_PATH from config: {DB_PATH}")
        print(f"📁 File exists: {os.path.exists(DB_PATH)}")
        
        if os.path.exists(DB_PATH):
            size = os.path.getsize(DB_PATH)
            print(f"📊 File size: {size / 1024:.1f} KB")
            
            # Test database connection
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"📋 Tables: {', '.join(tables)}")
            
            cursor.execute("SELECT COUNT(*) FROM ticks;")
            count = cursor.fetchone()[0]
            print(f"📊 Ticks: {count} rows")
            
            conn.close()
            print(f"✅ Database accessible!")
            
        else:
            print(f"❌ Database file not found")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def show_path_resolution():
    """Show how the database path is resolved."""
    print(f"\n🔍 PATH RESOLUTION LOGIC")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(parent_dir)
    
    print(f"📍 Current directory: {current_dir}")
    print(f"📍 Parent directory: {parent_dir}")
    print(f"📍 Root directory: {root_dir}")
    print()
    
    # Show the paths being checked
    paths = {
        "Original (root)": os.path.join(root_dir, "poly_history.db"),
        "Vortex (parent)": os.path.join(parent_dir, "poly_history.db"),
        "Local (current)": os.path.join(current_dir, "poly_history.db"),
    }
    
    for name, path in paths.items():
        exists = os.path.exists(path)
        print(f"{'✅' if exists else '❌'} {name}: {path}")
        if exists:
            size = os.path.getsize(path)
            print(f"   Size: {size / 1024:.1f} KB")

def main():
    test_db_path()
    show_path_resolution()
    
    print(f"\n📋 NEXT STEPS")
    print("=" * 50)
    print(f"1. Restart the trading application")
    print(f"2. Click on DB Explorer")
    print(f"3. Select 'ticks (last 100)'")
    print(f"4. Should now show data instead of 'file not found'")

if __name__ == "__main__":
    main()
