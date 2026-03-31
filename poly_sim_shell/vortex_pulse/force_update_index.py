#!/usr/bin/env python3
"""
Force Update Index Script
Manually triggers index.html update to refresh session listing with latest sessions.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ftp_manager import FTPManager

def main():
    print("🔄 Forcing index.html update...")
    
    try:
        # Initialize FTP manager with default config (will use config.py variables)
        ftp_manager = FTPManager()
        
        # Force update index
        ftp_manager.force_update_index()
        print("✅ Index update triggered successfully!")
        print("📊 Check http://myfavoritemalshin.space/index.html in a few moments")
        
    except Exception as e:
        print(f"❌ Failed to update index: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
