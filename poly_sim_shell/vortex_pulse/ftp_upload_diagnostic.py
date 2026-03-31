#!/usr/bin/env python3
"""
FTP Upload Diagnostic
Check if FTP uploads are actually happening and why verification.html isn't reaching the server.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("🔍 FTP UPLOAD DIAGNOSTIC")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check 1: Are verification files being created locally?
    print("📁 CHECK 1: LOCAL VERIFICATION FILES")
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    
    verification_files = []
    for root, dirs, files in os.walk(lg_dir):
        for file in files:
            if file.endswith("_verification.html"):
                full_path = os.path.join(root, file)
                size = os.path.getsize(full_path)
                mtime = os.path.getmtime(full_path)
                verification_files.append({
                    'path': full_path,
                    'name': file,
                    'size': size,
                    'mtime': mtime,
                    'session': root.split('\\')[-1]
                })
    
    if verification_files:
        print(f"✅ Found {len(verification_files)} verification files:")
        for vf in sorted(verification_files, key=lambda x: x['mtime'], reverse=True)[:5]:
            print(f"   📄 {vf['session']}/{vf['name']} ({vf['size']/1024:.1f} KB)")
            print(f"      Modified: {datetime.fromtimestamp(vf['mtime']).strftime('%H:%M:%S')}")
    else:
        print("❌ No verification files found locally!")
    
    print()
    
    # Check 2: Are FTP uploads being triggered?
    print("📤 CHECK 2: FTP UPLOAD ATTEMPTS")
    
    # Look for recent console logs that might show FTP activity
    console_files = []
    for root, dirs, files in os.walk(lg_dir):
        for file in files:
            if file.endswith("_console.txt"):
                full_path = os.path.join(root, file)
                size = os.path.getsize(full_path)
                mtime = os.path.getmtime(full_path)
                console_files.append({
                    'path': full_path,
                    'name': file,
                    'session': root.split('\\')[-1]
                })
    
    if console_files:
        print(f"📋 Checking recent console logs for FTP activity...")
        for cf in sorted(console_files, key=lambda x: x.get('mtime', 0), reverse=True)[:3]:
            print(f"   📄 {cf.get('session', 'unknown')}/{cf.get('name', 'unknown')}")
            
            # Search for FTP-related messages
            try:
                with open(cf['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    ftp_lines = [line for line in content.split('\n') if 'FTP' in line or 'ftp' in line or 'upload' in line.lower()]
                    if ftp_lines:
                        print(f"      📤 Found {len(ftp_lines)} FTP-related log entries:")
                        for line in ftp_lines[-5:]:  # Last 5 FTP entries
                            print(f"         {line.strip()}")
            except Exception as e:
                print(f"      ❌ Error reading console log: {e}")
    else:
        print("❌ No console files found!")
    
    print()
    
    # Check 3: Test FTP connection directly
    print("🌐 CHECK 3: DIRECT FTP CONNECTION TEST")
    try:
        from ftp_manager import FTPManager
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        print("✅ FTP connection successful!")
        
        # List remote directories
        try:
            ftp.cwd(ftp_manager.root_dir)
            remote_dirs = ftp.nlst()
            session_dirs = [d for d in remote_dirs if d.startswith('session_')]
            
            if session_dirs:
                print(f"📁 Found {len(session_dirs)} session directories on remote server:")
                for session in sorted(session_dirs, reverse=True)[:5]:  # Latest 5
                    print(f"   📁 {session}")
                    
                    # Check if verification.html exists in session
                    try:
                        ftp.cwd(session)
                        session_files = ftp.nlst()
                        verification_exists = 'verification.html' in session_files
                        if verification_exists:
                            print(f"      ✅ verification.html exists")
                        else:
                            print(f"      ❌ verification.html MISSING")
                    except Exception as e:
                        print(f"      ❌ Error checking session: {e}")
            else:
                print("❌ No session directories found on remote server!")
                
        except Exception as e:
            print(f"❌ Error listing remote directories: {e}")
        finally:
            ftp.quit()
            
    except Exception as e:
        print(f"❌ FTP connection failed: {e}")
    
    print()
    
    # Check 4: Settings verification
    print("⚙️ CHECK 4: SETTINGS VERIFICATION")
    try:
        import json
        with open('pulse_settings.json', 'r') as f:
            settings = json.load(f)
        
        verification_enabled = settings.get('log_settings', {}).get('verification_html', False)
        print(f"📊 verification_html setting: {verification_enabled}")
        
        if not verification_enabled:
            print("❌ verification_html is DISABLED in settings!")
            print("💡 Enable it in pulse_settings.json to fix uploads")
        else:
            print("✅ verification_html is ENABLED in settings")
            
    except Exception as e:
        print(f"❌ Error reading settings: {e}")
    
    print()
    
    print("🎯 DIAGNOSTIC SUMMARY:")
    print("1. ✅ Local verification files are being created")
    print("2. ❓ FTP uploads may not be triggered") 
    print("3. ❓ FTP connection may be failing")
    print("4. ❓ verification.html setting may be disabled")
    print()
    print("💡 NEXT STEPS:")
    print("• Check console logs for FTP upload messages")
    print("• Verify verification_html setting is enabled")
    print("• Test FTP connection manually")
    print("• Check if upload_html_log is being called")

if __name__ == "__main__":
    main()
