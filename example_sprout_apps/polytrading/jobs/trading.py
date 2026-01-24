import os
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
from sprout.log.logger import Logger
import aiohttp
import time
import json
from example_sprout_apps.polytrading.data import classes as db

logger = Logger('polytrading_job')

# Load environment variables
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon Mainnet

def get_client():
    if not PRIVATE_KEY:
        print("Error: PRIVATE_KEY not found in environment variables")
        return None
    
    # Derive the funder address if not provided explicitly
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
        raise
        
    return client

async def fetch_active_markets():
    url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=5"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                logger.process(f"Fetched {len(data)} active events from Gamma API")
                for event in data:
                    title = event.get('title', 'No Title')
                    markets = event.get('markets', [])
                    market_count = len(markets)
                    event_id = event.get('id', 'unknown')
                    
                    # Save to DB
                    try:
                        timestamp = int(time.time())
                        # Unique ID for the DB record: eventID_timestamp
                        entry_id = f"{event_id}_{timestamp}"
                        
                        market_record = db.ActiveMarket(entry_id)
                        await market_record.set(title=title, market_count=market_count, timestamp=timestamp)
                        logger.process(f"Saved Event: {title} ({market_count} markets)")
                    except Exception as e:
                        logger.process(f"Error saving to DB: {e}")

            else:
                logger.process(f"Failed to fetch events: {response.status}")

async def fetch_target_prices():
    slug = "btc-updown-15m-1769282100"
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if isinstance(data, list) and len(data) > 0:
                    event = data[0]
                else: 
                     # Sometimes API returns dict, sometimes list
                    event = data

                markets = event.get('markets', [])
                for market in markets:
                    outcomes = json.loads(market.get('outcomes', '[]'))
                    outcome_prices = json.loads(market.get('outcomePrices', '[]'))
                    market_id = market.get('id')
                    
                    if len(outcomes) == len(outcome_prices):
                        timestamp = int(time.time())
                        for i, outcome in enumerate(outcomes):
                            price = float(outcome_prices[i]) if i < len(outcome_prices) else 0.0
                            entry_id = f"{market_id}_{outcome}_{timestamp}"
                            
                            try:
                                record = db.PriceHistory(entry_id)
                                await record.set(market_id=market_id, outcome=outcome, price=price, timestamp=timestamp)
                                logger.process(f"Saved Price: {outcome} = {price}")
                            except Exception as e:
                                logger.process(f"Error saving price: {e}")
            else:
                logger.process(f"Failed to fetch target event: {response.status}")


async def run_trading_cycle():
    """
    This function is called by the scheduler.
    """
    logger.process("--- Starting Trading Cycle ---")
    try:
        client = get_client()
        if not client:
            return

        # Check Balance
        collateral = client.get_collateral_address()
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        bal = client.get_balance_allowance(params)
        logger.process(f"Current Balance/Allowance: {bal}")
        
        # Check Open Orders
        orders = client.get_orders()
        logger.process(f"Open Orders: {len(orders)}")
        for o in orders:
             logger.process(f"- Order ID: {o.get('orderID')}, Side: {o.get('side')}, Price: {o.get('price')}")
             
        # Fetch Market Data
        await fetch_active_markets()
        await fetch_target_prices()

        # Placeholder for strategy logic
        # e.g., if favorable_condition(): place_order(...)
        
    except Exception as e:
        logger.process(f"Error in trading cycle: {e}")
    logger.process("--- Trading Cycle Complete ---")
