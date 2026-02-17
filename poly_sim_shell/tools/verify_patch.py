import requests
import json
import os
from dotenv import load_dotenv

# --- MONKEY PATCH ---
print("Applying Monkey Patch...")
original_request = requests.Session.request
def new_request(self, method, url, *args, **kwargs):
    print(f"DEBUG: Monkey-Patch triggered for {url}")
    self.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Custom-Check": "VerifyPatchv1"
    })
    return original_request(self, method, url, *args, **kwargs)
requests.Session.request = new_request

# Now import client (simulate script order)
from py_clob_client.client import ClobClient

load_dotenv()
pk = os.getenv("PRIVATE_KEY")

try:
    print("Initializing Client...")
    client = ClobClient(host="https://clob.polymarket.com", key=pk, chain_id=137)
    
    print("Making Test Request via Client internals...")
    # This usually calls get_markets or similar which uses the internal session
    # We'll try to just check the session directly if possible, or trigger a call
    
    # We can try to fetch something simple like time or price if the client has a method
    # or just use the private session if we can access it (we couldn't before)
    # But the monkey patch prints "DEBUG" so we will see it.
    
    try:
        # Trigger a simple read call
        client.get_sampling_simplified_markets()
    except Exception as e:
        print(f"Client Call Error (Expected if auth bad/etc): {e}")

except Exception as e:
    print(f"Setup Error: {e}")
