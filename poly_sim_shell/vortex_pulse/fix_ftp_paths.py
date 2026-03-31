#!/usr/bin/env python3
"""
Fix FTP Path Issue
Fixes the Windows path issue in FTP uploads.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_ftp_paths():
    print("🔧 Fixing FTP Path Issues...")
    
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        try:
            # Navigate to root directory
            ftp.cwd(ftp_manager.root_dir)
            print(f"✅ Connected to: {ftp_manager.root_dir}")
            
            # Create session directory with proper path
            current_session = "session_20260324_130404"
            
            # Try to create directory directly
            try:
                ftp.mkd(current_session)
                print(f"✅ Created directory: {current_session}")
            except:
                print(f"📁 Directory exists: {current_session}")
            
            # Navigate to session directory
            ftp.cwd(current_session)
            print(f"✅ Changed to: {current_session}")
            
            # Upload verification file directly
            verification_file = "lg/session_20260324_130404/pulse_log_5M_20260324_130404_verification.html"
            
            if os.path.exists(verification_file):
                with open(verification_file, 'rb') as f:
                    ftp.storbinary("STOR verification.html", f)
                print("✅ Uploaded verification.html")
                
                # Create graphs directory
                try:
                    ftp.mkd("graphs")
                    print("✅ Created graphs directory")
                except:
                    print("📁 Graphs directory exists")
                
                # Upload graphs
                graphs_dir = "lg/session_20260324_130404/graphs"
                if os.path.exists(graphs_dir):
                    for graph_file in os.listdir(graphs_dir)[:3]:
                        if graph_file.endswith('.svg'):
                            ftp.cwd("graphs")
                            with open(os.path.join(graphs_dir, graph_file), 'rb') as f:
                                ftp.storbinary(f"STOR {graph_file}", f)
                            print(f"✅ Uploaded {graph_file}")
                            ftp.cwd("..")
                
                print(f"\n🌐 Website should be available at:")
                print(f"   http://myfavoritemalshin.space/{current_session}/verification.html")
            else:
                print(f"❌ Verification file not found: {verification_file}")
            
        finally:
            ftp.quit()
            
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(fix_ftp_paths())
