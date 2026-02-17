"""
Version 5.0
Simulator: Strong Uptrend Detection Strategy (1-Sec CSV Data)

This simulator processes historical 1-second BTC data from CSV files and applies
the "Strong Uptrend Detection" strategy. It continuously scans prices from minute 5-9
and executes a trade when a strong uptrend is detected.

Features:
- CSV Data Processing (1-second intervals)
- Continuous 5-Second Sampling (T+5 to T+9)
- Strong Uptrend Detection (momentum-based)
- Bollinger Band Edge Detection for T+9 Fallback
- Conditional Price Thresholds (0.55 at BB edge, 0.80 otherwise)
"""
import os
import glob
import pandas as pd
import numpy as np
import time
import math
import csv
from datetime import datetime, timedelta

# --- Configuration ---
DEFAULT_BUDGET = 50.0
DRIFT_THRESHOLD = 0.0004         # 0.04% (Standard Trend Trigger)
SPREAD = 0.02
ROLLING_WINDOW_SEC = 300         # 5 minutes for stable volatility

# --- Pricing Model ---
def polymarket_pricing_model(current_price, strike_price, time_remaining_seconds, volatility_per_second):
    if time_remaining_seconds <= 0:
        return (0.99, 0.01) if current_price > strike_price else (0.01, 0.99)

    div_pct = (current_price - strike_price) / strike_price
    volatility_remaining = volatility_per_second * np.sqrt(time_remaining_seconds)

    if volatility_remaining == 0:
        up_price = 0.99 if div_pct > 0 else 0.01
        return up_price, 1.0 - up_price

    z_score = div_pct / volatility_remaining
    prob_up = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
    
    # Spread adjustment
    up_price = max(0.001, min(0.999, prob_up * (1 - SPREAD)))
    down_price = max(0.001, min(0.999, (1 - prob_up) * (1 - SPREAD)))

    return up_price, down_price

# --- Bollinger Band Calculation ---
def calculate_bollinger_metrics(checkpoints):
    """
    Calculate Bollinger Band metrics for position sizing and risk assessment.
    
    Returns a dictionary with:
    - at_edge: True if price is within 10% of upper or lower band
    - position: 0.0 (lower band) to 1.0 (upper band), 0.5 = middle
    - size_multiplier: 0.5x (at edges) to 1.5x (at middle) for position sizing
    - band_width: Width of the band (volatility measure)
    
    Uses 36-period (3 minutes at 5-second intervals) SMA with 2 standard deviations.
    """
    # 3 minutes = 180 seconds, at 5-second intervals = 36 samples
    BB_PERIOD = 36
    
    # Default values when insufficient data
    default_result = {
        "at_edge": False,
        "position": 0.5,  # Assume middle
        "size_multiplier": 1.0,  # Baseline
        "band_width": 0.0,
        "sma": 0.0,
        "upper_band": 0.0,
        "lower_band": 0.0
    }
    
    if len(checkpoints) < BB_PERIOD:
        return default_result
    
    # Get sorted price history
    checkpoint_times = sorted(checkpoints.keys())
    prices = [checkpoints[t] for t in checkpoint_times]
    
    # Use last 36 samples (3 minutes) for calculation
    recent_prices = prices[-BB_PERIOD:]
    current_price = recent_prices[-1]
    
    # Calculate Simple Moving Average (SMA)
    sma = sum(recent_prices) / len(recent_prices)
    
    # Calculate Standard Deviation
    variance = sum((p - sma) ** 2 for p in recent_prices) / len(recent_prices)
    std_dev = variance ** 0.5
    
    # Bollinger Bands: SMA ± 2*StdDev
    upper_band = sma + (2 * std_dev)
    lower_band = sma - (2 * std_dev)
    
    # Calculate band width
    band_width = upper_band - lower_band
    
    # Calculate position within band (0.0 = lower, 0.5 = middle, 1.0 = upper)
    if band_width > 0:
        position = (current_price - lower_band) / band_width
        position = max(0.0, min(1.0, position))  # Clamp to [0, 1]
    else:
        position = 0.5  # No volatility, assume middle
    
    # Calculate distance from middle (0.0 = at middle, 0.5 = at edge)
    distance_from_middle = abs(position - 0.5)
    
    # Position sizing multiplier based on distance from middle
    # At middle (distance=0.0): 1.5x (low risk, high confidence)
    # At edges (distance=0.5): 0.5x (high risk, reduce exposure)
    # Linear interpolation: multiplier = 1.5 - (distance_from_middle * 2.0)
    size_multiplier = 1.5 - (distance_from_middle * 2.0)
    size_multiplier = max(0.5, min(1.5, size_multiplier))  # Clamp to [0.5, 1.5]
    
    # Edge detection (within 10% of band boundaries)
    edge_threshold = band_width * 0.10
    at_upper_edge = current_price >= (upper_band - edge_threshold)
    at_lower_edge = current_price <= (lower_band + edge_threshold)
    at_edge = at_upper_edge or at_lower_edge
    
    return {
        "at_edge": at_edge,
        "position": position,
        "size_multiplier": size_multiplier,
        "band_width": band_width,
        "sma": sma,
        "upper_band": upper_band,
        "lower_band": lower_band
    }


