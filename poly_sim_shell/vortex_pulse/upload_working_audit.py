#!/usr/bin/env python3
"""
Upload Working Audit Website
Uploads a session with actual trading data to test the website.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ftp_manager import FTPManager

def main():
    print("📤 Uploading working audit website...")
    
    try:
        # Find a session with actual trading data
        working_html = "lg/pulse_log_5M_20260320_082052_verification.html"
        
        if os.path.exists(working_html):
            print(f"📄 Found working HTML: {working_html}")
            
            # Initialize FTP and upload
            ftp_manager = FTPManager()
            ftp_manager.set_session("session_20260320_082052")
            ftp_manager.upload_html_log(working_html)
            
            print("✅ Upload complete!")
            print("🌐 Check: http://myfavoritemalshin.space/session_20260320_082052/verification.html")
            
            # Also upload graphs
            graphs_dir = "lg/graphs"
            if os.path.exists(graphs_dir):
                for file in os.listdir(graphs_dir):
                    if file.endswith('.svg'):
                        ftp_manager.upload_graph(os.path.join(graphs_dir, file), file)
                print("✅ Graphs uploaded!")
            
        else:
            print(f"❌ Working HTML not found: {working_html}")
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
