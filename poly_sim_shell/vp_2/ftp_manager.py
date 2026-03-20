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
        """Downloads, updates, and re-uploads index.html with the new session link."""
        index_file = "index.html"
        content = []
        try:
            ftp.retrlines(f"RETR {index_file}", content.append)
            index_html = "\n".join(content)
        except:
            index_html = f"""<!DOCTYPE html>
<html>
<head><title>Vortex Pulse Session Index</title></head>
<body style='font-family:sans-serif; background:#121212; color:#eee; padding:20px;'>
    <h1>Vortex Pulse Session Index</h1>
    <ul id='session-list'>
    </ul>
</body>
</html>"""

        # Add new link if not present
        link = f"<li><a href='./{self.session_id}/verification.html' style='color:#00ffff;'>{self.session_id}</a> - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>"
        if link not in index_html:
            index_html = index_html.replace("<ul id='session-list'>", f"<ul id='session-list'>\n        {link}")
        
        from io import BytesIO
        ftp.storbinary(f"STOR {index_file}", BytesIO(index_html.encode('utf-8')))

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
