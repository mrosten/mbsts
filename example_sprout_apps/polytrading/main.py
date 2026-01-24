import argparse
import asyncio
import sys

# Force unbuffered output for logging visibility
sys.stdout.reconfigure(line_buffering=True)

from example_sprout_apps.polytrading.polytrading import PolytradingApp
from sprout.log.logger import Logger

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sprout_context = "CLI"

    logger = Logger('main')
    parser.add_argument("--run_app", help="run application", action="store_true", default=True)

    args = parser.parse_args()
    
    if args.run_app:
        app_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(app_loop)
        app_inst = PolytradingApp()
        app_loop.run_until_complete(app_inst.start())
        app_loop.run_forever()
