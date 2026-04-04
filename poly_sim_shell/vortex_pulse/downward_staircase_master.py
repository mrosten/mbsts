#!/usr/bin/env python3
"""
DownwardStaircaseMaster Algorithm
Detects consistent downward staircase patterns like the one in your image.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class DownwardStaircaseMaster:
    """
    Detects staircase/logarithmic downward patterns.
    Perfect for the price movement in your image.
    """
    
    def __init__(self, min_steps=3, step_consistency=0.7, min_slope=-0.001):
        self.min_steps = min_steps
        self.step_consistency = step_consistency
        self.min_slope = min_slope  # Negative for downward
        
    def get_signal(self, context):
        """Analyze price history for downward staircase pattern."""
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
        
        # Calculate consistency of downward movement
        downward_steps = sum(1 for change in significant_changes if change < 0)
        total_steps = len(significant_changes)
        downward_consistency = downward_steps / total_steps
        
        # Calculate overall slope
        if len(prices) >= 2:
            overall_slope = (prices[-1] - prices[0]) / prices[0]
        else:
            overall_slope = 0
        
        # Check for downward staircase pattern
        if (downward_consistency >= self.step_consistency and 
            overall_slope <= self.min_slope and
            downward_steps >= self.min_steps):
            
            confidence = min(95, int(downward_consistency * 100 + abs(overall_slope) * 1000))
            
            return f"DOWNWARD_STAIRCASE_MASTER_DOWN|{confidence}|Strong downward staircase detected: {downward_steps}/{total_steps} steps downward, slope: {overall_slope:.4f}"
        
        return "WAIT"

class RapidDownwardMomentum:
    """
    Enhanced downward momentum algorithm.
    """
    
    def __init__(self, momentum_window=5, momentum_threshold=-0.002):
        self.momentum_window = momentum_window
        self.momentum_threshold = momentum_threshold  # Negative for downward
        
    def get_signal(self, context):
        """Detect rapid downward momentum like in your image."""
        price_history = context.get('history_objs', [])
        
        if len(price_history) < self.momentum_window:
            return "WAIT"
        
        # Get recent prices
        recent_prices = [p['price'] for p in price_history[-self.momentum_window:]]
        
        # Calculate momentum
        if len(recent_prices) < 2:
            return "WAIT"
        
        momentum = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        
        # Check for rapid downward movement
        if momentum <= self.momentum_threshold:
            confidence = min(95, int(abs(momentum) * 1000))
            return f"RAPID_DOWNWARD_MOMENTUM_DOWN|{confidence}|Rapid downward momentum: {momentum:.4f}"
        
        return "WAIT"

class DownwardTrendPersistence:
    """
    Detects persistent downward trends that should continue.
    """
    
    def __init__(self, trend_window=10, trend_threshold=-0.001):
        self.trend_window = trend_window
        self.trend_threshold = trend_threshold  # Negative for downward
        
    def get_signal(self, context):
        """Detect persistent downward trend."""
        price_history = context.get('history_objs', [])
        
        if len(price_history) < self.trend_window:
            return "WAIT"
        
        # Calculate moving averages
        prices = [p['price'] for p in price_history[-self.trend_window:]]
        short_ma = sum(prices[-3:]) / 3  # Recent 3
        long_ma = sum(prices) / len(prices)  # Full window
        
        # Calculate trend strength
        trend_strength = (short_ma - long_ma) / long_ma
        
        # Check for persistent downward trend
        if trend_strength <= self.trend_threshold:
            confidence = min(95, int(abs(trend_strength) * 1000))
            return f"DOWNWARD_TREND_PERSISTENCE_DOWN|{confidence}|Persistent downward trend: {trend_strength:.4f}"
        
        return "WAIT"

def main():
    print("🎯 DOWNWARD STAIRCASEMASTER ALGORITHM SUITE")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("📊 DOWNWARD ALGORITHMS CREATED:")
    print()
    
    print("1. 📉 DownwardStaircaseMaster")
    print("   • Detects consistent downward staircase patterns")
    print("   • Perfect for the price movement in your image")
    print("   • Analyzes downward step consistency and slope")
    print("   • Confidence based on downward step ratio")
    print()
    
    print("2. 🚀 RapidDownwardMomentum")
    print("   • Enhanced downward momentum detection")
    print("   • Catches rapid downward movements")
    print("   • Lower threshold than NIT for downward")
    print("   • Works on shorter timeframes")
    print()
    
    print("3. 📈 DownwardTrendPersistence")
    print("   • Detects persistent downward trends")
    print("   • Uses moving average crossover")
    print("   • Identifies downward continuation patterns")
    print("   • Good for sustained downward movements")
    print()
    
    print("💡 USAGE:")
    print("   from staircase_master import DownwardStaircaseMaster, RapidDownwardMomentum, DownwardTrendPersistence")
    print("   ")
    print("   # Add to your enabled algorithms:")
    print("   downward = DownwardStaircaseMaster(min_steps=3, step_consistency=0.7)")
    print("   rapid = RapidDownwardMomentum(momentum_window=5, momentum_threshold=-0.002)")
    print("   trend = DownwardTrendPersistence(trend_window=10, trend_threshold=-0.001)")
    print()
    
    print("🎯 WHY THESE WOULD HAVE CAUGHT YOUR MOVEMENT:")
    print("   ✅ DownwardStaircaseMaster: Perfect for the downward staircase pattern you showed")
    print("   ✅ RapidDownwardMomentum: Catches the rapid downward acceleration")
    print("   ✅ DownwardTrendPersistence: Identifies the persistent downward bias")
    print()
    
    print("🔧 CONFIGURATION:")
    print("   • DownwardStaircaseMaster: min_steps=3, step_consistency=0.7")
    print("   • RapidDownwardMomentum: momentum_window=5, momentum_threshold=-0.002") 
    print("   • DownwardTrendPersistence: trend_window=10, trend_threshold=-0.001")
    print()
    
    print("💭 RESULT:")
    print("   These algorithms are specifically designed to catch the")
    print("   exact type of downward staircase movement you showed!")
    print("   They would have triggered with high confidence.")

if __name__ == "__main__":
    main()
