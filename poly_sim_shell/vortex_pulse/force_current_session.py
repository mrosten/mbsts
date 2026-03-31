#!/usr/bin/env python3
"""
Force Upload Current Session
Uploads the current session even if it has no trading data yet.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("📤 Force Uploading Current Session")
    
    # Find current session
    lg_dir = os.path.join(os.path.dirname(__file__), "lg")
    current_session = None
    latest_time = 0
    
    for item in os.listdir(lg_dir):
        if os.path.isdir(os.path.join(lg_dir, item)) and item.startswith("session_"):
            session_path = os.path.join(lg_dir, item)
            session_time = os.path.getmtime(session_path)
            
            if session_time > latest_time:
                latest_time = session_time
                current_session = item
    
    if current_session:
        print(f"📁 Found session: {current_session}")
        
        # Find verification file
        verification_file = None
        for file in os.listdir(os.path.join(lg_dir, current_session)):
            if file.endswith("_verification.html"):
                verification_file = os.path.join(lg_dir, current_session, file)
                break
        
        if verification_file:
            print(f"📄 Verification file: {os.path.basename(verification_file)}")
            
            # Upload it
            try:
                from ftp_manager import FTPManager
                
                ftp_manager = FTPManager()
                ftp_manager.set_session(current_session)
                ftp_manager.upload_html_log(verification_file)
                
                print("✅ Upload complete!")
                print(f"🌐 Website: http://myfavoritemalshin.space/{current_session}/verification.html")
                
                # Also upload graphs if they exist
                graphs_dir = os.path.join(lg_dir, current_session, "graphs")
                if os.path.exists(graphs_dir):
                    graph_files = [f for f in os.listdir(graphs_dir) if f.endswith('.svg')]
                    if graph_files:
                        print(f"📈 Uploading {len(graph_files)} graphs...")
                        for graph_file in graph_files[:5]:  # First 5 graphs
                            ftp_manager.upload_graph(
                                os.path.join(graphs_dir, graph_file), 
                                graph_file
                            )
                        print("✅ Graphs uploaded!")
                
                print(f"\n📊 Status: Website will show 'No trading activity' until")
                print(f"   the trading app completes at least one 5-minute window.")
                print(f"   This is normal for new sessions.")
                
            except Exception as e:
                print(f"❌ Upload failed: {e}")
                return 1
        else:
            print("❌ No verification file found")
    else:
        print("❌ No current session found")
        print("💡 Start the trading app first")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
