import sys
import os
import time
from datetime import datetime
import asyncio

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

async def fast_verification():
    print("\n=== DARWIN ORCHESTRATOR ACCELERATED VERIFICATION ===")
    
    start_bal = 1000.00
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(root_dir, "lg", f"fast_verify_{session_id}.txt")
    
    if not os.path.exists(os.path.join(root_dir, "lg")):
        os.makedirs(os.path.join(root_dir, "lg"), exist_ok=True)
        
    sim_broker = SimBroker(start_bal, log_file)
    live_broker = LiveBroker(sim_broker) 
    
    app = PulseApp(sim_broker, live_broker, start_live_mode=False, session_id=session_id)
    
    # Force Darwin V2 Mode
    app.config.DARWIN_MODE = "v2"
    app.darwin.mode = "v2"
    
    print(f"Starting PulseApp in SIM mode...")
    
    # Run the app in a background thread if possible, or just mock the dependencies
    # Textual app.run() is blocking and starts its own event loop.
    # We'll try to run it then inject events.
    
    # Actually, we can just test the Darwin agent directly with a mock app object!
    print("Testing DarwinAgent directly with mock context...")
    
    mock_ctx = {
        "elapsed": 300,
        "up_price_close": 0.52,
        "system_config": app._assemble_darwin_system_config()
    }
    
    print("\n[STEP 1] Initializing Darwin Agent...")
    print(f"Darwin available scanners: {app.darwin.available_scanners}")
    
    print("\n[STEP 2] Triggering On-Window-End Cycle (Simulated)...")
    # This will call the Gemini API
    app.darwin.on_window_end(mock_ctx)
    
    print("Waiting for Darwin to process (check logs for 'GEMINI CYCLE' or 'DARWIN:')...")
    time.sleep(15) 
    
    print("\n[STEP 3] Verifying SourceCodeSniffer (Requesting Momentum)...")
    # We manually simulate a response that requests code
    # Normally Darwin would do this in its JSON response
    source = app.darwin.sniffer.get_source("Momentum")
    if source:
        print(f"SUCCESS: Pulled {len(source)} lines of code for Momentum.")
    else:
        print("FAILURE: Could not pull code.")
        
    print("\n[STEP 4] Verifying System Actions (Suggesting Risk Cap change)...")
    # Simulate Darwin suggesting a risk cap change
    test_actions = {"set_risk_cap": 35.0}
    print(f"Applying test actions: {test_actions}")
    app._apply_darwin_system_actions(test_actions)
    print(f"New Risk Cap: {app.total_risk_cap}")
    
    if app.total_risk_cap == 35.0:
        print("SUCCESS: Command Bridge applied the change.")
    else:
        print("FAILURE: Command Bridge failed to apply the change.")

if __name__ == "__main__":
    asyncio.run(fast_verification())
