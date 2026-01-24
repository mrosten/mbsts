
from sprout.app import SproutApp
from sprout.configuration import SproutConfiguration
from sprout.database import initialize_database, run_database_updates
from sprout.runtime import scheduler
from example_sprout_apps.financial import input_output as io
from example_sprout_apps.financial.jobs import track_stocks
from example_sprout_apps.financial.data import classes as fin_classes

class FinancialApp(SproutApp):
    def __init__(self):
        # Point to the financial app directory for config
        self.config = SproutConfiguration(path='example_sprout_apps/financial/').config
        super().__init__()

    async def start(self):
        sprout_context = "FinancialApp:start"
        
        # Setup IO (HTTP client etc)
        await io.setup()
        
        # Initialize Database
        await initialize_database(self.config, self.config.db.sqlite.storage_file, fin_classes)
        await run_database_updates(yaml_file=self.config.db.sqlite.updates_file)
        
        # Setup Scheduler
        await scheduler.SchedulerState.setup()
        
        # Schedule the stock tracking job
        # Assuming config.cron.schedule exists
        await scheduler.setup_scheduler(self.config.cron.schedule, track_stocks.track_stocks)
