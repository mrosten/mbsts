
import os
import sys
import asyncio
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timezone
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams

# Force load .env (Old Account)
print("Loading .env (Old Account)...")
load_dotenv(override=True)

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"

print(f"Loaded PROXY_ADDRESS: {PROXY_ADDRESS}")

async def run():
    if not PRIVATE_KEY:
        print("Missing PRIVATE_KEY")
        return

    funder = PROXY_ADDRESS
    print(f"Initializing Client with Funder: {funder}")

    try:
        client = ClobClient(
            host=HOST,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            signature_type=1, # Proxy
            funder=funder
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print("Client Connected.")
        
        # Check Balance & Allowance
        params = BalanceAllowanceParams(asset_type="COLLATERAL")
        bal_resp = client.get_balance_allowance(params)
        balance = float(bal_resp.get('balance', 0)) / 10**6 
        allowance = float(bal_resp.get('allowance', 0)) / 10**6
        print(f"Balance: ${balance:.2f} (USDC)")
        print(f"Allowance: ${allowance:.2f} (USDC)")

        if balance < 1.0:
            print("Insufficient balance for $1 trade.")
            return

        # Fetch Market to Find "Winning Side"
        now = datetime.now(timezone.utc)
        minutes = now.minute
        floor = (minutes // 15) * 15
        start_dt = now.replace(minute=floor, second=0, microsecond=0)
        ts_start = int(start_dt.timestamp())
        market_url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
        
        slug = market_url.split("/")[-1]
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        print(f"Fetching market: {slug}...")

        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Failed to fetch market: {resp.status_code}")
            return
            
        data = resp.json()
        ids = json.loads(data["clobTokenIds"])
        outcomes = json.loads(data["outcomes"])
        
        up_id = None
        down_id = None
        up_idx, down_idx = 0, 1
        for i, name in enumerate(outcomes):
            if "Up" in name or "Yes" in name: up_idx = i
            elif "Down" in name or "No" in name: down_idx = i
        
        up_id = ids[up_idx]
        down_id = ids[down_idx]
        
        # Check prices
        clob_url = "https://clob.polymarket.com/price"
        p_up = requests.get(clob_url, params={"token_id": up_id, "side": "buy"}).json().get("price", 0)
        p_down = requests.get(clob_url, params={"token_id": down_id, "side": "buy"}).json().get("price", 0)
        
        p_up = float(p_up)
        p_down = float(p_down)
        
        print(f"UP: {p_up} | DOWN: {p_down}")
        
        target_side = "UP" if p_up > p_down else "DOWN"
        token_id = up_id if target_side == "UP" else down_id
        price = p_up if target_side == "UP" else p_down
        
        if price <= 0: price = 0.5 # fallback

        # Calculate shares for ~$1
        shares = 1.0 / price
        shares = round(shares, 2)
        
        print(f"Attempting to BUY $1 of {target_side} (~{shares} shares @ {price})...")
        
        try:
             order_args = OrderArgs(
                price=0.99, # Market buy effectively
                size=shares,
                side="BUY",
                token_id=token_id
            )
             
             # Sync call in thread wrapper if required, but here just direct call is fine or wrapped
             # client.create_order is synchronous/blocking? 
             # manual_buy_v2 used a wrapper. Let's just try direct.
             signed = client.create_order(order_args)
             resp = client.post_order(signed)
             print(f"Order Response: {resp}")
             
        except Exception as e:
            print(f"Trade Execution Error: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Error during init/balance: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
