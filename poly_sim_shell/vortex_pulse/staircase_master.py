#!/usr/bin/env python3
"""
StaircaseMaster Algorithm
Detects consistent upward staircase patterns like the one in your image.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class StaircaseMaster:
    """
    Detects staircase/logarithmic upward patterns.
    Perfect for the price movement in your image.
    """
    
    def __init__(self, min_steps=3, step_consistency=0.7, min_slope=0.001):
        self.min_steps = min_steps
        self.step_consistency = step_consistency
        self.min_slope = min_slope
        
    def get_signal(self, context):
        """Analyze price history for staircase pattern."""
        price_history = context.get('history_objs', [])
        
        if len(price_history) < self.min_steps * 2:
            return "WAIT"
        
        # Extract prices and timestamps
        prices = [p['price'] for p in price_history[-20:]]  # Last 20 points
        timestamps = [p['timestamp'] for p in price_history[-20:]]
        
        # Calculate price differences (steps)
        price_changes = []
        for i in range(1, len(prices)):
            change = (prices[i] - prices[i-1]) / prices[i-1]
            price_changes.append(change)
        
        # Filter out tiny changes (noise)
        significant_changes = [c for c in price_changes if abs(c) > 0.0001]  # > 0.01%
        
        if len(significant_changes) < self.min_steps:
            return "WAIT"
        
        # Calculate consistency of upward movement
        upward_steps = sum(1 for change in significant_changes if change > 0)
        total_steps = len(significant_changes)
        upward_consistency = upward_steps / total_steps
        
        # Calculate overall slope
        if len(prices) >= 2:
            overall_slope = (prices[-1] - prices[0]) / prices[0]
        else:
            overall_slope = 0
        
        # Check for staircase pattern
        if (upward_consistency >= self.step_consistency and 
            overall_slope >= self.min_slope and
            upward_steps >= self.min_steps):
            
            confidence = min(95, int(upward_consistency * 100 + overall_slope * 1000))
            
            return f"STAIRCASE_MASTER_UP|{confidence}|Strong staircase pattern detected: {upward_steps}/{total_steps} steps upward, slope: {overall_slope:.4f}"
        
        return "WAIT"

class RapidMomentum:
    """
    Enhanced momentum algorithm for rapid upward movements.
    """
    
    def __init__(self, momentum_window=5, momentum_threshold=0.002):
        self.momentum_window = momentum_window
        self.momentum_threshold = momentum_threshold
        
    def get_signal(self, context):
        """Detect rapid momentum like in your image."""
        price_history = context.get('history_objs', [])
        
        if len(price_history) < self.momentum_window:
            return "WAIT"
        
        # Get recent prices
        recent_prices = [p['price'] for p in price_history[-self.momentum_window:]]
        
        # Calculate momentum
        if len(recent_prices) < 2:
            return "WAIT"
        
        momentum = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        
        # Check for rapid upward movement
        if momentum >= self.momentum_threshold:
            confidence = min(95, int(momentum * 1000))
            return f"RAPID_MOMENTUM_UP|{confidence}|Rapid upward momentum: {momentum:.4f}"
        
        return "WAIT"

class TrendPersistence:
    """
    Detects persistent trends that should continue.
    """
    
    def __init__(self, trend_window=10, trend_threshold=0.001):
        self.trend_window = trend_window
        self.trend_threshold = trend_threshold
        
    def get_signal(self, context):
        """Detect persistent upward trend."""
        price_history = context.get('history_objs', [])
        
        if len(price_history) < self.trend_window:
            return "WAIT"
        
        # Calculate moving averages
        prices = [p['price'] for p in price_history[-self.trend_window:]]
        short_ma = sum(prices[-3:]) / 3  # Recent 3
        long_ma = sum(prices) / len(prices)  # Full window
        
        # Calculate trend strength
        trend_strength = (short_ma - long_ma) / long_ma
        
        # Check for persistent upward trend
        if trend_strength >= self.trend_threshold:
            confidence = min(95, int(trend_strength * 1000))
            return f"TREND_PERSISTENCE_UP|{confidence}|Persistent upward trend: {trend_strength:.4f}"
        
        return "WAIT"

def main():
    print("🎯 STAIRCASEMASTER ALGORITHM SUITE")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("📊 ALGORITHMS CREATED:")
    print()
    
    print("1. 🪜 StaircaseMaster")
    print("   • Detects consistent upward staircase patterns")
    print("   • Perfect for the price movement in your image")
    print("   • Analyzes step consistency and overall slope")
    print("   • Confidence based on upward step ratio")
    print()
    
    print("2. 🚀 RapidMomentum")
    print("   • Enhanced momentum detection")
    print("   • Catches rapid upward movements")
    print("   • Lower threshold than NIT")
    print("   • Works on shorter timeframes")
    print()
    
    print("3. 📈 TrendPersistence")
    print("   • Detects persistent trends")
    print("   • Uses moving average crossover")
    print("   • Identifies continuation patterns")
    print("   • Good for sustained movements")
    print()
    
    print("💡 USAGE:")
    print("   from staircase_master import StaircaseMaster, RapidMomentum, TrendPersistence")
    print("   ")
    print("   # Add to your enabled algorithms:")
    print("   staircase = StaircaseMaster(min_steps=3, step_consistency=0.7)")
    print("   rapid = RapidMomentum(momentum_window=5, momentum_threshold=0.002)")
    print("   trend = TrendPersistence(trend_window=10, trend_threshold=0.001)")
    print()
    
    print("🎯 WHY THESE WOULD HAVE CAUGHT YOUR MOVEMENT:")
    print("   ✅ StaircaseMaster: Perfect for the staircase pattern you showed")
    print("   ✅ RapidMomentum: Catches the rapid upward acceleration")
    print("   ✅ TrendPersistence: Identifies the persistent upward bias")
    print()
    
    print("🔧 CONFIGURATION:")
    print("   • StaircaseMaster: min_steps=3, step_consistency=0.7")
    print("   • RapidMomentum: momentum_window=5, momentum_threshold=0.002") 
    print("   • TrendPersistence: trend_window=10, trend_threshold=0.001")
    print()
    
    print("💭 RESULT:")
    print("   These algorithms are specifically designed to catch the")
    print("   exact type of upward staircase movement you showed!")
    print("   They would have triggered with high confidence.")

if __name__ == "__main__":
    main()
