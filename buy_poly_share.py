import os
import argparse
import asyncio
import json
import requests
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs

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

async def place_order(args):
    """Parse URL, fetch market data, and place the order."""
    # 1. Extract slug from URL
    url_parts = args.url.strip("/").split("?")[0].split("/")
    slug = url_parts[-1]
    
    print(f"Resolving market slug: {slug}")
    market_data = get_market_data(slug)
    if not market_data:
        return

    # 2. Get Token ID and Market details
    token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
    outcomes = json.loads(market_data.get("outcomes", "[]"))
    
    if not token_ids or len(token_ids) < 2:
        print("Error: Could not find token IDs for this market.")
        return

    # Map outcome to index
    outcome_idx = 0 if args.outcome.lower() == "up" else 1
    target_token_id = token_ids[outcome_idx]
    target_outcome_name = outcomes[outcome_idx] if outcome_idx < len(outcomes) else args.outcome
    
    # Get order metadata for min size
    order_min_size = market_data.get("orderMinSize", 5) 
    current_price = float(json.loads(market_data.get("outcomePrices", "[]"))[outcome_idx])
    
    print(f"Targeting Outcome: {target_outcome_name} (token_id: {target_token_id})")
    print(f"Market Price: ${current_price:.4f} | Min Order Size: {order_min_size} shares")

    # 3. Initialize Client
    client = get_client()
    if not client:
        return

    # 4. Prepare Order
    side = args.action.upper() # BUY or SELL
    
    try:
        if args.type == "limit":
            if args.price is None:
                print("Error: --price is required for limit orders.")
                return
            price = round(float(args.price), 2)
            size = round(float(args.amount) / price, 2)
            
            if size < order_min_size:
                 print(f"Error: Command would buy {size} shares, but market requires min {order_min_size} shares.")
                 print(f"To buy at ${price}, you need at least ${round(order_min_size * price, 2)} USD.")
                 return
                 
            print(f"Placing LIMIT {side} order for ${args.amount} at price {price} (~{size} shares)...")
        else:
            # Simulate Market Order
            price = 0.99 if side == "BUY" else 0.01
            size = round(float(args.amount) / price, 2)
            
            if size < order_min_size:
                 print(f"Error: Market order for ${args.amount} is too small ({size} shares). Min: {order_min_size} shares.")
                 return
                 
            print(f"Placing MARKET {side} order for ${args.amount} (as Limit Order at {price})...")

        order_args = OrderArgs(
            price=price,
            size=size,
            token_id=target_token_id,
            side=side
        )
        
        # Sign and post the order
        signed_order = client.create_order(order_args)
        resp = client.post_order(signed_order)
        print(f"Order Success! Response: {resp}")
    except Exception as e:
        print(f"Error placing order: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Buy/Sell Polymarket shares via CLI.")
    parser.add_argument("--url", required=True, help="Polymarket market URL")
    parser.add_argument("--amount", type=float, required=True, help="Investment amount in USD")
    parser.add_argument("--price", type=float, help="Limit price (required for limit orders)")
    parser.add_argument("--outcome", choices=["up", "down"], required=True, help="Outcome to bet on")
    parser.add_argument("--action", choices=["buy", "sell"], required=True, help="Action to take")
    parser.add_argument("--type", choices=["limit", "market"], default="limit", help="Order type (default: limit)")

    args = parser.parse_args()
    asyncio.run(place_order(args))
