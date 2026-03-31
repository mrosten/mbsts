#!/usr/bin/env python3
"""
Database Diagnostic Tool
Checks if tick logging database and tables are being created properly.
"""

import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_database_files():
    """Check for database files in the project."""
    print("🔍 CHECKING DATABASE FILES")
    print("=" * 50)
    
    # Look for database files - check current directory AND parent directory
    db_files = []
    search_dirs = [
        os.path.dirname(__file__),  # Current directory
        os.path.dirname(os.path.dirname(__file__))  # Parent directory
    ]
    
    for search_dir in search_dirs:
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.db') or file.endswith('.sqlite') or file.endswith('.sqlite3'):
                    db_path = os.path.join(root, file)
                    file_size = os.path.getsize(db_path)
                    file_time = datetime.fromtimestamp(os.path.getmtime(db_path))
                    db_files.append((db_path, file_size, file_time))
    
    if db_files:
        print(f"📁 Found {len(db_files)} database file(s):")
        for db_path, size, mtime in sorted(db_files, key=lambda x: x[2], reverse=True):
            size_kb = size / 1024
            age = (datetime.now() - mtime).total_seconds() / 60
            print(f"  📄 {os.path.basename(db_path)}")
            print(f"     Path: {db_path}")
            print(f"     Size: {size_kb:.1f} KB")
            print(f"     Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')} ({age:.0f} min ago)")
            print()
    else:
        print("❌ No database files found")
        print("💡 Tick logging may not be enabled or configured")
    
    return db_files

def check_database_structure(db_path):
    """Check the structure and content of a database."""
    print(f"🔍 ANALYZING: {os.path.basename(db_path)}")
    print("-" * 40)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if tables:
            print(f"📊 Tables found: {len(tables)}")
            for table_name, in tables:
                print(f"\n📋 Table: {table_name}")
                
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                print(f"   Columns: {len(columns)}")
                for col_info in columns:
                    col_id, col_name, col_type, not_null, default, pk = col_info
                    pk_str = " (PK)" if pk else ""
                    print(f"     - {col_name}: {col_type}{pk_str}")
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                row_count = cursor.fetchone()[0]
                print(f"   Rows: {row_count}")
                
                # Show sample data if available
                if row_count > 0:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                    sample_rows = cursor.fetchall()
                    print(f"   Sample data (first 3 rows):")
                    for i, row in enumerate(sample_rows, 1):
                        print(f"     Row {i}: {row}")
                else:
                    print(f"   ⚠️  No data in table")
        
        else:
            print("❌ No tables found in database")
        
        # Check database size and page count
        cursor.execute("SELECT page_count, page_size FROM pragma_page_count(), pragma_page_size();")
        page_info = cursor.fetchone()
        if page_info:
            page_count, page_size = page_info
            actual_size = page_count * page_size
            print(f"\n📏 Database info:")
            print(f"   Pages: {page_count}")
            print(f"   Page size: {page_size} bytes")
            print(f"   Actual size: {actual_size / 1024:.1f} KB")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error analyzing database: {e}")
        return False

def check_tick_logging_config():
    """Check tick logging configuration."""
    print(f"\n⚙️  CHECKING TICK LOGGING CONFIG")
    print("=" * 50)
    
    # Check for tick logging settings
    config_files = ['config.py', 'pulse_settings.json', '.env']
    
    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"\n📄 Checking {config_file}:")
            
            try:
                if config_file.endswith('.py'):
                    with open(config_file, 'r') as f:
                        content = f.read()
                    
                    # Look for tick logging related settings
                    tick_settings = []
                    for line in content.split('\n'):
                        if any(keyword in line.lower() for keyword in ['tick', 'database', 'db_', 'sqlite']):
                            tick_settings.append(line.strip())
                    
                    if tick_settings:
                        print("   Tick logging settings found:")
                        for setting in tick_settings:
                            print(f"     {setting}")
                    else:
                        print("   No tick logging settings found")
                
                elif config_file.endswith('.json'):
                    import json
                    with open(config_file, 'r') as f:
                        data = json.load(f)
                    
                    # Look for tick logging in JSON
                    tick_found = False
                    for key, value in data.items():
                        if 'tick' in key.lower() or 'database' in key.lower():
                            print(f"   {key}: {value}")
                            tick_found = True
                    
                    if not tick_found:
                        print("   No tick logging settings found")
                
            except Exception as e:
                print(f"   Error reading {config_file}: {e}")

def check_recent_logs():
    """Check recent logs for tick logging activity."""
    print(f"\n📝 CHECKING RECENT LOGS")
    print("=" * 50)
    
    # Look for log files
    log_files = []
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    
    for root, dirs, files in os.walk(lg_dir):
        for file in files:
            if file.endswith('.log') or file.endswith('.txt'):
                log_path = os.path.join(root, file)
                file_time = os.path.getmtime(log_path)
                age_minutes = (time.time() - file_time) / 60
                
                if age_minutes < 60:  # Last hour
                    log_files.append((log_path, age_minutes))
    
    if log_files:
        print(f"📄 Found {len(log_files)} recent log files:")
        
        for log_path, age in sorted(log_files, key=lambda x: x[1]):
            print(f"\n📋 {os.path.basename(log_path)} ({age:.0f} min ago):")
            
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Read last few lines
                    lines = f.readlines()
                    recent_lines = lines[-5:] if len(lines) > 5 else lines
                
                for line in recent_lines:
                    if any(keyword in line.lower() for keyword in ['tick', 'database', 'sqlite', 'db']):
                        print(f"   {line.strip()}")
                        
            except Exception as e:
                print(f"   Error reading log: {e}")
    else:
        print("❌ No recent log files found")

def main():
    print("🔍 DATABASE DIAGNOSTIC TOOL")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Check for database files
    db_files = check_database_files()
    
    # 2. Analyze each database found
    if db_files:
        for db_path, size, mtime in db_files:
            check_database_structure(db_path)
            print("\n" + "="*60 + "\n")
    
    # 3. Check tick logging configuration
    check_tick_logging_config()
    
    # 4. Check recent logs
    check_recent_logs()
    
    # 5. Summary and recommendations
    print(f"\n📋 SUMMARY & RECOMMENDATIONS")
    print("=" * 50)
    
    if db_files:
        print("✅ Database files found")
        
        # Check if any have data
        any_data = False
        for db_path, size, mtime in db_files:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                for table_name, in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    row_count = cursor.fetchone()[0]
                    if row_count > 0:
                        any_data = True
                        break
                
                conn.close()
                if any_data:
                    break
            except:
                pass
        
        if any_data:
            print("✅ Database contains data")
            print("💡 Database explorer should show tables and data")
        else:
            print("⚠️  Database exists but contains no data")
            print("💡 Tick logging may be enabled but not receiving ticks")
    else:
        print("❌ No database files found")
        print("💡 Check if tick logging is enabled in configuration")
    
    print(f"\n🔧 Troubleshooting steps:")
    print("1. Verify tick logging is enabled in config")
    print("2. Check if trading app is actively running")
    print("3. Ensure database path is writable")
    print("4. Check for error messages in console logs")

if __name__ == "__main__":
    import time
    main()
