import sys
import os
import time
import asyncio
from datetime import datetime
from .broker import SimBroker, LiveBroker
from .app import SniperApp

async def main():
    print("\n=== POLYMARKET SNIPER V4B HEDGE ===")
    print(f"Running with Python: {sys.executable}")
    
    # Use loop.run_in_executor for inputs to avoid blocking the event loop if needed, 
    # but since this is at startup before the app runs, it's okay-ish.
    # However, to be fully async-friendly:
    def get_input(prompt):
        return input(prompt).strip()

    loop = asyncio.get_event_loop()
    start_mode = await loop.run_in_executor(None, get_input, "Select Mode: (1) Sim Mode [Default], (2) Live Mode: ")
    is_live_start = (start_mode == "2")
    
    start_bal = 100.00
    if not is_live_start:
        try: 
            inp = await loop.run_in_executor(None, get_input, "Enter Initial SIM Balance ($) [Default 100]: ")
            start_bal = float(inp) if inp else 100.00
        except: 
            start_bal = 100.00
        
    if not os.path.exists("logs"): 
        os.makedirs("logs")
        
    default_log = f"logs/sim_log_5M_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    log_file = await loop.run_in_executor(None, get_input, f"Enter Log Filename (default: {default_log}): ")
    if not log_file: 
        log_file = default_log
    if not log_file.endswith(".csv"): 
        log_file += ".csv"
        
    print(f"Starting... Logging to: {log_file}")
    await asyncio.sleep(1)
    
    sim_broker = SimBroker(start_bal, log_file)
    live_broker = LiveBroker(sim_broker) 
    
    app = SniperApp(sim_broker, live_broker, start_live_mode=is_live_start)
    await app.run_async()

if __name__ == "__main__":
    main()
