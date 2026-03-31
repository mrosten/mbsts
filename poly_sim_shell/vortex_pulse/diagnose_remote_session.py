import ftplib
import os
import sys
from datetime import datetime

# Add current dir to path for config import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

def diagnose_session(session_id):
    print(f"DIAGNOSING SESSION: {session_id}")
    print("=" * 60)
    
    try:
        print(f"Connecting to FTP: {config.FTP_HOST}...")
        ftp = ftplib.FTP(config.FTP_HOST)
        ftp.login(config.FTP_USER, config.FTP_PASS)
        print("Login successful")
        
        print(f"Changing to root: {config.FTP_ROOT}...")
        ftp.cwd(config.FTP_ROOT)
        
        # 1. Check if session directory exists
        print(f"Checking for directory: {session_id}...")
        items = ftp.nlst()
        if session_id in items:
            print(f"Directory '{session_id}' exists on server")
            
            # 2. List contents of session directory
            print(f"Listing contents of '{session_id}':")
            ftp.cwd(session_id)
            session_items = ftp.nlst()
            for item in session_items:
                if item in ['.', '..']:
                    print(f"  - {item} (DIR)")
                    continue
                try:
                    size = ftp.size(item)
                    print(f"  - {item} ({size} bytes)")
                except:
                    print(f"  - {item} (Unknown type/DIR)")
            
            # Check for verification.html
            if "verification.html" in session_items:
                print(" 'verification.html' EXISTS")
            else:
                print(" 'verification.html' IS MISSING")
                # Look for variations
                for item in session_items:
                    if "verification" in item.lower():
                        print(f"Found potential match: {item}")
        else:
            print(f"Directory '{session_id}' NOT FOUND in root")
            # Suggest closest matches
            print("Directories found (first 10):")
            for i, item in enumerate(items[:10]):
                print(f"  - {item}")
                
        ftp.quit()
        print("\nDiagnosis complete")
        
    except Exception as e:
        print(f"Error during diagnosis: {e}")

if __name__ == "__main__":
    target_session = "session_20260328_101642"
    diagnose_session(target_session)
