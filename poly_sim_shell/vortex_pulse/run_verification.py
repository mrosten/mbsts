import sys
import os
import time
from datetime import datetime

# Add root to sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Import modules directly
try:
    from broker import SimBroker, LiveBroker
    from app import PulseApp
except ImportError as e:
    print(f"ERROR: Failed to import modules: {e}")
    sys.exit(1)

def run_headless_verification():
    print("\n=== DARWIN ORCHESTRATOR VERIFICATION [HEADLESS] ===")
    
    start_bal = 1000.00
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(root_dir, "lg", f"verify_session_{session_id}.txt")
    
    if not os.path.exists(os.path.join(root_dir, "lg")):
        os.makedirs(os.path.join(root_dir, "lg"), exist_ok=True)
        
    sim_broker = SimBroker(start_bal, log_file)
    live_broker = LiveBroker(sim_broker) 
    
    app = PulseApp(sim_broker, live_broker, start_live_mode=False, session_id=session_id)
    
    # Force Darwin V2 Mode
    app.config.DARWIN_MODE = "v2"
    app.darwin.mode = "v2"
    
    print(f"Starting PulseApp in SIM mode (Bal: ${start_bal})...")
    # We'll run for a short period then exit, or just verify it starts.
    # Since run() is blocking, we might need a timeout or just check logs after it starts.
    
    try:
        # Non-blocking run? No, textual run() is blocking.
        # But we can use work() to stop it later, or just let it crash/exit if it fails.
        app.run()
    except Exception as e:
        print(f"App Runtime Error: {e}")

if __name__ == "__main__":
    run_headless_verification()
