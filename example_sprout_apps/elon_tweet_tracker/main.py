import argparse
import asyncio

from example_sprout_apps.elon_tweet_tracker.elon_tracker import ElonTrackerApp
from sprout.log import logger
from sprout.log.logger import Logger

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sprout_context = "CLI"

    logger = Logger('main')
    parser.add_argument("--run_app", help="run application", action="store_true", default=False)

    args = parser.parse_args()
    if args.run_app:
        app_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(app_loop)
        app_inst = ElonTrackerApp()
        app_loop.run_until_complete(app_inst.start())
        app_loop.run_forever()
    
    ans1 = logger.process("Elon Tracker Started")
    print(ans1)
