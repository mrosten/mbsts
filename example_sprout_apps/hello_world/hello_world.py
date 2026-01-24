from example_sprout_apps.hello_world import data as db
from example_sprout_apps.hello_world import input_output
from sprout.app import SproutApp
from sprout.configuration import SproutConfiguration
from sprout.database import initialize_database, run_database_updates


class HelloApp(SproutApp):
    def __init__(self):
        super().__init__()

    async def start(self):
        config = SproutConfiguration()
        await input_output.setup()
        from example_sprout_apps.hello_world.data import classes
        await initialize_database(config, 'example_sprout_apps/hello_world/helloworld.db', classes)
        await run_database_updates('example_sprout_apps/hello_world/db_updates.yaml')
        await db.setHttpLog(1245, remote='somewhere')
