#!/usr/bin/env python3
"""
Force Upload Verification Files
Ensures all recent verification files are uploaded and accessible.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def upload_recent_sessions():
    """Upload recent sessions with trading data."""
    print("📤 Uploading recent verification files...")
    
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        
        # Find sessions with actual trading data
        lg_dir = os.path.join(os.path.dirname(__file__), "lg")
        uploaded_sessions = []
        
        for root, dirs, files in os.walk(lg_dir):
            for file in files:
                if file.endswith("_verification.html"):
                    file_path = os.path.join(root, file)
                    
                    # Check if file has trading data
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            
                        if "class='match'" in content and "No trading activity recorded" not in content:
                            # Extract session ID
                            session_id = None
                            path_parts = file_path.split(os.sep)
                            for part in path_parts:
                                if part.startswith("session_"):
                                    session_id = part
                                    break
                            
                            if session_id and session_id not in uploaded_sessions:
                                print(f"📄 Uploading {session_id}...")
                                ftp_manager.set_session(session_id)
                                ftp_manager.upload_html_log(file_path)
                                uploaded_sessions.append(session_id)
                                
                                # Also upload graphs if they exist
                                graphs_dir = os.path.join(root, "graphs")
                                if os.path.exists(graphs_dir):
                                    for graph_file in os.listdir(graphs_dir):
                                        if graph_file.endswith('.svg'):
                                            ftp_manager.upload_graph(
                                                os.path.join(graphs_dir, graph_file), 
                                                graph_file
                                            )
                                
                                print(f"✅ Uploaded {session_id}")
                                
                    except Exception as e:
                        print(f"❌ Error processing {file_path}: {e}")
        
        if uploaded_sessions:
            print(f"\n🎯 Uploaded {len(uploaded_sessions)} sessions:")
            for session in uploaded_sessions:
                url = f"http://myfavoritemalshin.space/{session}/verification.html"
                print(f"  🌐 {url}")
        else:
            print("❌ No sessions with trading data found")
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return 1
    
    return 0

def check_website_access():
    """Check if uploaded websites are accessible."""
    print("\n🌐 Checking website access...")
    
    try:
        import requests
        
        # Test the working session we know exists
        test_urls = [
            "http://myfavoritemalshin.space/session_20260320_082052/verification.html",
            "http://myfavoritemalshin.space/index.html"
        ]
        
        for url in test_urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    if "class='match'" in response.text:
                        print(f"✅ {url} - Has trading data")
                    else:
                        print(f"⚠️  {url} - No trading data")
                else:
                    print(f"❌ {url} - HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ {url} - {e}")
                
    except ImportError:
        print("⚠️  requests module not available for website checking")

def main():
    print("🔧 Force Upload Verification Files")
    print("=" * 50)
    
    # Upload recent sessions
    upload_recent_sessions()
    
    # Check website access
    check_website_access()
    
    print(f"\n📋 Summary:")
    print(f"  • Recent verification files uploaded")
    print(f"  • Websites checked for accessibility")
    print(f"\n💡 To monitor live uploads, run: python monitor_audit_uploads.py")

if __name__ == "__main__":
    sys.exit(main())
