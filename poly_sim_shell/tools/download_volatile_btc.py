"""
Download 1-second BTC data for August 5, 2024 (highly volatile day)
Uses Binance API to fetch BTCUSDT 1-second klines
"""
import requests
import pandas as pd
from datetime import datetime, timezone
import time

def download_binance_1s_data(symbol, start_date, end_date, output_file):
    """
    Download 1-second kline data from Binance
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        start_date: Start datetime (UTC)
        end_date: End datetime (UTC)
        output_file: Output CSV filename
    """
    base_url = "https://api.binance.com/api/v3/klines"
    
    # Convert to milliseconds timestamp
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    
    all_data = []
    current_start = start_ms
    
    print(f"Downloading {symbol} 1-second data from {start_date} to {end_date}...")
    
    while current_start < end_ms:
        params = {
            'symbol': symbol,
            'interval': '1s',
            'startTime': current_start,
            'endTime': end_ms,
            'limit': 1000  # Max limit per request
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
            
            all_data.extend(data)
            
            # Update start time for next batch
            current_start = data[-1][0] + 1
            
            print(f"  Downloaded {len(all_data)} candles so far...")
            time.sleep(0.1)  # Rate limiting
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    # Convert to DataFrame
    df = pd.DataFrame(all_data, columns=[
        'Open Time', 'Open', 'High', 'Low', 'Close', 'Volume',
        'Close Time', 'Quote Volume', 'Trades', 'Taker Buy Base',
        'Taker Buy Quote', 'Ignore'
    ])
    
    # Convert timestamps to datetime
    df['Open Time'] = pd.to_datetime(df['Open Time'], unit='ms')
    df['Close Time'] = pd.to_datetime(df['Close Time'], unit='ms')
    
    # Convert price columns to float
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"\n✅ Saved {len(df)} candles to {output_file}")
    print(f"   Date range: {df['Open Time'].min()} to {df['Open Time'].max()}")
    print(f"   Price range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")
    
    return df

if __name__ == "__main__":
    # August 5, 2024 - Most volatile day in 2024 (19% intraday volatility)
    start_date = datetime(2024, 8, 5, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2024, 8, 5, 23, 59, 59, tzinfo=timezone.utc)
    
    output_file = "data/BTC_Aug5_2024_volatile.csv"
    
    df = download_binance_1s_data('BTCUSDT', start_date, end_date, output_file)
