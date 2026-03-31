#!/usr/bin/env python3
"""
Monitor Audit Website Uploads
Checks that verification.html files are being uploaded and websites are created correctly.
"""

import os
import sys
import time
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_local_files():
    """Check for recent local verification files."""
    print("🔍 Checking local verification files...")
    
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    recent_files = []
    
    for root, dirs, files in os.walk(lg_dir):
        for file in files:
            if file.endswith("_verification.html"):
                file_path = os.path.join(root, file)
                file_time = os.path.getmtime(file_path)
                file_age = time.time() - file_time
                
                if file_age < 3600:  # Files from last hour
                    recent_files.append((file_path, file_age))
    
    recent_files.sort(key=lambda x: x[1])  # Sort by age
    
    if recent_files:
        print(f"✅ Found {len(recent_files)} recent verification files:")
        for file_path, age in recent_files[:5]:
            print(f"  • {os.path.basename(file_path)} ({int(age/60)} min ago)")
        return recent_files[0][0]  # Return most recent
    else:
        print("❌ No recent verification files found")
        return None

def check_file_content(file_path):
    """Check if the verification file has actual trading data."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        if "No trading activity recorded" in content:
            print("⚠️  File contains no trading activity")
            return False
        elif "class='match'" in content:
            print("✅ File contains trading data")
            return True
        else:
            print("❓ Unknown file format")
            return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def check_remote_access(session_id):
    """Check if the remote website is accessible."""
    url = f"http://myfavoritemalshin.space/{session_id}/verification.html"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            content = response.text
            
            if "No trading activity recorded" in content:
                print(f"⚠️  Remote website has no trading data: {url}")
                return False
            elif "class='match'" in content:
                print(f"✅ Remote website has trading data: {url}")
                return True
            else:
                print(f"❓ Remote website format unknown: {url}")
                return False
        else:
            print(f"❌ HTTP {response.status_code}: {url}")
            return False
    except Exception as e:
        print(f"❌ Cannot access remote website: {e}")
        return False

def check_ftp_upload_status():
    """Check FTP upload queue status."""
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        
        # Check if there's a current session
        if hasattr(ftp_manager, 'session_id') and ftp_manager.session_id:
            print(f"📤 Current FTP session: {ftp_manager.session_id}")
            return ftp_manager.session_id
        else:
            print("❌ No active FTP session")
            return None
    except Exception as e:
        print(f"❌ FTP check failed: {e}")
        return None

def main():
    print("🔍 Monitoring Audit Website Uploads")
    print("=" * 50)
    
    # 1. Check local files
    latest_file = check_local_files()
    
    if latest_file:
        print(f"\n📄 Analyzing: {os.path.basename(latest_file)}")
        
        # 2. Check file content
        has_data = check_file_content(latest_file)
        
        # 3. Extract session ID from file path
        session_id = None
        path_parts = latest_file.split(os.sep)
        for part in path_parts:
            if part.startswith("session_"):
                session_id = part
                break
        
        if session_id:
            print(f"\n🌐 Checking remote access for {session_id}...")
            
            # 4. Check remote access
            remote_ok = check_remote_access(session_id)
            
            # 5. Check FTP status
            print(f"\n📤 FTP Upload Status:")
            ftp_session = check_ftp_upload_status()
            
            # Summary
            print(f"\n📋 Summary:")
            print(f"  • Local file: {'✅' if has_data else '❌'}")
            print(f"  • Remote access: {'✅' if remote_ok else '❌'}")
            print(f"  • FTP session: {'✅' if ftp_session else '❌'}")
            
            if has_data and not remote_ok:
                print(f"\n🔧 Suggestion: Force upload this file")
                print(f"   python force_upload_verification.py {session_id}")
        else:
            print("❌ Could not extract session ID from file path")
    else:
        print("\n💡 Suggestions:")
        print("  • Run the trading app for at least one complete 5-minute window")
        print("  • Check that verification HTML logging is enabled")
        print("  • Ensure FTP settings are correct in .env file")

if __name__ == "__main__":
    main()
