import sys
import os
import time
from datetime import datetime

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (vortex_pulse folder) - go up one level from scripts
parent_dir = os.path.dirname(current_dir)

# Add the parent directory to sys.path so we can import the modules directly
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import modules directly
try:
    from broker import SimBroker, LiveBroker
    from app import PulseApp
except ImportError as e:
    print(f"ERROR: Failed to import modules: {e}")
    sys.exit(1)

def main():
    print("\n=== POLYMARKET VORTEX PULSE V5 [PENDING ORDER EXECUTION] ===")
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
        
    log_base = os.path.join(parent_dir, "lg")
    
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(log_base, f"session_{session_id}")
    if not os.path.exists(log_dir): 
        os.makedirs(log_dir, exist_ok=True)
        
    default_log = os.path.join(log_dir, f"pulse_log_5M_{session_id}.csv")
    log_file = input(f"Enter Log Filename (default: {default_log}): ").strip()
    if not log_file: 
        log_file = default_log
    if not log_file.endswith(".csv"): 
        log_file += ".csv"
        
    sim_broker = SimBroker(start_bal, log_file)
    live_broker = LiveBroker(sim_broker) 
    
    app = PulseApp(sim_broker, live_broker, start_live_mode=is_live_start, session_id=session_id)
    
    print("\n[ACTIVE LOG FILES]")
    if app.log_settings.get("main_csv", True): 
        print(f" - CSV Log:      {os.path.abspath(log_file)}")
    if app.log_settings.get("console_txt", True):
        print(f" - Console Log:  {os.path.abspath(app.console_log_file)}")
    if app.log_settings.get("verification_html", True):
        print(f" - HTML Log:     {os.path.abspath(app.html_log_file)}")
    if app.log_settings.get("momentum_csv", True):
        print(f" - Momentum Log: {os.path.abspath(app.mom_adv_log_file)}")
    
    print("\nStarting...")
    time.sleep(1)
    app.run()

if __name__ == "__main__":
    main()
