"""
Manual Buy Scripts - FIXED for Proxy Trading
Forces signature_type=1 and correctly handles neg_risk for BTC markets.
"""
import os
import sys
import json
import asyncio
import requests
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams, PartialCreateOrderOptions

# Force stdout encoding for Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv()

# --- CONFIGURATION ---
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
# Use the NEW keys just generated if available, otherwise fallback to .env which might be old
API_KEY = os.getenv("POLYMARKET_API_KEY")
API_SECRET = os.getenv("POLYMARKET_API_SECRET")
API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

class ManualBuyerFix:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        print("=" * 60)
        print("  INITIALIZING PROXY TRADER (FIXED)")
        print("=" * 60)
        
        if not PROXY_ADDRESS:
            print("  [ERROR] PROXY_ADDRESS not found in .env")
            sys.exit(1)

        print(f"  Proxy: {PROXY_ADDRESS}")
        
        # Initialize Client with signature_type=1 (POLY_PROXY)
        self.client = ClobClient(
            host=HOST,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            signature_type=1,  # FORCE PROXY TYPE
            funder=PROXY_ADDRESS
        )

        # Set API Credentials
        try:
            if API_KEY and API_SECRET and API_PASSPHRASE:
                print("  [INFO] Using API Keys from .env...")
                self.client.set_api_creds(
                    self.client.create_or_derive_api_creds() 
                    # Note: We re-derive to be safe, or we could manually construct object
                )
            else:
                print("  [INFO] Deriving new API Keys...")
                creds = self.client.create_or_derive_api_creds()
                self.client.set_api_creds(creds)
            print("  [OK] API Credentials Set")
        except Exception as e:
            print(f"  [WARN] Failed to set credentials: {e}")

        # Check Balance
        try:
            bal = self.client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
            usdc = float(bal.get('balance', 0)) / 10**6
            print(f"  [OK] Proxy Balance: ${usdc:.4f}")
        except Exception as e:
            print(f"  [WARN] Balance check failed: {e}")

    def get_market_data(self):
        """Fetch current BTC 15m market"""
        print("\n  [INFO] Finding current BTC market...")
        # Simple logic: get the market expiring next
        # For now, let's hardcode a known slug pattern or search
        # Better: Search for "Bitcoin" events
        try:
            # 1. Get current time bucket
            import time
            now_ts = int(time.time())
            # Round to nearest 15m? Or just search gamma
            
            resp = requests.get("https://gamma-api.polymarket.com/events?slug=bitcoin-price", params={"closed": "false"})
            # This is complex to parse dynamically. 
            # Let's ask user for the Token ID directly for safety, or just default to the one we saw in logs
            # In logs: btc-updown-15m-1770789600 which is likely expired or old
            
            print("  [INPUT] Please enter the Token ID to buy (Cleanest way)")
            print("  (Find this on the market page URL or dev tools)")
            token_id = input("  Token ID: ").strip()
            return token_id
        except Exception as e:
            print(f"Error fetching market: {e}")
            return None

    async def buy(self):
        token_id = self.get_market_data()
        if not token_id: return

        print(f"\n  Target Token ID: {token_id}")
        amount = input("  Amount to Buy ($): ").strip()
        if not amount: return
        
        try:
            # Get Price (approx)
            print("  [INFO] Fetching price...")
            # We can use get_midpoint or orderbook
            # For simplicity, assume 0.50 if fails
            price = 0.50 
            try:
                ob = self.client.get_order_book(token_id)
                if ob.asks:
                    price = float(ob.asks[0].price)
                    print(f"  [INFO] Best Ask: {price}")
            except:
                print("  [WARN] Could not fetch OB, using 0.50 estimate")

            shares = round(float(amount) / price, 2)
            print(f"  [PLAN] Buying ~{shares} shares for ${amount}")
            
            confirm = input("  Execute? (y/N): ")
            if confirm.lower() != 'y': return

            # Create Order
            order_args = OrderArgs(
                price=0.99, # Market Buy aggression
                size=shares,
                side="BUY",
                token_id=token_id
            )

            print("\n  [EXEC] Signing and Posting Order...")
            
            # METHOD 1: Try with neg_risk=True
            try:
                print("  [ATTEMPT 1] Using neg_risk=True...")
                options = PartialCreateOrderOptions(neg_risk=True) # Use Partial options
                signed_order = self.client.create_order(order_args, options)
                resp = await asyncio.to_thread(self.client.post_order, signed_order)
                print(f"  [SUCCESS] {resp}")
                return
            except Exception as e:
                print(f"  [FAIL] Attempt 1 failed: {e}")
                if "invalid signature" in str(e).lower():
                    pass # Expected if neg_risk mismatch
                else:
                    pass

            # METHOD 2: Try without neg_risk (Standard)
            try:
                print("\n  [ATTEMPT 2] Using neg_risk=False...")
                signed_order = self.client.create_order(order_args)
                resp = await asyncio.to_thread(self.client.post_order, signed_order)
                print(f"  [SUCCESS] {resp}")
            except Exception as e:
                print(f"  [FAIL] Attempt 2 failed: {e}")

        except Exception as e:
            print(f"  [ERROR] {e}")

if __name__ == "__main__":
    buyer = ManualBuyerFix()
    asyncio.run(buyer.buy())
