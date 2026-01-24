"""
Gmail Tracker - Main Entry Point
"""
import asyncio
from example_sprout_apps.gmail_tracker.gmail_tracker import GmailTrackerApp

if __name__ == "__main__":
    app_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(app_loop)
    app_inst = GmailTrackerApp()
    app_loop.run_until_complete(app_inst.start())
    app_loop.run_forever()
