
from sprout.app import SproutApp
from sprout.configuration import SproutConfiguration
from sprout.database import initialize_database, run_database_updates
from sprout.runtime import scheduler
from example_sprout_apps.elon_tweet_tracker import input_output as io
from example_sprout_apps.elon_tweet_tracker.jobs import track_tweets
from example_sprout_apps.elon_tweet_tracker.data import classes as tweet_classes

class ElonTrackerApp(SproutApp):
    def __init__(self):
        # Point to the elon app directory for config
        self.config = SproutConfiguration(path='example_sprout_apps/elon_tweet_tracker/').config
        super().__init__()

    async def start(self):
        sprout_context = "ElonTrackerApp:start"
        
        # Setup IO
        await io.setup()
        
        # Initialize Database
        await initialize_database(self.config, self.config.db.sqlite.storage_file, tweet_classes)
        # Assuming no updates file yet, but config points to one
        # await run_database_updates(yaml_file=self.config.db.sqlite.updates_file)
        
        # Setup Scheduler
        await scheduler.SchedulerState.setup()
        
        # Initialize Twikit Client in the job module (using a dirty hack or proper init)
        # We can pass config to the job setup if we had a proper job manager.
        # For now, let's inject config into track_tweets module
        track_tweets.init_config(self.config)

        # Schedule the tracker job
        await scheduler.setup_scheduler(self.config.cron.schedule, track_tweets.track_tweets_job)
