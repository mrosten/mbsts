import os
import ftplib
import threading
import logging
import queue
import time
from datetime import datetime
try:
    from . import config
except ImportError:
    import config

# Set up logging for FTP operations
logger = logging.getLogger("vortex_ftp")
logger.setLevel(logging.INFO)

class FTPManager:
    """
    Manages asynchronous FTP uploads for HTML logs and session index.
    """
    def __init__(self, host=None, user=None, passwd=None, root_dir=None, logger_func=None):
        self.host = host or config.FTP_HOST
        self.user = user or config.FTP_USER
        self.passwd = passwd or config.FTP_PASS
        self.root_dir = root_dir or config.FTP_ROOT
        self.logger_func = logger_func
        
        self.upload_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        self.session_id = None
        self.remote_session_dir = None
        
        # Rate limiting for index updates (prevent excessive uploads)
        self.last_index_update = 0
        self.min_index_update_interval = 300  # 5 minutes minimum between index updates

    def _log(self, msg, level="INFO"):
        if self.logger_func:
            # Check if the logger_func supports a level argument (PulseApp.log_msg does)
            try:
                self.logger_func(f"[FTP] {msg}", level=level)
            except TypeError:
                self.logger_func(f"[FTP] {msg}")
        else:
            if level == "ERROR":
                logger.error(msg)
            else:
                logger.info(msg)

    def set_session(self, session_id):
        """Sets the current session ID and ensures the remote directory exists."""
        self.session_id = session_id
        self.remote_session_dir = f"{self.root_dir}/{session_id}"
        self.session_stats = {"pnl": 0.0, "trades": 0, "status": "ACTIVE", "asset": "BTC", "interval": "5M"}
        self.enqueue_task(self._ensure_remote_dirs_and_update_index)
        # Force immediate index update for new session
        self.force_update_index()

    def push_session_stats(self, pnl=None, trades=None, status=None, asset=None, interval=None):
        """Updates internal session stats and enqueues a metadata/index update."""
        if pnl is not None: self.session_stats["pnl"] = pnl
        if trades is not None: self.session_stats["trades"] = trades
        if status is not None: self.session_stats["status"] = status
        if asset is not None: self.session_stats["asset"] = asset
        if interval is not None: self.session_stats["interval"] = interval
        
        # Enqueue metadata save
        self.enqueue_task(self._save_session_metadata)
        
        # Rate limit index updates to prevent excessive uploads
        current_time = time.time()
        if current_time - self.last_index_update >= self.min_index_update_interval:
            self.enqueue_task(self._update_remote_index)
            self.last_index_update = current_time

    def force_update_index(self):
        """Force immediate index update, bypassing rate limiting."""
        self.enqueue_task(self._update_remote_index)
        self.last_index_update = time.time()

    def _save_session_metadata(self):
        """Saves current session stats to metadata.json in the remote session directory."""
        import json
        from io import BytesIO
        ftp = self._get_connection()
        try:
            data = json.dumps(self.session_stats)
            ftp.cwd(self.remote_session_dir)
            ftp.storbinary("STOR metadata.json", BytesIO(data.encode('utf-8')))
        finally:
            ftp.quit()

    def enqueue_task(self, func, *args, **kwargs):
        """Adds a task to the background worker queue."""
        self.upload_queue.put((func, args, kwargs))

    def _worker(self):
        """Background worker loop for FTP operations."""
        while True:
            func, args, kwargs = self.upload_queue.get()
            try:
                func(*args, **kwargs)
            except Exception as e:
                self._log(f"Task Error: {e}", level="ERROR")
            finally:
                self.upload_queue.task_done()

    def _get_connection(self):
        """Creates and returns an authenticated FTP connection."""
        ftp = ftplib.FTP(self.host)
        ftp.login(self.user, self.passwd)
        return ftp

    def _ensure_remote_dirs_and_update_index(self):
        """Ensures session and graph directories exist, and updates index.html."""
        ftp = self._get_connection()
        try:
            # Change to root dir (domain folder)
            try:
                ftp.cwd(self.root_dir)
            except:
                ftp.mkd(self.root_dir)
                ftp.cwd(self.root_dir)
            
            # Create session dir
            try:
                ftp.cwd(self.session_id)
            except:
                ftp.mkd(self.session_id)
                ftp.cwd(self.session_id)
            
            # Create graphs dir
            try:
                ftp.cwd("graphs")
            except:
                ftp.mkd("graphs")
            
            # Back to root_dir explicitly for Index update
            ftp.cwd("/")
            ftp.cwd(self.root_dir)
            
            # Update Index
            self._update_remote_index(ftp)
            self._log(f"Session {self.session_id} initialized and index updated.", level="SYS")
            
        except Exception as e:
            self._log(f"Failed to ensure remote dirs: {e}", level="ERROR")
        finally:
            ftp.quit()

    def _update_remote_index(self, ftp=None):
        """Rebuilds the master index.html by scanning for all session directories and their metadata."""
        local_ftp = False
        if ftp is None:
            ftp = self._get_connection()
            local_ftp = True
            try:
                ftp.cwd(self.root_dir)
            except: pass

        index_file = "index.html"
        
        # 1. Scan for session directories
        try:
            items = []
            try:
                items = [name for name, facts in ftp.mlsd() if facts['type'] == 'dir']
            except:
                items = ftp.nlst()
                
            sessions = [os.path.basename(i) for i in items if "session_" in i]
        except Exception as e:
            self._log(f"Failed to list remote directories: {e}", level="ERROR")
            if local_ftp: ftp.quit()
            return

        # 2. Extract metadata for each session (if available)
        import json
        session_data_list = []
        total_pnl = 0.0
        total_trades = 0
        
        for s_id in sessions[:20]: # Only build rich cards for last 20 sessions for speed
            meta = {"pnl": 0.0, "trades": 0, "status": "UNKNOWN", "asset": "BTC", "interval": "5M"}
            try:
                # Try to download metadata.json
                from io import BytesIO
                bio = BytesIO()
                ftp.retrbinary(f"RETR {s_id}/metadata.json", bio.write)
                meta.update(json.loads(bio.getvalue().decode('utf-8')))
            except:
                pass # Use defaults if metadata missing
            
            meta["id"] = s_id
            session_data_list.append(meta)
            total_pnl += meta.get("pnl", 0.0)
            total_trades += meta.get("trades", 0)
        
        now = datetime.now()
        for sd in session_data_list:
            s_id = sd["id"]
            try:
                session_time = datetime.strptime(s_id.replace("session_", ""), "%Y%m%d_%H%M%S")
                sd["pretty_date"] = session_time.strftime("%b %d, %Y - %H:%M:%S")
                if sd.get("status") == "ACTIVE" and (now - session_time).total_seconds() > 3600: # 1 hour
                    sd["status"] = "OFFLINE"
            except:
                sd["pretty_date"] = s_id

        # --- SORTING ---
        # 1. ACTIVE sessions first
        # 2. Then by session date (newest first)
        def sort_key(item):
            is_active = 1 if item.get("status") == "ACTIVE" else 0
            # item['id'] is session_20260320_094325, so strings sort chronologically
            return (is_active, item.get("id", ""))
            
        session_data_list.sort(key=sort_key, reverse=True)

        # 3. Build Premium Master Index
        links_html = ""
        current_time = datetime.now()
        for idx, sd in enumerate(session_data_list):
            is_latest = (idx == 0)  # First item is the most recent
            pnl = sd.get("pnl", 0.0)
            pnl_class = "profit" if pnl > 0.1 else ("loss" if pnl < -0.1 else "flat")
            pnl_sign = "+" if pnl > 0 else ""
            
            # Calculate time ago for latest session
            time_ago = ""
            if is_latest:
                try:
                    session_time = datetime.strptime(sd['id'].replace("session_", ""), "%Y%m%d_%H%M%S")
                    time_diff = current_time - session_time
                    if time_diff.total_seconds() < 3600:  # Less than 1 hour
                        minutes = int(time_diff.total_seconds() / 60)
                        time_ago = f"<div class='time-ago'>{minutes} minutes ago</div>"
                    elif time_diff.total_seconds() < 86400:  # Less than 1 day
                        hours = int(time_diff.total_seconds() / 3600)
                        time_ago = f"<div class='time-ago'>{hours} hours ago</div>"
                    else:
                        days = int(time_diff.total_seconds() / 86400)
                        time_ago = f"<div class='time-ago'>{days} days ago</div>"
                except:
                    pass
            
            # Add latest badge and enhanced styling for most recent
            latest_badge = ""
            latest_class = ""
            if is_latest:
                latest_badge = "<div class='latest-badge'>LATEST</div>"
                latest_class = "latest-session"
            
            links_html += f"""
            <div class='session-card {latest_class}'>
                <div class='session-header'>
                    <div class='asset-badg'>{sd.get('asset', 'BTC')}-{sd.get('interval', '5M')}</div>
                    <div class='status-pill {sd.get('status', 'ACTIVE').lower()}'>{sd.get('status', 'ACTIVE')}</div>
                    {latest_badge}
                </div>
                <div class='session-body'>
                    <div class='main-info'>
                        <span class='session-date'>{sd['pretty_date']}</span>
                        <span class='session-id'>{sd['id']}</span>
                        {time_ago}
                    </div>
                    <div class='stats-row'>
                        <div class='stat'>
                            <span class='label'>PnL</span>
                            <span class='value {pnl_class}'>{pnl_sign}{pnl:.2f}</span>
                        </div>
                        <div class='stat'>
                            <span class='label'>Trades</span>
                            <span class='value'>{sd.get('trades', 0)}</span>
                        </div>
                    </div>
                </div>
                <div class='actions'>
                    <a href='./{sd['id']}/verification.html' class='view-btn expert'>EXPERT AUDIT</a>
                </div>
            </div>"""

        master_html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>Vortex Pulse | Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #070709;
            --card-bg: rgba(255, 255, 255, 0.03);
            --card-hover: rgba(255, 255, 255, 0.06);
            --accent: #00ffff;
            --accent-glow: rgba(0, 255, 255, 0.3);
            --text: #e0e0e0;
            --dim: #777;
            --up: #00ff88;
            --down: #ff4466;
        }}
        body {{
            background-color: var(--bg);
            background-image: 
                radial-gradient(circle at 0% 0%, rgba(0, 255, 255, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 100% 100%, rgba(0, 255, 255, 0.08) 0%, transparent 40%);
            color: var(--text);
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 0;
            min-height: 100vh;
        }}
        .navbar {{
            width: 100%;
            padding: 25px 0;
            background: rgba(0,0,0,0.5);
            border-bottom: 1px solid rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            text-align: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .navbar h1 {{
            margin: 0;
            font-size: 1.2rem;
            letter-spacing: 4px;
            font-weight: 800;
            text-transform: uppercase;
            background: linear-gradient(to right, #fff, var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .dashboard-header {{
            max-width: 1000px;
            margin: 40px auto;
            padding: 0 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .header-stat {{
            background: var(--card-bg);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        .header-stat .label {{
            display: block;
            font-size: 0.75rem;
            color: var(--dim);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .header-stat .value {{
            font-size: 1.8rem;
            font-weight: 800;
            font-family: 'IBM Plex Mono', monospace;
        }}
        .header-stat .value.profit {{ color: var(--up); }}
        .header-stat .value.loss {{ color: var(--down); }}

        .container {{
            width: 100%;
            max-width: 1000px;
            margin: 0 auto 100px;
            padding: 0 20px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
        }}
        .session-card {{
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            backdrop-filter: blur(8px);
            position: relative;
            overflow: hidden;
        }}
        .session-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
            opacity: 0;
            transition: opacity 0.3s;
        }}
        .session-card:hover {{
            background: var(--card-hover);
            border-color: var(--accent);
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5), 0 0 15px var(--accent-glow);
        }}
        .session-card:hover::before {{ opacity: 1; }}

        .session-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .asset-badg {{
            font-size: 0.7rem;
            font-weight: 800;
            background: rgba(0, 255, 255, 0.1);
            color: var(--accent);
            padding: 4px 10px;
            border-radius: 4px;
            letter-spacing: 1px;
        }}
        .status-pill {{
            font-size: 0.65rem;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 20px;
            text-transform: uppercase;
        }}
        .status-pill.active {{ background: rgba(0, 255, 136, 0.1); color: var(--up); }}
        .status-pill.unknown {{ background: rgba(255, 255, 255, 0.05); color: var(--dim); }}

        /* Latest Session Enhancements */
        .latest-badge {{
            position: absolute;
            top: -8px;
            right: -8px;
            background: linear-gradient(135deg, #ff006e, #ff4458);
            color: white;
            font-size: 0.6rem;
            font-weight: 800;
            padding: 4px 8px;
            border-radius: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 2px 8px rgba(255, 0, 110, 0.4);
            animation: pulse-glow 2s infinite;
            z-index: 10;
        }}
        .latest-session {{
            border: 2px solid #ff006e;
            background: linear-gradient(135deg, rgba(255, 0, 110, 0.1), rgba(255, 68, 88, 0.05));
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(255, 0, 110, 0.2);
            position: relative;
        }}
        .latest-session:hover {{
            transform: scale(1.03);
            box-shadow: 0 12px 35px rgba(255, 0, 110, 0.3);
        }}
        @keyframes pulse-glow {{
            0%, 100% {{ box-shadow: 0 2px 8px rgba(255, 0, 110, 0.4); }}
            50% {{ box-shadow: 0 2px 16px rgba(255, 0, 110, 0.8); }}
        }}

        .main-info {{ display: flex; flex-direction: column; gap: 5px; }}
        .session-date {{ font-size: 1.1rem; font-weight: 700; color: #fff; }}
        .session-id {{ font-size: 0.75rem; color: var(--dim); font-family: 'IBM Plex Mono', monospace; }}
        .time-ago {{ 
            font-size: 0.7rem; 
            color: #ff006e; 
            font-weight: 600; 
            text-transform: uppercase; 
            letter-spacing: 1px;
            margin-top: 2px;
        }}

        .stats-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.05);
        }}
        .stat {{ display: flex; flex-direction: column; gap: 4px; }}
        .stat .label {{ font-size: 0.65rem; color: var(--dim); text-transform: uppercase; }}
        .stat .value {{ font-size: 1.2rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }}
        .stat .value.profit {{ color: var(--up); }}
        .stat .value.loss {{ color: var(--down); }}
        
        /* New Field Styling */
        .stat .value.scanner {{ 
            color: #00ff88; 
            font-size: 1.0rem; 
            text-transform: uppercase;
            font-weight: 600;
        }}
        .stat .value.risk-low {{ color: var(--up); }}
        .stat .value.risk-medium {{ color: #ffaa00; }}
        .stat .value.risk-high {{ color: var(--down); }}
        .stat .value.entry-time {{ 
            color: #00ffff; 
            font-family: 'IBM Plex Mono', monospace;
        }}

        .view-btn {{
            width: 100%;
            display: block;
            text-align: center;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            padding: 12px 0;
            border-radius: 8px;
            text-decoration: none;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 1px;
            transition: all 0.2s;
        }}
        .view-btn:hover {{
            background: var(--accent);
            color: #000;
            border-color: var(--accent);
            box-shadow: 0 0 15px var(--accent-glow);
        }}

        .footer {{
            text-align: center;
            padding: 40px;
            color: var(--dim);
            font-size: 0.7rem;
            letter-spacing: 2px;
            opacity: 0.5;
        }}
        .last-updated {{
            margin-top: 10px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: #666;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    <div class='navbar'>
        <h1>Vortex Command Center</h1>
    </div>
    
    <div class='dashboard-header'>
        <div class='header-stat'>
            <span class='label'>Total PnL</span>
            <span class='value {'profit' if total_pnl > 0 else 'loss'}'>{'+' if total_pnl > 0 else ''}{total_pnl:.2f}</span>
        </div>
        <div class='header-stat'>
            <span class='label'>Active Sessions</span>
            <span class='value'>{len(sessions)}</span>
        </div>
        <div class='header-stat'>
            <span class='label'>Market Focus</span>
            <span class='value'>BTC-5M</span>
        </div>
    </div>

    <div class='container'>
        {links_html if links_html else "<div style='grid-column: 1/-1; text-align:center; padding:100px; color:#333; font-size: 1.5rem; font-weight:800;'>DETACHED - AWAITING SESSION</div>"}
    </div>
    <div class='footer'>
        POLYMARKET VORTEX PULSE V5 EXPERT SYSTEM ARCHIVE
        <div class='last-updated'>Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
    </div>
</body>
</html>"""

        from io import BytesIO
        ftp.storbinary(f"STOR {index_file}", BytesIO(master_html.encode('utf-8')))
        self._log("Master index.html uploaded successfully.", level="SYS")

    def upload_html_log(self, local_path):
        """Enqueues the upload of the main HTML verification log and triggers index update."""
        self.enqueue_task(self._upload_file, local_path, f"{self.remote_session_dir}/verification.html")
        # Use rate-limited index update for HTML log uploads
        current_time = time.time()
        if current_time - self.last_index_update >= self.min_index_update_interval:
            self.enqueue_task(self._update_remote_index)
            self.last_index_update = current_time

    def upload_graph(self, local_path, filename):
        """Enqueues the upload of a graph image."""
        self.enqueue_task(self._upload_file, local_path, f"{self.remote_session_dir}/graphs/{filename}")

    def _upload_file(self, local_path, remote_path):
        """Synchronous file upload (intended for worker thread)."""
        if not os.path.exists(local_path):
            return
        
        ftp = self._get_connection()
        try:
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)
        finally:
            ftp.quit()
