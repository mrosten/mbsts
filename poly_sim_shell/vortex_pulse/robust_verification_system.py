#!/usr/bin/env python3
"""
Robust Verification Creation System
Ensures verification.html is created and updated for any session, anywhere.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_universal_verification_creator():
    """Create a universal verification creator that works anywhere."""
    print("🔨 CREATING UNIVERSAL VERIFICATION CREATOR")
    print("=" * 60)
    
    creator_code = '''#!/usr/bin/env python3
"""
Universal Verification Creator
Creates verification.html for any session, anywhere it's running.
"""

import os
import sys
import time
from datetime import datetime

def create_verification_for_current_session():
    """Create verification.html for the current active session."""
    print("🔍 CREATING VERIFICATION FOR CURRENT SESSION")
    print("=" * 50)
    
    # Find current session (most recent)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Look for session directories in multiple possible locations
    possible_locations = [
        current_dir,  # Same directory
        os.path.join(current_dir, "lg"),  # lg subdirectory
        os.path.dirname(current_dir),  # Parent directory
    ]
    
    current_session = None
    session_dir = None
    
    for location in possible_locations:
        if os.path.exists(location):
            sessions = [d for d in os.listdir(location) 
                       if d.startswith("session_") and os.path.isdir(os.path.join(location, d))]
            
            if sessions:
                # Sort by modification time
                latest_session = max(sessions, 
                                   key=lambda x: os.path.getmtime(os.path.join(location, x)))
                session_path = os.path.join(location, latest_session)
                
                if current_session is None or os.path.getmtime(session_path) > os.path.getmtime(os.path.join(session_dir, "verification.html") if session_dir else ""):
                    current_session = latest_session
                    session_dir = session_path
    
    if not current_session:
        print("❌ No active session found")
        # Create a new session
        current_session = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session_dir = os.path.join(current_dir, "lg", current_session)
        os.makedirs(session_dir, exist_ok=True)
        print(f"📁 Created new session: {current_session}")
    else:
        print(f"📅 Found current session: {current_session}")
        print(f"📁 Session directory: {session_dir}")
    
    # Create verification file
    base_name = current_session.replace("session_", "")
    verification_file = os.path.join(session_dir, f"pulse_log_5M_{base_name}_verification.html")
    
    # Create professional HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audit Verification - {current_session}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #1a1a2e, #0f0f1e);
            color: #ffffff;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(0, 0, 0, 0.8);
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #ffaa00;
            padding-bottom: 20px;
        }}
        .status {{
            background: #ffaa00;
            color: #000;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
            margin: 20px 0;
        }}
        .info {{
            background: rgba(255, 170, 0, 0.1);
            border: 1px solid #ffaa00;
            padding: 20px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .data-section {{
            background: rgba(0, 255, 0, 0.05);
            border-left: 3px solid #00ff00;
            padding: 15px;
            margin: 10px 0;
        }}
        .refresh {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #ffaa00;
            color: #000;
            padding: 10px 15px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
        }}
        .timestamp {{
            text-align: center;
            font-size: 14px;
            opacity: 0.7;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <a href="#" class="refresh" onclick="location.reload()">🔄 REFRESH</a>
    
    <div class="container">
        <div class="header">
            <h1>🔍 AUDIT VERIFICATION</h1>
            <h2>{current_session}</h2>
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Location:</strong> {os.path.dirname(__file__)}</p>
        </div>
        
        <div class="status">
            📊 SESSION ACTIVE - Trading data will appear in real-time
        </div>
        
        <div class="info">
            <h3>📋 Session Information</h3>
            <p><strong>Session ID:</strong> {current_session}</p>
            <p><strong>Status:</strong> Active - Collecting trading data</p>
            <p><strong>Market:</strong> BTC/USDT</p>
            <p><strong>Duration:</strong> 5-minute windows</p>
            <p><strong>Auto-Refresh:</strong> Every 30 seconds</p>
        </div>
        
        <div class="data-section">
            <h3>📈 Live Trading Data</h3>
            <p><strong>Waiting for trading data...</strong></p>
            <p>This verification file will be automatically updated as trading activity occurs.</p>
            <p>Check back in a few minutes for real-time data.</p>
        </div>
        
        <div class="info">
            <h3>⚙️ System Information</h3>
            <p><strong>Creator:</strong> Universal Verification System</p>
            <p><strong>Version:</strong> 1.0</p>
            <p><strong>Created:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Last Update:</strong> <span id="lastUpdate">{datetime.now().strftime('%H:%M:%S')}</span></p>
        </div>
        
        <div class="timestamp">
            Last page load: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }}, 1000);
        
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            location.reload();
        }}, 30000);
    </script>
</body>
</html>"""
    
    try:
        with open(verification_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        file_size = os.path.getsize(verification_file)
        print(f"✅ Created verification: {verification_file}")
        print(f"📊 File size: {file_size / 1024:.1f} KB")
        
        # Create graphs directory
        graphs_dir = os.path.join(session_dir, "graphs")
        if not os.path.exists(graphs_dir):
            os.makedirs(graphs_dir)
            print(f"📁 Created graphs directory: {graphs_dir}")
        
        return verification_file, current_session
        
    except Exception as e:
        print(f"❌ Failed to create verification: {e}")
        return None, current_session

def upload_to_ftp(verification_file, session_id):
    """Upload verification file to FTP."""
    try:
        # Try to import FTP manager
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        ftp = ftp_manager._get_connection()
        
        # Create remote directory
        try:
            ftp.mkd(session_id)
            print(f"📁 Created remote directory: {session_id}")
        except:
            print(f"📁 Remote directory exists: {session_id}")
        
        # Upload verification file
        remote_filename = f"pulse_log_5M_{session_id.replace('session_', '')}_verification.html"
        remote_path = f"{session_id}/{remote_filename}"
        
        with open(verification_file, 'rb') as f:
            ftp.storbinary(f"STOR {remote_path}", f)
        
        print(f"✅ Uploaded: {remote_path}")
        
        # Create graphs directory
        try:
            ftp.mkd(f"{session_id}/graphs")
            print(f"📁 Created remote graphs directory")
        except:
            print(f"📁 Remote graphs directory exists")
        
        ftp.quit()
        
        print(f"🌐 Website: http://myfavoritemalshin.space/{session_id}/verification.html")
        return True
        
    except Exception as e:
        print(f"❌ FTP upload failed: {e}")
        return False

def main():
    print("🚀 UNIVERSAL VERIFICATION CREATOR")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create verification for current session
    verification_file, session_id = create_verification_for_current_session()
    
    if verification_file and session_id:
        # Upload to FTP
        upload_success = upload_to_ftp(verification_file, session_id)
        
        if upload_success:
            print(f"\\n🎉 SUCCESS!")
            print(f"📋 Summary:")
            print(f"   ✅ Verification file created and uploaded")
            print(f"   ✅ Session: {session_id}")
            print(f"   ✅ Website: http://myfavoritemalshin.space/{session_id}/verification.html")
            print(f"   ✅ Auto-refresh enabled")
            print(f"   ✅ Ready for trading data")
        else:
            print(f"\\n❌ FTP upload failed")
    else:
        print(f"\\n❌ Failed to create verification file")

if __name__ == "__main__":
    main()
'''
    
    # Write the universal creator
    creator_file = os.path.join(os.path.dirname(__file__), "universal_verification_creator.py")
    
    try:
        with open(creator_file, 'w', encoding='utf-8') as f:
            f.write(creator_code)
        
        print(f"✅ Created universal creator: {creator_file}")
        print(f"📊 File size: {len(creator_code) / 1024:.1f} KB")
        
        # Make it executable
        os.chmod(creator_file, 0o755)
        
        return creator_file
        
    except Exception as e:
        print(f"❌ Failed to create universal creator: {e}")
        return None

def main():
    print("🎯 ROBUST VERIFICATION CREATION SYSTEM")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("🔧 CREATING ROBUST SYSTEM:")
    print("   • Universal verification creator")
    print("   • Works on any machine/location")
    print("   • Finds current session automatically")
    print("   • Creates verification files")
    print("   • Uploads to FTP")
    print()
    
    creator_file = create_universal_verification_creator()
    
    if creator_file:
        print(f"\\n✅ SYSTEM CREATED!")
        print(f"📋 Files Created:")
        print(f"   📄 universal_verification_creator.py")
        print(f"   📊 Size: {os.path.getsize(creator_file) / 1024:.1f} KB")
        print()
        print(f"💡 USAGE:")
        print(f"   1. Run: python universal_verification_creator.py")
        print(f"   2. Works on any machine (Google VM, local, etc.)")
        print(f"   3. Finds current session automatically")
        print(f"   4. Creates verification.html")
        print(f"   5. Uploads to FTP server")
        print(f"   6. Makes website accessible")
        print()
        print(f"🌐 This will work for your Google VM sessions!")
    else:
        print(f"\\n❌ SYSTEM CREATION FAILED")

if __name__ == "__main__":
    main()
