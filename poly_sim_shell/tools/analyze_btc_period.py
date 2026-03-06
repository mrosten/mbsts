import pandas as pd
import numpy as np

def analyze_period(file_path):
    df = pd.read_csv(file_path)
    df['Open Time'] = pd.to_datetime(df['Open Time'])
    
    # 1. Price Range
    start_price = df.iloc[0]['Open']
    end_price = df.iloc[-1]['Close']
    high_price = df['High'].max()
    low_price = df['Low'].min()
    pct_change = (end_price - start_price) / start_price * 100
    
    # 2. Volatility (ATR-like calculation for 5m windows)
    # Group by 5-minute intervals
    df.set_index('Open Time', inplace=True)
    df_5m = df.resample('5min').agg({
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Open': 'first'
    })
    
    # Simple ATR (True Range = High - Low)
    df_5m['TR'] = df_5m['High'] - df_5m['Low']
    avg_atr = df_5m['TR'].mean()
    max_atr = df_5m['TR'].max()
    min_atr = df_5m['TR'].min()
    
    # 3. Market Regime Distribution (based on suggested Chaos Boundary of 75)
    chaos_count = (df_5m['TR'] > 75).sum()
    stable_count = (df_5m['TR'] < 25).sum()
    total_5m = len(df_5m)
    
    print(f"--- Analysis for {file_path} ---")
    print(f"Price: ${start_price:.2f} -> ${end_price:.2f} ({pct_change:+.2f}%)")
    print(f"Range: ${low_price:.2f} - ${high_price:.2f}")
    print(f"\nVolatility (5m Windows):")
    print(f"  Avg ATR: ${avg_atr:.2f}")
    print(f"  Max ATR: ${max_atr:.2f}")
    print(f"  Min ATR: ${min_atr:.2f}")
    print(f"\nRegime Stats (using current boundaries):")
    print(f"  Chaos (> $75): {chaos_count} intervals ({(chaos_count/total_5m)*100:.1f}%)")
    print(f"  Stable (< $25): {stable_count} intervals ({(stable_count/total_5m)*100:.1f}%)")
    print(f"  Normal: {total_5m - chaos_count - stable_count} intervals")

    # 4. Find potential "Bull Traps" or Sharp Reversals
    # (Simplified: looking for 5m candles with large wicks or immediate reversals)
    df_5m['Body'] = abs(df_5m['Close'] - df_5m['Open'])
    df_5m['Wick'] = df_5m['TR'] - df_5m['Body']
    big_wicks = df_5m[df_5m['Wick'] > 40]
    print(f"\nPotential Reversal Zones (Wicks > $40): {len(big_wicks)}")

if __name__ == "__main__":
    analyze_period('binance_btc_20260302_1329_1919_EST.csv')
