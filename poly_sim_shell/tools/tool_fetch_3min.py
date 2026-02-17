"""
Tool: Binance 3-Min Data Fetcher

Downloads 3-minute granularity k-line data from Binance.
- Used for generating datasets for the T+9 Trend Simulator.
- Saves to data/ directory.
"""
import requests
import pandas as pd
from datetime import datetime, timezone

# 2025-12-01 00:00:00 UTC
# Using UTC timezone explicitly
start_dt = datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
start_ts = int(start_dt.timestamp() * 1000) # Binance uses ms

# 24 hours later
end_ts = start_ts + (24 * 60 * 60 * 1000)

url = "https://api.binance.com/api/v3/klines"
params = {
    "symbol": "BTCUSDT",
    "interval": "3m",
    "startTime": start_ts,
    "endTime": end_ts,
    "limit": 1000 
}

print(f"Fetching data for {start_dt}...")
try:
    resp = requests.get(url, params=params)
    data = resp.json()

    if isinstance(data, list) and len(data) > 0:
        print(f"Received {len(data)} candles.")
        
        # Columns based on Binance API response structure
        # [OpenTime, Open, High, Low, Close, Volume, CloseTime, QuoteAssetVolume, NumberOfTrades, TakerBuyBaseAssetVolume, TakerBuyQuoteAssetVolume, Ignore]
        columns = ['Open Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close Time', 'Quote Asset Volume', 'Number of Trades', 'Taker Buy Base Asset Volume', 'Taker Buy Quote Asset Volume', 'Ignore']
        
        formatted_data = []
        for row in data:
            # Timestamp to readable string
            ts = int(row[0]) / 1000
            readable_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            
            # Construct row (keep numbers as strings or convert? Pandas handles CSV writing well)
            new_row = [readable_date] + row[1:]
            formatted_data.append(new_row)
            
        df = pd.DataFrame(formatted_data, columns=columns)
        
        outfile = "poly_sim_shell/data/BTC_Dec1_2025_3min.csv"
        df.to_csv(outfile, index=False)
        print(f"SUCCESS: Saved to {outfile}")
    else:
        print("ERROR: No data received. Response:", data)

except Exception as e:
    print(f"EXCEPTION: {e}")
