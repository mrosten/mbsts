import asyncio
import time

class SchedulerState:
    @staticmethod
    async def setup():
        # Setup global scheduler state if needed
        pass

async def setup_scheduler(schedule_str, job_func):
    """
    Basic scheduler implementation.
    Supports simple interval parsing from cron-like string "*/N * * * * *" (seconds).
    """
    interval = 60
    
    if schedule_str.startswith("*/"):
        try:
            parts = schedule_str.split(" ")
            first_part = parts[0]
            interval = int(first_part.replace("*/", ""))
        except Exception as e:
            print(f"[Scheduler] Could not parse '{schedule_str}', defaulting to 60s. Error: {e}")
    
    print(f"[Scheduler] Registering job {job_func.__name__} every {interval}s")
    
    async def loop():
        print(f"[Scheduler] Starting loop for {job_func.__name__}")
        while True:
            try:
                print(f"[Scheduler] About to call {job_func.__name__}...")
                await job_func()
                print(f"[Scheduler] {job_func.__name__} completed successfully")
            except Exception as e:
                print(f"[Scheduler] Job {job_func.__name__} failed: {e}")
                import traceback
                traceback.print_exc()
            await asyncio.sleep(interval)

    # Fire and forget the loop
    print(f"[Scheduler] Creating task for {job_func.__name__}")
    asyncio.create_task(loop())
    print(f"[Scheduler] Task created for {job_func.__name__}")

