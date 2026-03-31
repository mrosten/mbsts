#!/usr/bin/env python3
"""
Test Database Explorer Access
Quick test to verify database can be accessed from common paths.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_access():
    """Test database access from various paths."""
    print("🧪 TESTING DATABASE ACCESS")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # Test paths
    test_paths = [
        os.path.join(current_dir, "poly_history.db"),
        os.path.join(current_dir, "data", "poly_history.db"),
        os.path.join(parent_dir, "poly_history.db"),
    ]
    
    success_count = 0
    
    for path in test_paths:
        print(f"\n📍 Testing: {path}")
        
        if os.path.exists(path):
            try:
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT COUNT(*) FROM ticks;")
                count = cursor.fetchone()[0]
                
                print(f"✅ Connected successfully!")
                print(f"📊 Ticks table: {count} rows")
                
                # Get table list
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                print(f"📋 Tables: {', '.join(tables)}")
                
                success_count += 1
                conn.close()
                
            except Exception as e:
                print(f"❌ Connection failed: {e}")
        else:
            print(f"❌ File not found")
    
    print(f"\n📋 SUMMARY")
    print("=" * 50)
    print(f"✅ Successful connections: {success_count}/{len(test_paths)}")
    
    if success_count > 0:
        print(f"\n🎉 Database explorer should work!")
        print(f"💡 Point your database explorer to any of the working paths above")
        
        # Show the best path (first successful one)
        for path in test_paths:
            if os.path.exists(path):
                print(f"🌐 Recommended path: {path}")
                break
    else:
        print(f"\n❌ No working database paths found")
        print(f"💡 Check file permissions and database creation")

def show_explorer_instructions():
    """Show instructions for common database explorers."""
    print(f"\n📖 DATABASE EXPLORER INSTRUCTIONS")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    print(f"🔧 For DB Browser for SQLite:")
    print(f"   1. Open DB Browser")
    print(f"   2. Click 'Open Database'")
    print(f"   3. Navigate to: {parent_dir}")
    print(f"   4. Select: poly_history.db")
    print()
    
    print(f"🔧 For DBeaver:")
    print(f"   1. Create new connection")
    print(f"   2. Select SQLite")
    print(f"   3. Database file: {parent_dir}\\poly_history.db")
    print(f"   4. Click 'Test Connection'")
    print()
    
    print(f"🔧 For VS Code SQLite Extension:")
    print(f"   1. Install SQLite extension")
    print(f"   2. Click 'SQLite Explorer' in sidebar")
    print(f"   3. Click 'Add Database'")
    print(f"   4. Enter path: {parent_dir}\\poly_history.db")
    print()
    
    print(f"🔧 Alternative paths (if above doesn't work):")
    print(f"   • {current_dir}\\poly_history.db")
    print(f"   • {current_dir}\\data\\poly_history.db")

def main():
    test_database_access()
    show_explorer_instructions()

if __name__ == "__main__":
    main()
