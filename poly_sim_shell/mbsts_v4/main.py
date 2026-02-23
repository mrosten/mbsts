import sys
import os
import time
from datetime import datetime
from .broker import SimBroker, LiveBroker
from .app import SniperApp

def main():
    print("\n=== POLYMARKET SNIPER V4 REFACTORED [5 MINUTE VERSION] ===")
    print(f"Running with Python: {sys.executable}")
    
    start_mode = input("Select Mode: (1) Sim Mode [Default], (2) Live Mode: ").strip()
    is_live_start = (start_mode == "2")
    
    start_bal = 100.00
    if not is_live_start:
        try: 
            inp = input("Enter Initial SIM Balance ($) [Default 100]: ").strip()
            start_bal = float(inp) if inp else 100.00
        except: 
            start_bal = 100.00
        
    if not os.path.exists("logs"): 
        os.makedirs("logs")
        
    # Timeframe is 5M for this version
    timeframe = "5"
    
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    default_log = f"logs/sim_log_{timeframe}M_{timestamp}.csv"
    log_file = input(f"Enter Log Filename (default: {default_log}): ").strip()
    if not log_file: 
        log_file = default_log
    if not log_file.endswith(".csv"): 
        log_file += ".csv"
        
    print(f"Starting... Logging to: {log_file}")
    time.sleep(1)
    
    sim_broker = SimBroker(start_bal, log_file)
    live_broker = LiveBroker(sim_broker) 
    
    app = SniperApp(sim_broker, live_broker, start_live_mode=is_live_start)
    app.run()

if __name__ == "__main__":
    main()
