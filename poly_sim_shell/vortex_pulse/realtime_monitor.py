#!/usr/bin/env python3
"""
Real-Time Audit Monitor
Checks actual current session status and uploads in real-time.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def find_current_session():
    """Find the most recent session directory."""
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    
    current_session = None
    latest_time = 0
    
    # Look for session directories
    for item in os.listdir(lg_dir):
        if os.path.isdir(os.path.join(lg_dir, item)) and item.startswith("session_"):
            session_path = os.path.join(lg_dir, item)
            session_time = os.path.getmtime(session_path)
            
            if session_time > latest_time:
                latest_time = session_time
                current_session = item
    
    return current_session, latest_time

def check_session_files(session_id):
    """Check all files in current session."""
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    session_path = os.path.join(lg_dir, session_id)
    
    if not os.path.exists(session_path):
        return {}
    
    files = {}
    for file in os.listdir(session_path):
        file_path = os.path.join(session_path, file)
        if os.path.isfile(file_path):
            file_time = os.path.getmtime(file_path)
            file_size = os.path.getsize(file_path)
            files[file] = {
                'time': file_time,
                'size': file_size,
                'age_minutes': int((time.time() - file_time) / 60)
            }
    
    return files

def check_current_uploads():
    """Check what's currently uploaded to FTP."""
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        try:
            ftp.cwd(ftp_manager.root_dir)
            items = ftp.nlst()
            
            # Find session directories
            session_dirs = []
            for item in items:
                if item.startswith("session_"):
                    session_path = os.path.join(ftp_manager.root_dir, item)
                    try:
                        ftp.cwd(session_path)
                        session_files = ftp.nlst()
                        session_dirs.append((item, session_files))
                        ftp.cwd("..")
                    except:
                        pass
            
            ftp.quit()
            return session_dirs
            
        except Exception as e:
            print(f"FTP check error: {e}")
            return []
            
    except Exception as e:
        print(f"FTP connection error: {e}")
        return []

def main():
    print("🔍 REAL-TIME AUDIT MONITOR")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Find current session
    current_session, session_time = find_current_session()
    
    if current_session:
        age_minutes = int((time.time() - session_time) / 60)
        print(f"📁 Current Session: {current_session}")
        print(f"   Started: {age_minutes} minutes ago")
        print(f"   Path: lg/{current_session}/")
        
        # 2. Check session files
        files = check_session_files(current_session)
        
        print(f"\n📄 Session Files:")
        for filename, info in sorted(files.items(), key=lambda x: x[1]['time'], reverse=True):
            age = info['age_minutes']
            size_kb = info['size'] / 1024
            
            if filename.endswith("_verification.html"):
                status = "🔍 VERIFICATION"
                if size_kb > 10:  # More than 10KB means it has data
                    status += " ✅ HAS DATA"
                else:
                    status += " ⚠️  EMPTY/SMALL"
            elif filename.endswith("_console.txt"):
                status = "📝 CONSOLE LOG"
            elif filename.endswith(".csv"):
                status = "📊 CSV DATA"
            else:
                status = f"📄 {filename}"
            
            print(f"   {status} - {age:3d} min ago - {size_kb:6.1f} KB")
        
        # 3. Check FTP uploads
        print(f"\n📤 FTP Status:")
        uploaded_sessions = check_current_uploads()
        
        if uploaded_sessions:
            print(f"   Found {len(uploaded_sessions)} uploaded sessions")
            
            # Check if current session is uploaded
            current_uploaded = any(session[0] == current_session for session in uploaded_sessions)
            
            if current_uploaded:
                print(f"   ✅ {current_session} is uploaded")
                
                # Check if verification.html exists
                for session_id, session_files in uploaded_sessions:
                    if session_id == current_session:
                        if "verification.html" in session_files:
                            print(f"   ✅ verification.html exists on server")
                            print(f"   🌐 http://myfavoritemalshin.space/{current_session}/verification.html")
                        else:
                            print(f"   ❌ verification.html missing on server")
                        break
            else:
                print(f"   ❌ {current_session} NOT uploaded yet")
                print(f"   💡 Run: python force_upload_verification.py")
        else:
            print("   ❌ No sessions found on server")
    
    else:
        print("❌ No current session found")
        print("💡 Start the trading app to create a session")
    
    print(f"\n🔧 Quick Actions:")
    print("   force_upload_verification.py - Upload current session")
    print("   fix_ftp_uploads.py - Fix FTP issues")
    print("   monitor_audit_website.py - Check status")

if __name__ == "__main__":
    main()
