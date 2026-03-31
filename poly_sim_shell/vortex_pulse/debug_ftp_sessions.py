#!/usr/bin/env python3
"""
Debug FTP Sessions Script
Lists what sessions are actually available on remote FTP server.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ftp_manager import FTPManager

def main():
    print("🔍 Debugging FTP sessions...")
    
    try:
        # Initialize FTP manager
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        try:
            ftp.cwd(ftp_manager.root_dir)
        except:
            pass
        
        # List all directories
        try:
            items = [name for name, facts in ftp.mlsd() if facts['type'] == 'dir']
            print(f"✅ Found {len(items)} directories via MLSD")
        except Exception as e:
            print(f"⚠️  MLSD failed: {e}, trying NLST...")
            items = ftp.nlst()
            print(f"✅ Found {len(items)} items via NLST")
        
        # Filter sessions
        sessions = [item for item in items if "session_" in item]
        print(f"\n📊 Found {len(sessions)} session directories:")
        
        # Sort and show newest 10
        def parse_session_time(session_id):
            try:
                timestamp_str = session_id.replace("session_", "")
                return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except:
                return datetime.min
        
        sessions.sort(key=parse_session_time, reverse=True)
        
        for i, session in enumerate(sessions[:15]):
            print(f"  {i+1:2d}. {session}")
        
        if len(sessions) > 15:
            print(f"  ... and {len(sessions) - 15} more")
            
        ftp.quit()
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    from datetime import datetime
    sys.exit(main())
