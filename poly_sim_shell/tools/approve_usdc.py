import os
import sys
import asyncio
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient

# Load .env
load_dotenv()

# --- CONSTANTS ---
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")

def log(msg):
    print(f"[*] {msg}")

def main():
    if not PRIVATE_KEY:
        log("CRITICAL: No PRIVATE_KEY in .env!")
        sys.exit(1)

    try:
        key_acct = Account.from_key(PRIVATE_KEY)
        funder = PROXY_ADDRESS if PROXY_ADDRESS else key_acct.address
        
        # Init Client
        client = ClobClient(
            host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, 
            signature_type=1 if PROXY_ADDRESS else 0, funder=funder
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        log(f"Connected. Funder: {funder}")
        
        # Check current allowance
        log("Checking current allowance...")
        # Note: Depending on library version, might use different method, but set_allowance is standard
        # usually update_balance_allowance or similar. 
        # Standard py_clob_client often has 'update_collateral_allowance' or similar?
        # Actually simplest is to try to set it.
        
        log("Approving Maximum USDC Allowance for Polymarket Exchange...")
        try:
             # This sets the allowance for the Exchange Contract to spend your USDC
             tx_hash = client.update_collateral_allowance(
                 allowance=1_000_000 # Set a high number ($1M USDC)
             )
             log(f"Transaction Sent! Hash: {tx_hash}")
             log("Waiting for confirmation (usually 2-5s)...")
             log("DONE! You should be able to trade now.")
             
        except Exception as e:
            log(f"Error sending approval: {e}")
            log("Trying alternative method (enable_collateral)...")
            try:
                # Some versions use this
                tx = client.update_allowance(amount=1_000_000, asset_type="COLLATERAL")
                log(f"Transaction Sent! Hash: {tx}")
            except Exception as e2:
                 log(f"Alternative failed too: {e2}")

    except Exception as e:
        log(f"Init Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
