
"""
Tool: Binance 1-Sec Data Fetcher

Downloads 1-second granularity k-line data from Binance API.
- Configured for BTCUSDT.
- Saves to data/ folder for use with Swing Simulator.
"""
import asyncio
import json
import logging
import csv
import sys
import os
from datetime import datetime, timezone, timedelta
import requests

# Constants
SYMBOL = 'BTCUSDT'
INTERVAL = '1s'
# Target Date: Dec 1, 2024
START_DT = datetime(2024, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DT = datetime(2024, 12, 2, 0, 0, 0, tzinfo=timezone.utc)

OUTPUT_FILE = "poly_sim_shell/data/BTC_Dec1_2024_1s.csv"

# setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_klines(start_ts, end_ts):
    base_url = "https://api.binance.com/api/v3/klines"
    limit = 1000
    all_data = []
    
    current_start = start_ts
    
    while current_start < end_ts:
        logging.info(f"Fetching from {datetime.fromtimestamp(current_start/1000, tz=timezone.utc)}...")
        params = {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "startTime": current_start,
            "endTime": end_ts,
            "limit": limit
        }
        
        try:
            resp = requests.get(base_url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if not data:
                    break
                    
                all_data.extend(data)
                
                # Update start time for next batch (last Close Time + 1ms)
                last_close_ts = data[-1][6]
                current_start = last_close_ts + 1
                
                # Safety break
                if len(data) < limit:
                     if current_start >= end_ts:
                         break
            else:
                logging.error(f"Error {resp.status_code}: {resp.text}")
                break
                
        except Exception as e:
            logging.error(f"Exception: {e}")
            break
            
    return all_data

def save_to_csv(klines, filename):
    # Binance Klines: [Open Time, Open, High, Low, Close, Volume, Close Time, ...]
    # We want: open_time, open, high, low, close, volume
    
    headers = ["Open Time", "Open", "High", "Low", "Close", "Volume"]
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for k in klines:
            # Format TS
            dt_obj = datetime.fromtimestamp(k[0]/1000, tz=timezone.utc)
            ts_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            
            row = [
                ts_str,
                k[1], # Open
                k[2], # High
                k[3], # Low
                k[4], # Close
                k[5]  # Volume
            ]
            writer.writerow(row)
            
    logging.info(f"Saved {len(klines)} rows to {filename}")

if __name__ == "__main__":
    start_ts = int(START_DT.timestamp() * 1000)
    end_ts = int(END_DT.timestamp() * 1000)
    
    logging.info(f"Downloading 1s data for {START_DT} to {END_DT}")
    
    klines = fetch_klines(start_ts, end_ts)
    save_to_csv(klines, OUTPUT_FILE)
    
