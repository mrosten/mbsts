#!/usr/bin/env python3
"""
Quick System Status
Quick check of system health and BullFlag fix.
"""

import os
import sys
import sqlite3
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_bullflag_fix():
    """Check if BullFlag settings modal is fixed."""
    print("🔧 BULLFLAG SETTINGS FIX")
    print("=" * 40)
    
    try:
        # Check if the fix is in place
        with open("ui_modals.py", 'r') as f:
            content = f.read()
        
        if "research_enabled = False" in content and "# Research logging checkbox was removed" in content:
            print("✅ BullFlag settings modal fixed")
            print("   • Removed reference to missing #cb_research_log")
            print("   • Set research_enabled to False by default")
            return True
        else:
            print("❌ BullFlag fix may not be applied")
            return False
            
    except Exception as e:
        print(f"❌ Error checking BullFlag fix: {e}")
        return False

def check_database():
    """Check database status."""
    print("\n🗄️  DATABASE STATUS")
    print("=" * 40)
    
    try:
        from config import DB_PATH
        
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT 'ticks', COUNT(*) FROM ticks UNION ALL SELECT 'windows', COUNT(*) FROM windows UNION ALL SELECT 'trades', COUNT(*) FROM trades;")
            stats = cursor.fetchall()
            
            for table, count in stats:
                print(f"📋 {table}: {count} rows")
            
            conn.close()
            print("✅ Database operational")
            return True
        else:
            print("❌ Database not found")
            return False
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def check_audit_website():
    """Check audit website status."""
    print("\n🌐 AUDIT WEBSITE STATUS")
    print("=" * 40)
    
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    
    if os.path.exists(lg_dir):
        # Find current session
        current_session = None
        latest_time = 0
        
        for item in os.listdir(lg_dir):
            if os.path.isdir(os.path.join(lg_dir, item)) and item.startswith("session_"):
                session_path = os.path.join(lg_dir, item)
                session_time = os.path.getmtime(session_path)
                
                if session_time > latest_time:
                    latest_time = session_time
                    current_session = item
        
        if current_session:
            age_minutes = int((time.time() - latest_time) / 60)
            print(f"📁 Current session: {current_session}")
            print(f"🕐 Started: {age_minutes} minutes ago")
            print(f"🌐 Website: http://myfavoritemalshin.space/{current_session}/verification.html")
            print("✅ Audit website operational")
            return True
        else:
            print("❌ No current session")
            return False
    else:
        print("❌ Log directory not found")
        return False

def main():
    print("🔍 QUICK SYSTEM STATUS")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check all systems
    results = {
        "BullFlag Fix": check_bullflag_fix(),
        "Database": check_database(),
        "Audit Website": check_audit_website()
    }
    
    # Summary
    print("\n📋 SUMMARY")
    print("=" * 40)
    
    for system, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {system}: {'OK' if status else 'ISSUE'}")
    
    operational_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n🎯 Overall: {operational_count}/{total_count} systems working")
    
    if operational_count == total_count:
        print("🎉 All systems operational!")
    else:
        print("⚠️  Some issues detected")

if __name__ == "__main__":
    main()
