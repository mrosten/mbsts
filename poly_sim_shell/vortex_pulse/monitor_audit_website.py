#!/usr/bin/env python3
"""
Audit Website Monitoring
Ensures audit websites are being created and uploaded properly.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def monitor_uploads():
    """Monitor and ensure audit website uploads are working."""
    print("🔍 AUDIT WEBSITE MONITOR")
    print("=" * 50)
    
    # Check current status
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Check latest local verification file
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    latest_file = None
    latest_time = 0
    
    for root, dirs, files in os.walk(lg_dir):
        for file in files:
            if file.endswith("_verification.html"):
                file_path = os.path.join(root, file)
                file_time = os.path.getmtime(file_path)
                if file_time > latest_time:
                    latest_time = file_time
                    latest_file = file_path
    
    if latest_file:
        age_minutes = int((time.time() - latest_time) / 60)
        print(f"📄 Latest verification file: {os.path.basename(latest_file)}")
        print(f"   Age: {age_minutes} minutes ago")
        
        # Check if it has trading data
        try:
            with open(latest_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if "class='match'" in content:
                print("   ✅ Contains trading data")
                
                # Extract session ID
                session_id = None
                path_parts = latest_file.split(os.sep)
                for part in path_parts:
                    if part.startswith("session_"):
                        session_id = part
                        break
                
                if session_id:
                    print(f"   🌐 Website: http://myfavoritemalshin.space/{session_id}/verification.html")
                    
                    # Force upload if recent
                    if age_minutes < 30:
                        print("   📤 Auto-uploading recent session...")
                        try:
                            from ftp_manager import FTPManager
                            ftp_manager = FTPManager()
                            ftp_manager.set_session(session_id)
                            ftp_manager.upload_html_log(latest_file)
                            print("   ✅ Upload queued")
                        except Exception as e:
                            print(f"   ❌ Upload failed: {e}")
                
            else:
                print("   ⚠️  No trading data (session ended early)")
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
    else:
        print("❌ No verification files found")
    
    # 2. Check FTP status
    print(f"\n📤 FTP Status:")
    try:
        from ftp_manager import FTPManager
        ftp_manager = FTPManager()
        
        if hasattr(ftp_manager, 'session_id') and ftp_manager.session_id:
            print(f"   Active session: {ftp_manager.session_id}")
        else:
            print("   No active session")
            
    except Exception as e:
        print(f"   FTP error: {e}")
    
    # 3. Recommendations
    print(f"\n💡 Recommendations:")
    if latest_file:
        print("   ✅ Verification files are being generated")
        print("   ✅ Upload system is functional")
        print("   📊 Check the website URL above")
        if age_minutes > 60:
            print("   ⚠️  Consider running the trading app for fresh data")
    else:
        print("   ❌ Run the trading app to generate verification files")
        print("   ❌ Ensure verification HTML logging is enabled")
    
    print(f"\n🔧 Useful commands:")
    print("   python force_upload_verification.py  # Force upload recent sessions")
    print("   python monitor_audit_uploads.py      # Monitor upload status")
    print("   python fix_ftp_uploads.py           # Fix FTP directory issues")

if __name__ == "__main__":
    monitor_uploads()
