import asyncio
import time
from simulation import simulation

async def speed_test():
    print("Starting Speed Test...")
    start = time.time()
    
    # Run one update cycle
    print("Running update_loop (concurrent fetch)...")
    await simulation.update_loop()
    
    duration = time.time() - start
    print(f"Cycle completed in {duration:.3f} seconds")
    
    print("Logs:")
    for l in simulation.logs[-5:]:
        print(l)
        
    if duration > 3.0:
        print("WARNING: Cycle took too long!")
    else:
        print("SUCCESS: Cycle fast enough.")

if __name__ == "__main__":
    asyncio.run(speed_test())
