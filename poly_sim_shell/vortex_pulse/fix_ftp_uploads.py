#!/usr/bin/env python3
"""
Fix FTP Upload Directories
Ensures proper directory creation and file uploads.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_ftp_uploads():
    """Fix FTP upload directory creation and test with working session."""
    print("🔧 Fixing FTP upload directories...")
    
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        try:
            # Check root directory
            ftp.cwd(ftp_manager.root_dir)
            items = ftp.nlst()
            
            # Look for existing session directories
            session_dirs = [item for item in items if item.startswith("session_")]
            print(f"Found {len(session_dirs)} existing session directories")
            
            if session_dirs:
                print(f"Latest sessions: {session_dirs[:5]}")
            
            # Test directory creation
            test_dir = "test_fix_upload"
            if test_dir not in items:
                print(f"Creating test directory: {test_dir}")
                ftp.mkd(test_dir)
            
            # Upload a simple test file directly
            test_content = """<!DOCTYPE html>
<html>
<head><title>FTP Test</title></head>
<body>
    <h1>FTP Upload Test</h1>
    <p>This file was uploaded directly via FTP.</p>
    <p>Time: 2026-03-24 04:20:00</p>
</body>
</html>"""
            
            # Upload test file
            ftp.cwd(test_dir)
            from io import BytesIO
            ftp.storbinary("STOR test.html", BytesIO(test_content.encode('utf-8')))
            print("✅ Test file uploaded directly")
            
            # Now test with FTPManager for a working session
            working_session = "session_20260320_082052"
            working_file = "lg/pulse_log_5M_20260320_082052_verification.html"
            
            if os.path.exists(working_file):
                print(f"Uploading working session: {working_session}")
                ftp_manager.set_session(working_session)
                ftp_manager.upload_html_log(working_file)
                print("✅ Working session uploaded")
                
                # Upload graphs
                graphs_dir = "lg/graphs"
                if os.path.exists(graphs_dir):
                    for graph_file in os.listdir(graphs_dir)[:3]:  # Upload first 3 graphs
                        if graph_file.endswith('.svg'):
                            ftp_manager.upload_graph(
                                os.path.join(graphs_dir, graph_file), 
                                graph_file
                            )
                    print("✅ Graphs uploaded")
            
            print(f"\n🌐 Test URLs:")
            print(f"  Direct FTP test: http://myfavoritemalshin.space/{test_dir}/test.html")
            print(f"  Working session: http://myfavoritemalshin.space/{working_session}/verification.html")
            
        finally:
            ftp.quit()
            
        return 0
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(fix_ftp_uploads())
