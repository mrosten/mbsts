import os
import argparse
import asyncio
import json
import requests
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams, AssetType

# Load environment variables from .env file
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon Mainnet
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

def get_market_data(slug):
    """Fetch market data from Gamma API using slug."""
    url = f"{GAMMA_API_BASE}/markets/slug/{slug}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching market data for slug '{slug}': {response.status_code}")
        return None

def get_client():
    """Initialize Polymarket CLOB client."""
    if not PRIVATE_KEY:
        print("Error: PRIVATE_KEY not found in environment variables.")
        return None

    if PROXY_ADDRESS:
        funder_address = PROXY_ADDRESS
    else:
        account = Account.from_key(PRIVATE_KEY)
        funder_address = account.address

    client = ClobClient(
        host=HOST,
        key=PRIVATE_KEY,
        chain_id=CHAIN_ID,
        signature_type=1,
        funder=funder_address
    )
    
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
    except Exception as e:
        print(f"Error deriving API credentials: {e}")
        return None
        
    return client

async def sell_all(url):
    """Parse URL, find holdings, and sell everything."""
    # 1. Extract slug from URL
    url_parts = url.strip("/").split("?")[0].split("/")
    slug = url_parts[-1]
    
    print(f"Resolving market slug: {slug}")
    market_data = get_market_data(slug)
    if not market_data:
        return

    # 2. Get Token IDs and Market details
    token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
    outcomes = json.loads(market_data.get("outcomes", "[]"))
    
    if not token_ids:
        print("Error: Could not find token IDs for this market.")
        return

    # 3. Initialize Client
    client = get_client()
    if not client:
        return

    # 4. Check holdings and sell
    print(f"Scanning holdings for {len(token_ids)} outcomes...")
    for i, token_id in enumerate(token_ids):
        outcome_name = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
        try:
            params = BalanceAllowanceParams(
                asset_type=AssetType.CONDITIONAL,
                token_id=token_id
            )
            resp = client.get_balance_allowance(params)
            raw_balance = int(resp.get('balance', '0'))
            
            if raw_balance > 0:
                # Convert to shares (assuming 6 decimals based on USDC comparison)
                # Actually, let's check market_data for share decimals if possible.
                # Usually it's 1 token = 1 share, but the API returns raw units.
                # In Polymarket CLOB, shares have 6 decimals.
                import math
                shares = raw_balance / 1_000_000
                print(f"Found {shares} shares of '{outcome_name}'.")
                
                # Check min size
                min_size = float(market_data.get("orderMinSize", 5))

                # Round DOWN to 2 decimals to ensure we have enough balance
                sell_size = math.floor(shares * 100) / 100
                
                prices = json.loads(market_data.get("outcomePrices", "[]"))
                current_price = float(prices[i]) if i < len(prices) else 0.5

                if shares < min_size:
                    if not args.force:
                        print(f"Warning: Holding {shares} is less than min order size {min_size}. Use --force to buy up to minimum then sell all.")
                        continue
                    
                    # Buy to Sell logic
                    top_up_needed = round(min_size - shares + 0.1, 2) # Add small buffer
                    buy_price = min(0.99, current_price * 1.2) # 20% slippage for buy
                    
                    print(f"Small position detected ({shares} shares). Buying {top_up_needed} more to reach {min_size} minimum...")
                    buy_args = OrderArgs(
                        price=round(buy_price, 2),
                        size=top_up_needed,
                        token_id=token_id,
                        side="BUY"
                    )
                    signed_buy = client.create_order(buy_args)
                    buy_resp = client.post_order(signed_buy)
                    print(f"Buy Success! Response: {buy_resp}")
                    
                    # Re-calculate sell size
                    # Loop until balance updates (up to 10 seconds)
                    print("Waiting for balance to update...")
                    max_retries = 10
                    while max_retries > 0:
                        await asyncio.sleep(1)
                        new_resp = client.get_balance_allowance(params)
                        new_raw = int(new_resp.get('balance', '0'))
                        if new_raw > raw_balance:
                            break
                        max_retries -= 1
                        print(f"  Still waiting... ({max_retries} retries left)")

                    sell_size = math.floor((new_raw / 1_000_000) * 100) / 100
                    print(f"New balance confirmed: {sell_size} shares.")

                sell_price = max(0.01, current_price * 0.8) # 20% slippage tolerance
                
                print(f"Selling {sell_size} shares of '{outcome_name}' at limit price {sell_price:.2f}...")
                
                order_args = OrderArgs(
                    price=round(sell_price, 2),
                    size=sell_size,
                    token_id=token_id,
                    side="SELL"
                )
                
                signed_order = client.create_order(order_args)
                resp = client.post_order(signed_order)
                print(f"Order Success! Response: {resp}")
            else:
                print(f"  {outcome_name}: 0 shares")
        except Exception as e:
            print(f"  Error processing {outcome_name}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sell all Polymarket shares for a market.")
    parser.add_argument("--url", required=True, help="Polymarket market URL")
    parser.add_argument("--force", action="store_true", help="Buy up to minimum if balance is too low to sell")

    args = parser.parse_args()
    asyncio.run(sell_all(args.url))
