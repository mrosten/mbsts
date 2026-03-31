#!/usr/bin/env python3
"""
Test Darwin Algorithm Logic
Tests the improved algorithm with sample data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from darwin_agent import run_darwin_algo

def test_darwin_logic():
    print("🧪 Testing Darwin Algorithm Logic...")
    
    # Test case 1: VolSnap fired with downward move
    print("\n📊 Test 1: VolSnap fired, downward trend, negative odds")
    data1 = {
        'fired_scanners': ['VolSnap'],
        'trend_1h': 'DOWN',
        'btc_move_pct': -0.015,
        'odds_score': -15,
        'atr_5m': 25.0
    }
    
    result1 = run_darwin_algo(algo_code, data1)
    print(f"  Expected: BET_DOWN, Got: {result1} {'✅' if result1 == 'BET_DOWN' else '❌'}")
    
    # Test case 2: Nitro fired with upward move
    print("\n📊 Test 2: Nitro fired, upward trend, positive odds")
    data2 = {
        'fired_scanners': ['Nitro'],
        'trend_1h': 'UP',
        'btc_move_pct': 0.012,
        'odds_score': 12,
        'atr_5m': 30.0
    }
    
    result2 = run_darwin_algo(algo_code, data2)
    print(f"  Expected: BET_UP, Got: {result2} {'✅' if result2 == 'BET_UP' else '❌'}")
    
    # Test case 3: Multiple scanners confirming upward
    print("\n📊 Test 3: Multiple scanners (MOM, MM2) fired, upward trend")
    data3 = {
        'fired_scanners': ['MOM', 'MM2', 'NIT'],
        'trend_1h': 'UP',
        'btc_move_pct': 0.008,
        'odds_score': 8,
        'atr_5m': 20.0
    }
    
    result3 = run_darwin_algo(algo_code, data3)
    print(f"  Expected: BET_UP, Got: {result3} {'✅' if result3 == 'BET_UP' else '❌'}")
    
    # Test case 4: No scanners fired
    print("\n📊 Test 4: No scanners fired")
    data4 = {
        'fired_scanners': [],
        'trend_1h': 'NEUTRAL',
        'btc_move_pct': 0.003,
        'odds_score': 5,
        'atr_5m': 15.0
    }
    
    result4 = run_darwin_algo(algo_code, data4)
    print(f"  Expected: HOLD, Got: {result4} {'✅' if result4 == 'HOLD' else '❌'}")
    
    print(f"\n🎯 Test Summary: {sum(1 for r in [result1, result2, result3, result4] if r in ['BET_UP', 'BET_DOWN'])}/4 trading signals generated")

if __name__ == "__main__":
    # Load the improved algorithm
    algo_file = os.path.join(os.path.dirname(__file__), "darwin", "current_algo.py")
    if os.path.exists(algo_file):
        with open(algo_file, 'r') as f:
            algo_code = f.read()
        test_darwin_logic()
    else:
        print("❌ Algorithm file not found")
        sys.exit(1)
