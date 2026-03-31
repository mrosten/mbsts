#!/usr/bin/env python3
"""
Manual FTP Upload
Manually upload the verification file to fix the missing website.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def manual_ftp_upload():
    """Manually upload verification file to FTP."""
    print("📤 MANUAL FTP UPLOAD")
    print("=" * 50)
    
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        session_id = "session_20260327_072057"
        verification_file = f"pulse_log_5M_{session_id.replace('session_', '')}_verification.html"
        local_path = os.path.join(os.path.dirname(__file__), "lg", session_id, verification_file)
        
        print(f"📁 Local file: {local_path}")
        print(f"📊 File size: {os.path.getsize(local_path) / 1024:.1f} KB")
        
        # Create remote directory
        try:
            ftp.mkd(session_id)
            print(f"📁 Created remote directory: {session_id}")
        except:
            print(f"📁 Remote directory exists: {session_id}")
        
        # Upload verification file
        remote_path = f"{session_id}/{verification_file}"
        
        with open(local_path, 'rb') as f:
            ftp.storbinary(f"STOR {remote_path}", f)
        
        print(f"✅ Uploaded: {remote_path}")
        
        # Create graphs directory
        try:
            ftp.mkd(f"{session_id}/graphs")
            print(f"📁 Created graphs directory")
        except:
            print(f"📁 Graphs directory exists")
        
        ftp.quit()
        
        print(f"\n🌐 Website: http://myfavoritemalshin.space/{session_id}/verification.html")
        print(f"🎉 FTP upload complete!")
        
        return True
        
    except Exception as e:
        print(f"❌ FTP upload failed: {e}")
        return False

def main():
    print("🔧 MANUAL VERIFICATION FILE UPLOAD")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = manual_ftp_upload()
    
    if success:
        print(f"\n✅ SUCCESS!")
        print(f"📋 The verification website should now be accessible")
        print(f"🌐 http://myfavoritemalshin.space/session_20260327_072057/verification.html")
    else:
        print(f"\n❌ UPLOAD FAILED!")
        print(f"💡 Check FTP credentials and connection")

if __name__ == "__main__":
    main()
