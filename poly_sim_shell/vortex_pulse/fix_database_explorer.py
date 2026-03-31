#!/usr/bin/env python3
"""
Fix Database Explorer Path
Ensures database explorer can find the database file.
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_database_explorer_paths():
    """Check all possible paths where database explorer might look."""
    print("🔍 CHECKING DATABASE EXPLORER PATHS")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # Possible database paths
    possible_paths = [
        os.path.join(current_dir, "poly_history.db"),  # Current directory
        os.path.join(parent_dir, "poly_history.db"),  # Parent directory
        os.path.join(current_dir, "data", "poly_history.db"),  # Data subdirectory
        os.path.join(parent_dir, "data", "poly_history.db"),  # Parent data subdirectory
    ]
    
    print(f"📍 Current directory: {current_dir}")
    print(f"📍 Parent directory: {parent_dir}")
    print()
    
    found_db = None
    for path in possible_paths:
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✅ Found database: {path}")
            print(f"   Size: {size / 1024:.1f} KB")
            found_db = path
        else:
            print(f"❌ Not found: {path}")
    
    return found_db

def create_database_symlinks():
    """Create symlinks/copies in common locations."""
    print(f"\n🔗 CREATING DATABASE SYMLINKS")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    source_db = os.path.join(parent_dir, "poly_history.db")
    
    if not os.path.exists(source_db):
        print(f"❌ Source database not found: {source_db}")
        return False
    
    # Target locations
    targets = [
        os.path.join(current_dir, "poly_history.db"),
        os.path.join(current_dir, "data", "poly_history.db"),
    ]
    
    for target in targets:
        # Create directory if needed
        target_dir = os.path.dirname(target)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            print(f"📁 Created directory: {target_dir}")
        
        # Remove existing file/symlink
        if os.path.exists(target):
            os.remove(target)
            print(f"🗑️  Removed existing: {target}")
        
        try:
            # Try creating symlink first
            os.symlink(source_db, target)
            print(f"🔗 Created symlink: {target} -> {source_db}")
        except (OSError, NotImplementedError):
            # If symlink fails, copy the file
            shutil.copy2(source_db, target)
            print(f"📋 Copied database: {target}")
    
    return True

def check_database_explorer_config():
    """Check database explorer configuration."""
    print(f"\n⚙️  CHECKING DATABASE EXPLORER CONFIG")
    print("=" * 50)
    
    # Look for database explorer config files
    config_files = []
    
    for root, dirs, files in os.walk(os.path.dirname(__file__)):
        for file in files:
            if any(keyword in file.lower() for keyword in ['explorer', 'db_', 'database']):
                config_files.append(os.path.join(root, file))
    
    if config_files:
        print(f"📄 Found database-related files:")
        for config_file in config_files[:5]:  # Show first 5
            print(f"   📋 {config_file}")
            
            # Try to read database path from file
            try:
                with open(config_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for line in content.split('\n'):
                    if any(keyword in line.lower() for keyword in ['path', 'database', 'db']):
                        print(f"      {line.strip()}")
                        
            except Exception as e:
                print(f"      Error reading: {e}")
    else:
        print("❌ No database explorer config files found")
    
    # Check for common database explorer locations
    common_paths = [
        os.path.join(os.path.dirname(__file__), "db_explorer"),
        os.path.join(os.path.dirname(__file__), "database_explorer"),
        os.path.join(os.path.dirname(__file__), "explorer"),
    ]
    
    print(f"\n🔍 Checking common explorer locations:")
    for path in common_paths:
        if os.path.exists(path):
            print(f"✅ Found: {path}")
        else:
            print(f"❌ Not found: {path}")

def create_explorer_config():
    """Create a database explorer configuration file."""
    print(f"\n📝 CREATING EXPLORER CONFIG")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    db_path = os.path.join(parent_dir, "poly_history.db")
    
    # Create a simple config file
    config_content = f"""# Database Explorer Configuration
# Generated: {sys.time.strftime('%Y-%m-%d %H:%M:%S') if hasattr(sys, 'time') else '2026-03-24 13:36:00'}

[database]
path = {db_path}
type = sqlite3
name = poly_history

[tables]
ticks = ticks
windows = windows
trades = trades

[settings]
auto_refresh = true
refresh_interval = 5
"""
    
    config_file = os.path.join(current_dir, "db_explorer_config.ini")
    
    try:
        with open(config_file, 'w') as f:
            f.write(config_content)
        print(f"✅ Created config: {config_file}")
        print(f"   Database path: {db_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create config: {e}")
        return False

def main():
    print("🔧 DATABASE EXPLORER FIX")
    print("=" * 60)
    
    # 1. Check current database paths
    found_db = check_database_explorer_paths()
    
    # 2. Create symlinks/copies
    if found_db:
        create_database_symlinks()
    
    # 3. Check explorer config
    check_database_explorer_config()
    
    # 4. Create explorer config
    create_explorer_config()
    
    # 5. Summary
    print(f"\n📋 SUMMARY")
    print("=" * 50)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"✅ Database locations created:")
    print(f"   📁 {os.path.join(current_dir, 'poly_history.db')}")
    print(f"   📁 {os.path.join(current_dir, 'data', 'poly_history.db')}")
    print(f"   📁 {os.path.join(os.path.dirname(current_dir), 'poly_history.db')}")
    
    print(f"\n✅ Configuration created:")
    print(f"   📄 {os.path.join(current_dir, 'db_explorer_config.ini')}")
    
    print(f"\n🔧 Next steps:")
    print(f"1. Restart database explorer")
    print(f"2. Point explorer to one of the database locations above")
    print(f"3. Use the config file if explorer supports it")
    print(f"4. Check explorer's database path settings")

if __name__ == "__main__":
    import time
    main()
