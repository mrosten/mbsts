#!/usr/bin/env python3
"""
Permanent FTP Fix
Permanently fixes the FTP path issue in ftp_manager.py
"""

import os
import sys

def fix_ftp_manager():
    """Fix the Windows path issue in ftp_manager.py"""
    
    ftp_file = "ftp_manager.py"
    
    # Read current file
    with open(ftp_file, 'r') as f:
        content = f.read()
    
    # Fix the path issue - replace backslashes with forward slashes
    old_line = 'self.remote_session_dir = f"{self.root_dir}/{session_id}"'
    new_line = 'self.remote_session_dir = f"{self.root_dir}/{session_id}".replace("\\\\", "/")'
    
    if old_line in content:
        content = content.replace(old_line, new_line)
        
        # Write fixed file
        with open(ftp_file, 'w') as f:
            f.write(content)
        
        print("✅ Fixed FTP path issue in ftp_manager.py")
        print("   Replaced Windows backslashes with forward slashes")
        return True
    else:
        print("❌ Could not find the line to fix")
        return False

def main():
    print("🔧 PERMANENT FTP FIX")
    print("=" * 40)
    
    if fix_ftp_manager():
        print("\n✅ FTP manager has been permanently fixed")
        print("   Future uploads should work correctly")
        print("\n🌐 Current working website:")
        print("   http://myfavoritemalshin.space/session_20260324_130404/verification.html")
        print("\n💡 Next steps:")
        print("   1. Run trading app for a complete 5-minute window")
        print("   2. Verification file will auto-update with trading data")
        print("   3. Website will show actual trading activity")
    else:
        print("\n❌ Fix failed - manual intervention needed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
