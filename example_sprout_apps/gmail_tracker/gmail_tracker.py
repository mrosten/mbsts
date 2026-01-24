"""
Gmail Tracker Application
Monitors inbox statistics and email patterns
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sprout.app import SproutApp
from sprout.configuration import SproutConfiguration
from sprout.database import initialize_database
from sprout.runtime import scheduler
from example_sprout_apps.gmail_tracker.data import classes as db
from example_sprout_apps.gmail_tracker.input_output import setup_input_output
from example_sprout_apps.gmail_tracker.jobs import track_inbox

class GmailTrackerApp(SproutApp):
    def __init__(self):
        # Load configuration
        self.config = SproutConfiguration(
            path='example_sprout_apps/gmail_tracker/'
        ).config
        super().__init__()
    
    async def start(self):
        """Start the Gmail tracker"""
        print("\n" + "="*60)
        print(" GMAIL INBOX TRACKER ".center(60))
        print("="*60 + "\n")
        
        # Setup I/O
        setup_input_output(self.config)
        
        # Initialize database
        await initialize_database(
            self.config,
            self.config.db.sqlite.storage_file,
            db
        )
        
        print("✅ Database initialized")
        print(f"📧 Tracking inbox every 5 minutes...")
        print(f"📊 Data saved to: {self.config.db.sqlite.storage_file}\n")
        
        # Setup scheduler
        await scheduler.SchedulerState.setup()
        
        # Get the cron schedule from jobs
        job_config = self.config.jobs[0]
        await scheduler.setup_scheduler(job_config.cron, track_inbox.track_inbox_stats)
