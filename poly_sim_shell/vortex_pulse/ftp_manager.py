import os
import ftplib
import threading
import logging
import queue
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
    def __init__(self, host=None, user=None, passwd=None, root_dir=None):
        self.host = host or config.FTP_HOST
        self.user = user or config.FTP_USER
        self.passwd = passwd or config.FTP_PASS
        self.root_dir = root_dir or config.FTP_ROOT
        
        self.upload_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        self.session_id = None
        self.remote_session_dir = None

    def set_session(self, session_id):
        """Sets the current session ID and ensures the remote directory exists."""
        self.session_id = session_id
        self.remote_session_dir = f"{self.root_dir}/{session_id}"
        self.enqueue_task(self._ensure_remote_dirs_and_update_index)

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
                logger.error(f"FTP Task Error: {e}")
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
            
            ftp.cwd("..") # Back to session root
            ftp.cwd("..") # Back to root_dir
            
            # Update Index
            self._update_remote_index(ftp)
            
        finally:
            ftp.quit()

    def _update_remote_index(self, ftp):
        """Rebuilds the master index.html by scanning for all session directories."""
        index_file = "index.html"
        
        # 1. Scan for session directories
        try:
            items = ftp.nlst()
            # Filter for anything that looks like a session folder
            sessions = sorted([i for i in items if i.startswith("session_")], reverse=True)
        except Exception as e:
            logger.error(f"Failed to list remote directories for indexing: {e}")
            return

        # 2. Build Premium Master Index
        # Gradient background, glowing accents, and responsive layout
        links_html = ""
        for s_id in sessions:
            # Try to get a pretty date from the session_id format YYYYMMDD_HHMMSS
            try:
                dt_str = datetime.strptime(s_id.replace("session_", ""), "%Y%m%d_%H%M%S").strftime("%b %d, %Y - %H:%M:%S")
            except:
                dt_str = s_id
            
            links_html += f"""
            <div class='session-card'>
                <div class='session-info'>
                    <span class='session-date'>{dt_str}</span>
                    <span class='session-id'>{s_id}</span>
                </div>
                <a href='./{s_id}/verification.html' class='view-btn'>VIEW LOG</a>
            </div>"""

        master_html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>Vortex Pulse | Master Archive</title>
    <style>
        :root {{
            --bg: #0a0a0c;
            --card-bg: rgba(255, 255, 255, 0.03);
            --accent: #00ffff;
            --accent-glow: rgba(0, 255, 255, 0.4);
            --text: #e0e0e0;
            --dim: #888;
        }}
        body {{
            background-color: var(--bg);
            background-image: 
                radial-gradient(circle at 20% 20%, rgba(0, 255, 255, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 80% 80%, rgba(0, 255, 255, 0.05) 0%, transparent 40%);
            color: var(--text);
            font-family: 'Inter', -apple-system, sans-serif;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        h1 {{
            font-size: 2.5rem;
            letter-spacing: -1px;
            margin-bottom: 40px;
            background: linear-gradient(to right, #fff, var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-transform: uppercase;
        }}
        .container {{
            width: 100%;
            max-width: 800px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        .session-card {{
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 20px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            backdrop-filter: blur(10px);
        }}
        .session-card:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: var(--accent);
            box-shadow: 0 0 20px var(--accent-glow);
            transform: translateY(-2px);
        }}
        .session-info {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .session-date {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
        }}
        .session-id {{
            font-size: 0.85rem;
            color: var(--dim);
            font-family: monospace;
        }}
        .view-btn {{
            background: transparent;
            border: 1px solid var(--accent);
            color: var(--accent);
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 1px;
            transition: all 0.2s;
        }}
        .view-btn:hover {{
            background: var(--accent);
            color: #000;
            box-shadow: 0 0 15px var(--accent);
        }}
        .footer {{
            margin-top: 60px;
            color: var(--dim);
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <h1>Vortex Archive</h1>
    <div class='container'>
        {links_html if links_html else "<div style='text-align:center; padding:40px; color:#555;'>No sessions found yet.</div>"}
    </div>
    <div class='footer'>POLYMARKET VORTEX PULSE V5 EXPERT SYSTEM</div>
</body>
</html>"""

        from io import BytesIO
        ftp.storbinary(f"STOR {index_file}", BytesIO(master_html.encode('utf-8')))

    def upload_html_log(self, local_path):
        """Enqueues the upload of the main HTML verification log."""
        self.enqueue_task(self._upload_file, local_path, f"{self.remote_session_dir}/verification.html")

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
