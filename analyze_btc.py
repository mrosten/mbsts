import argparse
import sys
from datetime import datetime
import market_analysis
import sys
import io

# Force UTF-8 output for Windows Console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def print_analysis(url):
    print(f"\nAnalyzing: {url}")
    print("Fetching market data...")
    
    results = market_analysis.analyze_market_data(url)
    
    if "error" in results:
        print(f"Error: {results['error']}")
        return

    # Display
    print("\n" + "="*40)
    print(f" 📊 BITCOIN 15M MARKET ANALYSIS")
    print("="*40)
    
    start_dt = datetime.fromtimestamp(results['start_ts'])
    end_dt = datetime.fromtimestamp(results['end_ts'])
    
    print(f"\nStart Time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End Time:   {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    mins = int(results['time_left_s'] // 60)
    secs = int(results['time_left_s'] % 60)
    
    if results['time_left_s'] > 0:
        print(f"\n⏳ TIME LEFT: {mins}m {secs}s")
    else:
        print(f"\n⏳ STATUS: EXPIRED")

    print("-" * 30)
    
    strike = results.get('strike_price')
    if strike:
        print(f"🎯 PRICE TO BEAT (Strike): ${strike:,.2f}  (Source: {results['strike_source']})")
    else:
        print(f"🎯 PRICE TO BEAT (Strike): [Fetching Failed]")
        
    curr = results.get('current_price')
    if curr:
        print(f"💰 CURRENT PRICE:        ${curr:,.2f}  (Source: {results['current_source']} Live)")
    
    if strike and curr:
        diff = results['diff']
        color = "🟢 UP" if diff > 0 else "🔴 DOWN"
        print(f"\n🚀 STATUS: {color} by ${abs(diff):.2f}")
        
    if "recommendation" in results:
        print(f"\n📢 RECOMMENDATION: {results['recommendation']}")
    
    # TA Section
    if 'rsi' in results:
        print("\n" + "-"*40)
        print(" 📈 TECHNICAL INDICATORS (15m Candles)")
        print("-" * 40)
        print(f"RSI (14):         {results['rsi']:.1f} ({results['rsi_status']})")
        print(f"Bollinger Bands:  ${results['bb_lower']:,.0f} - ${results['bb_upper']:,.0f} ({results['bb_status']})")
        print(f"Volatility:       {results.get('vol_status', 'N/A')} (ATR: ${results.get('atr', 0):.2f})")
        print(f"Trend Signal:     {results['trend']}")
        print(f"SMA 50:           ${results['sma50']:,.0f} ({results['sma_status']})")
        print("-" * 40 + "\n")
    else:
        print("\n⚠️ Technical Analysis Data Unavailable (Binance connection issue?)\n")

    print("="*40 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    print_analysis(args.url)
