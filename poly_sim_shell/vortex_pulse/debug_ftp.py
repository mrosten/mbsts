#!/usr/bin/env python3
"""
Debug FTP Uploads
Check exactly what's on the FTP server.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_ftp():
    print("🔍 DEBUGGING FTP UPLOADS")
    print("=" * 50)
    
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        try:
            ftp.cwd(ftp_manager.root_dir)
            print(f"📁 Root directory: {ftp_manager.root_dir}")
            
            items = ftp.nlst()
            print(f"📄 Total items: {len(items)}")
            
            # Find session directories
            session_dirs = []
            for item in items:
                if item.startswith("session_"):
                    session_dirs.append(item)
            
            print(f"📁 Session directories: {len(session_dirs)}")
            
            # Check recent sessions
            session_dirs.sort(reverse=True)
            for session_dir in session_dirs[:5]:
                print(f"\n📁 {session_dir}:")
                
                try:
                    session_path = os.path.join(ftp_manager.root_dir, session_dir)
                    ftp.cwd(session_path)
                    session_files = ftp.nlst()
                    
                    for file in session_files:
                        file_path = os.path.join(session_path, file)
                        try:
                            size = ftp.size(file_path)
                            print(f"   📄 {file} ({size} bytes)")
                        except:
                            print(f"   📄 {file} (size unknown)")
                    
                    ftp.cwd("..")
                except Exception as e:
                    print(f"   ❌ Error accessing: {e}")
            
            # Test if we can create a simple file
            print(f"\n🧪 Testing direct upload...")
            test_content = b"<html><body><h1>Test Upload</h1><p>Time: 2026-03-24 13:12:00</p></body></html>"
            
            # Create test directory
            try:
                if "debug_test" not in items:
                    ftp.mkd("debug_test")
                    print("✅ Created debug_test directory")
                
                ftp.cwd("debug_test")
                ftp.storbinary("STOR test.html", test_content)
                print("✅ Uploaded test.html")
                print("🌐 http://myfavoritemalshin.space/debug_test/test.html")
                
            except Exception as e:
                print(f"❌ Direct upload failed: {e}")
            
        finally:
            ftp.quit()
            
    except Exception as e:
        print(f"❌ FTP error: {e}")

if __name__ == "__main__":
    debug_ftp()
