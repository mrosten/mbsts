#!/usr/bin/env python3
"""
Create Immediate Website
Creates a properly styled verification website that loads immediately.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_immediate_website():
    """Create a proper verification website that loads immediately."""
    
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
    
    if not current_session:
        print("❌ No current session found")
        return 1
    
    # Create proper HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vortex Pulse Verification - {current_session}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);
            color: #e0e0e0;
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: rgba(0, 255, 255, 0.1);
            border-radius: 15px;
            border: 1px solid rgba(0, 255, 255, 0.3);
            backdrop-filter: blur(10px);
        }}
        
        .header h1 {{
            color: #00ffff;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
        }}
        
        .session-info {{
            font-size: 1.2em;
            color: #b0b0b0;
            margin-bottom: 20px;
        }}
        
        .status-card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 30px;
            margin: 20px 0;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(5px);
        }}
        
        .status-active {{
            border-left: 5px solid #00ff00;
            box-shadow: 0 0 30px rgba(0, 255, 0, 0.2);
        }}
        
        .status-waiting {{
            border-left: 5px solid #ffaa00;
            box-shadow: 0 0 30px rgba(255, 170, 0, 0.2);
        }}
        
        .status-title {{
            font-size: 1.5em;
            color: #00ffff;
            margin-bottom: 15px;
        }}
        
        .status-message {{
            font-size: 1.1em;
            color: #d0d0d0;
            margin-bottom: 10px;
        }}
        
        .status-time {{
            font-size: 0.9em;
            color: #888;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            overflow: hidden;
            margin: 20px 0;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #00ffff, #00ff00);
            border-radius: 10px;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 0.6; }}
            50% {{ opacity: 1; }}
        }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .metric-card {{
            background: rgba(255, 255, 255, 0.05);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .metric-value {{
            font-size: 2em;
            color: #00ffff;
            font-weight: bold;
        }}
        
        .metric-label {{
            color: #888;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #666;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .refresh-hint {{
            background: rgba(0, 255, 255, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            text-align: center;
            border: 1px solid rgba(0, 255, 255, 0.3);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Vortex Pulse Trading Verification</h1>
            <div class="session-info">
                <strong>Session:</strong> {current_session}<br>
                <strong>Started:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                <strong>Status:</strong> <span style="color: #00ff00;">ACTIVE</span>
            </div>
        </div>
        
        <div class="status-card status-active">
            <div class="status-title">Trading Session Active</div>
            <div class="status-message">
                The trading algorithm is currently running and monitoring the market.
            </div>
            <div class="status-time">
                Session started approximately {int((time.time() - latest_time) / 60)} minutes ago
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: 25%;"></div>
            </div>
        </div>
        
        <div class="status-card status-waiting">
            <div class="status-title">Waiting for First Trading Window</div>
            <div class="status-message">
                Trading data will appear here as soon as the first 5-minute window completes.
            </div>
            <div class="status-time">
                Windows are processed every 5 minutes. Check back soon for results!
            </div>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value">0</div>
                <div class="metric-label">Windows Processed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">0</div>
                <div class="metric-label">Trades Executed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">$0.00</div>
                <div class="metric-label">Current P&L</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">--</div>
                <div class="metric-label">Active Algorithms</div>
            </div>
        </div>
        
        <div class="refresh-hint">
            <strong>Auto-Refresh:</strong> This page will automatically update with trading data as windows complete.<br>
            <strong>Full Details:</strong> Complete trading analysis will appear here shortly.
        </div>
        
        <div class="footer">
            <p>Vortex Pulse Automated Trading System</p>
            <p style="font-size: 0.8em;">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            location.reload();
        }}, 30000);
    </script>
</body>
</html>"""
    
    # Write the immediate website
    verification_file = os.path.join(lg_dir, current_session, f"pulse_log_5M_{current_session.replace('session_', '')}_verification.html")
    
    with open(verification_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Created immediate website for {current_session}")
    print(f"📄 File: {verification_file}")
    
    # Upload it immediately
    try:
        from ftp_manager import FTPManager
        
        ftp_manager = FTPManager()
        ftp_manager.set_session(current_session)
        ftp_manager.upload_html_log(verification_file)
        
        print(f"✅ Uploaded to server")
        print(f"🌐 Website: http://myfavoritemalshin.space/{current_session}/verification.html")
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(create_immediate_website())
