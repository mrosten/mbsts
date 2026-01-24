
import asyncio
import time
import aiohttp
from example_sprout_apps.financial.data import classes as db

# Fetch real price using aiohttp (already in project)
async def fetch_price(symbol, session):
    try:
        # Coinbase API for crypto
        if symbol == "BTC":
            url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
            async with session.get(url) as response:
                data = await response.json()
                return float(data['data']['amount'])
        
        # Yahoo Finance or other for stocks is harder without html parsing/library.
        # simulating stock flux for others for now, focusing on BTC as requested.
        elif symbol == "AAPL":
            return 150.0 # Placeholder
            
        return 100.0
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return 0.0

async def track_stocks():
    import time as time_module
    print(f"[Financial] {time_module.strftime('%H:%M:%S')} - Tracking stocks (Real BTC)...")
    
    symbols = ["BTC"]
    
    async with aiohttp.ClientSession() as session:
        for sym in symbols:
            price = await fetch_price(sym, session)
            timestamp = int(time.time())
            
            entry_id = f"{sym}_{timestamp}"
            
            stock = db.StockTicker(entry_id)
            await stock.set(symbol=sym, price=price, timestamp=timestamp)
            
            print(f"[Financial] {sym}: ${price:,.2f} stored in DB.")
