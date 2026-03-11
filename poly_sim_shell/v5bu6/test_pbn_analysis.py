#!/usr/bin/env python3
"""
PBN Analysis Test Script
Tests the Momentum scanner's PBN analysis logic with fake data
"""

import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanners import MomentumScanner

def create_test_context(btc_price=73000, btc_open=72900, up_ask=0.52, down_ask=0.48, 
                       atr_5m=40.0, trend_1h="NEUTRAL", rsi_1m=50, odds_score=2.0):
    """Create a fake context for testing PBN analysis"""
    return {
        "elapsed": 285,  # T-15s
        "up_bid": up_ask - 0.01,
        "down_bid": down_ask - 0.01,
        "up_ask": up_ask,
        "down_ask": down_ask,
        "atr_5m": atr_5m,
        "trend_1h": trend_1h,
        "trend_1h": "NEUTRAL",
        "odds_score": odds_score,
        "rsi_1m": rsi_1m,
        "velocity": 100,
        "window_analytics": {},
        "btc_price": btc_price,
        "btc_open": btc_open,
        "btc_dyn_rng": 200
    }

def test_pbn_analysis():
    """Test PBN analysis with various scenarios"""
    print("=" * 60)
    print("PBN ANALYSIS TEST SCRIPT")
    print("=" * 60)
    
    # Create Momentum scanner
    scanner = MomentumScanner()
    scanner.buy_mode = "PRE"
    scanner.pre_buy_triggered = False
    
    # Test scenarios
    test_cases = [
        {
            "name": "Bullish Scenario - Strong UP Signal",
            "context": create_test_context(
                btc_price=73200, btc_open=72900,  # BTC up $300
                up_ask=0.55, down_ask=0.45,       # UP premium
                atr_5m=45.0, trend_1h="S-UP", rsi_1m=35, odds_score=8.0
            )
        },
        {
            "name": "Bearish Scenario - Strong DOWN Signal", 
            "context": create_test_context(
                btc_price=72600, btc_open=72900,  # BTC down $300
                up_ask=0.48, down_ask=0.52,       # DOWN premium
                atr_5m=55.0, trend_1h="S-DOWN", rsi_1m=65, odds_score=-8.0
            )
        },
        {
            "name": "Indecisive Scenario - Close Prices",
            "context": create_test_context(
                btc_price=72950, btc_open=72900,  # BTC up $50
                up_ask=0.51, down_ask=0.49,       # Small spread
                atr_5m=35.0, trend_1h="NEUTRAL", rsi_1m=50, odds_score=1.0
            )
        },
        {
            "name": "High Volatility - Chaos ATR",
            "context": create_test_context(
                btc_price=73100, btc_open=72900,  # BTC up $200
                up_ask=0.54, down_ask=0.46,       # Moderate spread
                atr_5m=125.0, trend_1h="M-UP", rsi_1m=40, odds_score=5.0
            )
        },
        {
            "name": "Low Volatility - Stable ATR",
            "context": create_test_context(
                btc_price=72980, btc_open=72900,  # BTC up $80
                up_ask=0.505, down_ask=0.495,     # Very tight spread
                atr_5m=15.0, trend_1h="W-UP", rsi_1m=45, odds_score=2.0
            )
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"TEST CASE {i}: {test_case['name']}")
        print(f"{'='*60}")
        
        # Reset scanner for each test
        scanner.pre_buy_triggered = False
        scanner.pbn_analysis = None
        scanner.triggered_signal = None
        
        # Get signal
        signal = scanner.get_signal(test_case['context'])
        
        print(f"\nSignal Returned: {signal}")
        
        # Display analysis if available
        if hasattr(scanner, 'pbn_analysis') and scanner.pbn_analysis:
            analysis = scanner.pbn_analysis
            print(f"\n🧠 PBN MULTI-FACTOR ANALYSIS:")
            print(f"  Decision: {analysis.get('decision', 'SKIP')} | Confidence: {analysis.get('confidence', 'NONE')} | Score: {analysis.get('net_score', 0):+d}")
            print(f"  UP Score: {analysis.get('up_score', 0)} | DOWN Score: {analysis.get('down_score', 0)}")
            print(f"  Factors:")
            for factor in analysis.get('factors', []):
                print(f"    • {factor}")
            print(f"  Final Reason: {analysis.get('reason', 'None')}")
        else:
            print("❌ No PBN analysis found!")
        
        print(f"\nContext Details:")
        ctx = test_case['context']
        print(f"  BTC: ${ctx['btc_price']} (Open: ${ctx['btc_open']}) | Change: ${ctx['btc_price'] - ctx['btc_open']:+.0f}")
        print(f"  Prices: UP {ctx['up_ask']*100:.1f}¢ / DN {ctx['down_ask']*100:.1f}¢ | Spread: {(ctx['up_ask'] - ctx['down_ask'])*100:.1f}¢")
        print(f"  ATR: {ctx['atr_5m']:.1f} | Trend: {ctx['trend_1h']} | RSI: {ctx['rsi_1m']:.0f} | Odds: {ctx['odds_score']:+.1f}¢")

def test_atr_floor_scenarios():
    """Test different ATR floor values"""
    print(f"\n{'='*60}")
    print("ATR FLOOR TEST")
    print(f"{'='*60}")
    
    scanner = MomentumScanner()
    scanner.buy_mode = "PRE"
    scanner.adv_settings["atr_floor"] = 50.0  # High floor
    
    # Test with ATR below floor
    context_low_atr = create_test_context(atr_5m=30.0, up_ask=0.52, down_ask=0.48)
    scanner.pre_buy_triggered = False
    scanner.pbn_analysis = None
    
    signal = scanner.get_signal(context_low_atr)
    
    print(f"\nATR Below Floor (30.0 < 50.0):")
    print(f"Signal: {signal}")
    if scanner.pbn_analysis:
        print(f"Analysis: {scanner.pbn_analysis['decision']} ({scanner.pbn_analysis['reason']})")
    else:
        print("❌ No analysis created")

if __name__ == "__main__":
    try:
        test_pbn_analysis()
        test_atr_floor_scenarios()
        
        print(f"\n{'='*60}")
        print("TEST COMPLETED")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
