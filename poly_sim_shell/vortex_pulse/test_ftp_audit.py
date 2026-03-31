#!/usr/bin/env python3
"""
Test FTP Upload for Audit Website
Tests if verification.html files are being uploaded correctly.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ftp_manager import FTPManager

def test_ftp_upload():
    print("🔍 Testing FTP upload for audit website...")
    
    try:
        # Initialize FTP manager
        ftp_manager = FTPManager()
        
        # Set a test session
        ftp_manager.set_session("test_session_123")
        
        # Find the most recent verification.html file
        lg_dir = os.path.join(os.path.dirname(__file__), "lg")
        latest_html = None
        latest_time = 0
        
        for root, dirs, files in os.walk(lg_dir):
            for file in files:
                if file.endswith("_verification.html"):
                    file_path = os.path.join(root, file)
                    file_time = os.path.getmtime(file_path)
                    if file_time > latest_time:
                        latest_time = file_time
                        latest_html = file_path
        
        if latest_html:
            print(f"📄 Found latest HTML: {latest_html}")
            
            # Test upload
            print("📤 Testing upload...")
            ftp_manager.upload_html_log(latest_html)
            print("✅ Upload queued successfully")
            
            # Check if we can access it on the remote server
            print("🌐 Checking remote access...")
            import requests
            test_url = "http://myfavoritemalshin.space/test_session_123/verification.html"
            try:
                response = requests.get(test_url, timeout=10)
                if response.status_code == 200:
                    print("✅ Website accessible!")
                    print(f"📊 Check: {test_url}")
                else:
                    print(f"❌ HTTP {response.status_code}: {test_url}")
            except Exception as e:
                print(f"❌ Cannot access website: {e}")
                
        else:
            print("❌ No verification.html files found")
            
    except Exception as e:
        print(f"❌ FTP Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(test_ftp_upload())
