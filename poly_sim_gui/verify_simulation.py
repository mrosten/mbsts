print("DEBUG: Pre-Import")
from nicegui import run
import asyncio

# Mock io_bound for headless run
async def mock_io_bound(func, *args, **kwargs):
    return func(*args, **kwargs)

run.io_bound = mock_io_bound

from simulation import SimulationStore

async def verify():
    print("DEBUG: Script Started")
    print("Verifying Simulation Logic...")
    sim = SimulationStore()
    print("DEBUG: Store Initialized")
    sim.start_simulation()
    
    # Mock some data or connection
    # We will just run the update loop a few times
    print("Running update loop...")
    
    # Force some update cycles
    for i in range(5):
        print(f"--- Cycle {i+1} ---")
        await sim.update_loop()
        await asyncio.sleep(1) # Wait a bit
        
    print("\nLogs:")
    for l in sim.logs:
        print(l)
        
    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(verify())
