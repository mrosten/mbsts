from sprout.app import SproutApp
from sprout.configuration import SproutConfiguration
from sprout.runtime import scheduler
from sprout.database import initialize_database, run_database_updates
from example_sprout_apps.polytrading.data import classes as poly_classes
from example_sprout_apps.polytrading.jobs import trading

class PolytradingApp(SproutApp):
    def __init__(self):
        # Point to the polytrading app directory for config
        self.config = SproutConfiguration(path='example_sprout_apps/polytrading/').config
        super().__init__()

    async def start(self):
        sprout_context = "PolytradingApp:start"
        
        # Initialize Database
        await initialize_database(self.config, self.config.db.sqlite.storage_file, poly_classes)
        await run_database_updates(yaml_file=self.config.db.sqlite.updates_file)
        
        # Setup Scheduler
        await scheduler.SchedulerState.setup()
        
        # Schedule the trading job
        print(f"Scheduling trading job with cron: {self.config.cron.schedule}")
        await scheduler.setup_scheduler(self.config.cron.schedule, trading.run_trading_cycle)