# --- Simulation Logic ---
class StrongUptrendSimulation:
    def __init__(self, csv_file, balance, use_bb_sizing=True):
        self.df = pd.read_csv(csv_file)
        # Handle formats
        try:
            self.df['Open Time'] = pd.to_datetime(self.df['Open Time'])
        except:
             pass
             
        self.balance = float(balance)
        self.start_balance = float(balance)
        self.trades = []  # List of trade dictionaries for CSV export
        self.wins = 0
        self.losses = 0
        self.use_bb_sizing = use_bb_sizing  # Toggle for BB-based position sizing

        # Pre-calc Volatility
        self.df['Log_Ret'] = np.log(self.df['Close'] / self.df['Close'].shift(1))
        self.df['Roll_Std'] = self.df['Log_Ret'].rolling(window=ROLLING_WINDOW_SEC).std()

    def run(self):
        mode_str = "BB-Weighted" if self.use_bb_sizing else "Fixed Size"
        print(f"\n--- STRONG UPTREND DETECTION SIMULATOR ({mode_str}) ---")
        print(f"Processing {len(self.df)} datapoints (1-sec resolution)...")
        print(f"Starting Balance: ${self.balance:.2f}\n")
        
        self.df['Window_Start'] = self.df['Open Time'].dt.floor('15min')
        windows = self.df.groupby('Window_Start')
        
        for window_start, group in windows:
            if len(group) < 60: continue 
            
            # Reset Index for 0..900s access
            g = group.reset_index(drop=True)
            
            open_price = g.iloc[0]['Open']
            final_price = g.iloc[-1]['Close']
            
            # State
            window_trade = None
            strategy_triggered = False
            
            # Track checkpoints for continuous scanning
            checkpoints = {} # {second: leader_price}
            
            print(f"--- Window {window_start.strftime('%H:%M')} | Open: {open_price:.2f} ---")
            
            for i, row in g.iterrows():
                elapsed_sec = i
                if elapsed_sec >= 900: break
                
                curr_price = row['Close']
                curr_vol = row['Roll_Std'] if row['Roll_Std'] > 0 else 0.0001
                curr_vol *= 1.55 # Calibrated Multiplier
                
                # Calculate Polymarket prices
                time_left = 900 - elapsed_sec
                up_p, down_p = polymarket_pricing_model(curr_price, open_price, time_left, curr_vol)
                
                # Identify Leader
                leader_side = "UP" if curr_price > open_price else "DOWN"
                leader_price = up_p if leader_side == "UP" else down_p
                
                # --- CONTINUOUS SAMPLING (Every 5s from T+5:00 to T+9:00) ---
                if 300 <= elapsed_sec <= 540:
                    if elapsed_sec % 5 == 0:
                        checkpoints[elapsed_sec] = leader_price
                
                # --- STRONG UPTREND DETECTION (Continuous from T+5 to T+9) ---
                if 300 <= elapsed_sec <= 540 and not strategy_triggered:
                    drift = abs(curr_price - open_price) / open_price
                    
                    # Need at least 3 data points (spanning 60+ seconds) to detect uptrend
                    checkpoint_times = sorted(checkpoints.keys())
                    
                    if len(checkpoint_times) >= 3:
                        # Get recent history (last 60-90 seconds)
                        recent_times = [t for t in checkpoint_times if elapsed_sec - t <= 90]
                        
                        if len(recent_times) >= 3:
                            recent_prices = [checkpoints[t] for t in recent_times]
                            
                            # Calculate momentum: price change over the period
                            price_start = recent_prices[0]
                            price_current = recent_prices[-1]
                            momentum = price_current - price_start
                            
                            # Check for consistency: count consecutive rising samples
                            consecutive_rises = 0
                            max_consecutive = 0
                            for j in range(1, len(recent_prices)):
                                if recent_prices[j] > recent_prices[j-1]:
                                    consecutive_rises += 1
                                    max_consecutive = max(max_consecutive, consecutive_rises)
                                else:
                                    consecutive_rises = 0
                            
                            # Calculate velocity (acceleration): compare recent vs earlier momentum
                            if len(recent_times) >= 6:
                                mid_point = len(recent_times) // 2
                                early_momentum = recent_prices[mid_point] - recent_prices[0]
                                late_momentum = recent_prices[-1] - recent_prices[mid_point]
                                is_accelerating = late_momentum >= early_momentum * 0.8
                            else:
                                is_accelerating = True  # Not enough data, assume neutral
                            
                            # --- UPTREND CRITERIA ---
                            has_strong_momentum = momentum >= 0.10
                            has_consistency = max_consecutive >= 2
                            
                            if (has_strong_momentum and 
                                has_consistency and 
                                is_accelerating and
                                drift > DRIFT_THRESHOLD and 
                                leader_price < 0.85 and 
                                leader_price > 0.10):
                                
                                # STRONG UPTREND DETECTED - Calculate BB-adjusted position size
                                bb_metrics = calculate_bollinger_metrics(checkpoints)
                                
                                # Base cost: 20% of balance
                                base_cost = min(50.0, self.balance * 0.20)
                                
                                # Apply BB multiplier (0.5x at edges, 1.5x at middle) if enabled
                                if self.use_bb_sizing:
                                    cost = base_cost * bb_metrics["size_multiplier"]
                                else:
                                    cost = base_cost  # Fixed sizing
                                cost = max(5.50, cost)  # Enforce minimum
                                
                                if cost <= self.balance:
                                    shares = cost / leader_price
                                    self.balance -= cost
                                    
                                    window_trade = {
                                        "type": "UPTREND",
                                        "side": leader_side,
                                        "entry": leader_price,
                                        "shares": shares,
                                        "cost": cost,
                                        "bb_multiplier": bb_metrics["size_multiplier"] if self.use_bb_sizing else 1.0
                                    }
                                    strategy_triggered = True
                                    
                                    # Record trade details for CSV export
                                    window_trade["window_time"] = window_start.strftime('%Y-%m-%d %H:%M')
                                    window_trade["elapsed_sec"] = elapsed_sec
                                    window_trade["btc_open"] = open_price
                                    window_trade["btc_current"] = curr_price
                                    window_trade["drift"] = drift
                                    window_trade["bb_edge"] = bb_metrics["at_edge"]
                                    window_trade["bb_position"] = bb_metrics["position"]
                                    
                                    print(f"  [T+{elapsed_sec}s UPTREND DETECTED] Momentum: +{momentum:.3f} | Consecutive: {max_consecutive}")
                                    print(f"    -> BUY {leader_side} @ {leader_price:.3f} (Cost: ${cost:.2f})")
                                    if self.use_bb_sizing:
                                        print(f"    -> BB Position: {bb_metrics['position']:.2f} | Multiplier: {bb_metrics['size_multiplier']:.2f}x")
                
                # --- FALLBACK: T+9 (540s) if no uptrend detected ---
                if elapsed_sec == 540 and not strategy_triggered:
                    drift = abs(curr_price - open_price) / open_price
                    
                    # Get BB metrics for T+9 decision
                    bb_metrics = calculate_bollinger_metrics(checkpoints)
                    at_bb_edge = bb_metrics["at_edge"]
                    
                    # Determine price threshold based on Bollinger Band position
                    if at_bb_edge:
                        min_price = 0.55
                        reason_suffix = "at BB edge"
                    else:
                        min_price = 0.80
                        reason_suffix = "not at BB edge"
                    
                    # Apply the conditional logic
                    if (drift > DRIFT_THRESHOLD and 
                        leader_price >= min_price and 
                        leader_price < 0.85 and 
                        leader_price > 0.10):
                        
                        # Base cost: 10% of balance, adjusted by BB multiplier if enabled
                        base_cost = min(50.0, self.balance * 0.10)
                        if self.use_bb_sizing:
                            cost = base_cost * bb_metrics["size_multiplier"]
                        else:
                            cost = base_cost  # Fixed sizing
                        cost = max(5.50, cost)
                        
                        if cost <= self.balance:
                            shares = cost / leader_price
                            self.balance -= cost
                            
                            window_trade = {
                                "type": "FALLBACK-T9",
                                "side": leader_side,
                                "entry": leader_price,
                                "shares": shares,
                                "cost": cost,
                                "bb_multiplier": bb_metrics["size_multiplier"] if self.use_bb_sizing else 1.0
                            }
                            strategy_triggered = True
                            
                            # Record trade details for CSV export
                            window_trade["window_time"] = window_start.strftime('%Y-%m-%d %H:%M')
                            window_trade["elapsed_sec"] = elapsed_sec
                            window_trade["btc_open"] = open_price
                            window_trade["btc_current"] = curr_price
                            window_trade["drift"] = drift
                            window_trade["bb_edge"] = bb_metrics["at_edge"]
                            window_trade["bb_position"] = bb_metrics["position"]
                            
                            print(f"  [T+9 FALLBACK] Entry at {leader_price:.2f} ({reason_suffix})")
                            print(f"    -> BUY {leader_side} @ {leader_price:.3f} (Cost: ${cost:.2f})")
                            if self.use_bb_sizing:
                                print(f"    -> BB Position: {bb_metrics['position']:.2f} | Multiplier: {bb_metrics['size_multiplier']:.2f}x")
                    else:
                        print(f"  [T+9 SKIP] Price {leader_price:.2f} < {min_price:.2f} ({reason_suffix})")

            # --- SETTLEMENT ---
            winner = "UP" if final_price > open_price else "DOWN"
            if window_trade:
                # Add settlement data
                window_trade["btc_final"] = final_price
                window_trade["winner"] = winner
                
                if window_trade["side"] == winner:
                    payout = window_trade["shares"]
                    profit = payout - window_trade["cost"]
                    self.balance += payout
                    self.wins += 1
                    
                    window_trade["outcome"] = "WIN"
                    window_trade["payout"] = payout
                    window_trade["profit"] = profit
                    window_trade["balance_after"] = self.balance
                    
                    print(f"  [WIN] Payout ${payout:.2f} (+${profit:.2f})")
                else:
                    self.losses += 1
                    
                    window_trade["outcome"] = "LOSS"
                    window_trade["payout"] = 0.0
                    window_trade["profit"] = -window_trade["cost"]
                    window_trade["balance_after"] = self.balance
                    
                    print(f"  [LOSS] -${window_trade['cost']:.2f}")
                
                # Add to trades list
                self.trades.append(window_trade)
            else:
                print(f"  [NO TRADE]")
                
            print(f"  Balance: ${self.balance:.2f}\n")

        self.print_report()
        self.export_to_csv()

    def print_report(self):
        total = self.wins + self.losses
        pnl = self.balance - self.start_balance
        pnl_pct = (pnl / self.start_balance) * 100 if self.start_balance > 0 else 0
        
        print("=" * 50)
        print(f"FINAL REPORT")
        print("=" * 50)
        print(f"Starting Balance: ${self.start_balance:.2f}")
        print(f"Final Balance:    ${self.balance:.2f}")
        print(f"P&L:              ${pnl:+.2f} ({pnl_pct:+.1f}%)")
        print(f"Trades:           {total} (Wins: {self.wins} | Losses: {self.losses})")
        if total > 0:
            win_rate = (self.wins / total) * 100
            print(f"Win Rate:         {win_rate:.1f}%")
        print("=" * 50)
    
    def export_to_csv(self):
        """Export all trade data to CSV for detailed analysis"""
        if not self.trades:
            print("\nNo trades to export.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_suffix = "bb" if self.use_bb_sizing else "fixed"
        filename = f"sim_results_{timestamp}_{mode_suffix}.csv"
        
        # Define CSV columns
        fieldnames = [
            "window_time", "elapsed_sec", "trade_type", "side", 
            "btc_open", "btc_current", "btc_final", "drift",
            "entry_price", "cost", "shares", 
            "winner", "outcome", "payout", "profit", "balance_after",
            "bb_edge", "bb_position", "bb_multiplier"
        ]
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for trade in self.trades:
                # Prepare row with all fields (use .get() for optional fields)
                row = {
                    "window_time": trade.get("window_time", ""),
                    "elapsed_sec": trade.get("elapsed_sec", ""),
                    "trade_type": trade.get("type", ""),
                    "side": trade.get("side", ""),
                    "btc_open": f"{trade.get('btc_open', 0):.2f}",
                    "btc_current": f"{trade.get('btc_current', 0):.2f}",
                    "btc_final": f"{trade.get('btc_final', 0):.2f}",
                    "drift": f"{trade.get('drift', 0):.6f}",
                    "entry_price": f"{trade.get('entry', 0):.4f}",
                    "cost": f"{trade.get('cost', 0):.2f}",
                    "shares": f"{trade.get('shares', 0):.4f}",
                    "winner": trade.get("winner", ""),
                    "outcome": trade.get("outcome", ""),
                    "payout": f"{trade.get('payout', 0):.2f}",
                    "profit": f"{trade.get('profit', 0):.2f}",
                    "balance_after": f"{trade.get('balance_after', 0):.2f}",
                    "bb_edge": trade.get("bb_edge", "N/A"),
                    "bb_position": f"{trade.get('bb_position', 0.5):.3f}",
                    "bb_multiplier": f"{trade.get('bb_multiplier', 1.0):.2f}"
                }
                writer.writerow(row)
        
        print(f"\n✅ Trade data exported to: {filename}")
        print(f"   Total trades recorded: {len(self.trades)}")

def main():
    # 1. Scan for CSVs in data/
    files = sorted(glob.glob("data/*.csv") + glob.glob("poly_sim_shell/data/*.csv"))
    if not files:
        print("No CSV files found in data/.")
        return

    print("\n=== STRONG UPTREND DETECTION SIMULATOR ===")
    print("\nSelect Data File:")
    for idx, f in enumerate(files):
        print(f"{idx+1}. {f}")
    
    choice = input("Select [1]: ").strip()
    idx = int(choice) - 1 if choice else 0
    selected_file = files[idx]
    
    bal = input(f"Starting Balance [{DEFAULT_BUDGET}]: ").strip()
    balance = float(bal) if bal else DEFAULT_BUDGET
    
    # Ask about BB-based position sizing
    print("\nPosition Sizing Mode:")
    print("  1. BB-Weighted (0.5x-1.5x based on volatility)")
    print("  2. Fixed Size (1.0x always)")
    bb_choice = input("Select [1]: ").strip()
    use_bb_sizing = (bb_choice != "2")  # Default to BB-weighted
    
    sim = StrongUptrendSimulation(selected_file, balance, use_bb_sizing)
    sim.run()

if __name__ == "__main__":
    main()
