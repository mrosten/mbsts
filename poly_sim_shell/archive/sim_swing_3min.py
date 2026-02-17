"""
Simulator: Swing Strategy (3-Min Data)

A coarser version of the Swing Strategy simulator.
- Estimations are less precise than the 1-sec sim.
- Used for quick validation on 3-minute datasets.
"""
import os
import glob
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- Constants ---
TRADE_SIZE = 5.50
DRIFT_THRESHOLD = 0.0004
SPREAD = 0.02

# --- Pricing Model ---
def polymarket_pricing_model(current_price, strike_price, time_remaining_seconds, volatility_per_second):
    """
    Estimate UP/DOWN prices using normal distribution model
    """
    # Calculate divergence (Percentage)
    div_pct = (current_price - strike_price) / strike_price

    # Calculate volatility over remaining time
    # Standard deviation scales with sqrt(time)
    volatility_remaining = volatility_per_second * np.sqrt(time_remaining_seconds)

    # Avoid division by zero
    if volatility_remaining == 0 or time_remaining_seconds == 0:
        # At expiry or zero volatility, outcome is certain
        up_price = 0.01 if div_pct < 0 else 0.99
        down_price = 1.0 - up_price
        return up_price, down_price

    # Calculate z-score (how many standard deviations from strike)
    z_score = div_pct / volatility_remaining

    # Calculate probability using cumulative normal distribution
    # prob_up = norm.cdf(z_score) -> Using math.erf to avoid scipy dependency
    prob_up = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
    prob_down = 1 - prob_up

    # Add market spread/edge (Polymarket takes a cut)
    # Adjust probabilities slightly to ensure they don't sum to exactly 1.0
    spread = SPREAD
    up_price = max(0.001, min(0.999, prob_up * (1 - spread)))
    down_price = max(0.001, min(0.999, prob_down * (1 - spread)))

    return up_price, down_price

# --- Simulation Logic ---
class LocalSimulation:
    def __init__(self, csv_file, balance):
        self.df = pd.read_csv(csv_file)
        self.df['Open Time'] = pd.to_datetime(self.df['Open Time'])
        self.balance = float(balance)
        self.trades = []
        self.wins = 0
        self.losses = 0

    def run(self):
        print(f"\nLoading data from {len(self.df)} candles...")
        
        # Calculate Volatility (Standard Deviation of log returns over last 30 candles)
        self.df['Log_Ret'] = np.log(self.df['Close'] / self.df['Close'].shift(1))
        # 3-minute vol -> 1-second vol? 
        # Vol per 3min = std(log_ret). 
        # Vol per sec = Vol per 3min / sqrt(180) ?
        # Let's use a rolling window for dynamic volatility
        self.df['Vol_3m'] = self.df['Log_Ret'].rolling(window=20).std()
        self.df['Vol_Sec'] = self.df['Vol_3m'] / np.sqrt(180)
        self.df['Vol_Sec'] = self.df['Vol_Sec'].fillna(0.0005) # Fallback

        # Group into 15m windows (5 candles per window)
        # Assuming data starts at a clean 15m interval (00, 15, 30, 45)
        # We can iterate by index in steps of 5
        
        for i in range(0, len(self.df), 5):
            window = self.df.iloc[i:i+5]
            if len(window) < 5: break # Skip incomplete last window

            c0 = window.iloc[0] # T+0 to T+3
            c1 = window.iloc[1] # T+3 to T+6 (Checkpoint A)
            c2 = window.iloc[2] # T+6 to T+9 (Checkpoint B)
            c3 = window.iloc[3] # T+9 to T+12
            c4 = window.iloc[4] # T+12 to T+15 (Close)

            # Metadata
            start_time = c0['Open Time']
            strike_price = c0['Open'] # Fixed Open Price
            final_price = c4['Close'] # Final Settlement Price
            
            # Volatility for this window (use start of window vol)
            vol_sec = c0['Vol_Sec']
            if vol_sec == 0: vol_sec = 0.0001

            print(f"--- Window: {start_time.strftime('%H:%M')} | Open: {strike_price:.2f} ---")
            
            active_trade = None
            
            # --- Checkpoint A (T+6) ---
            # Time is end of c1 (6 minutes elapsed)
            # Remaining time = 9 minutes = 540 seconds
            curr_price_t6 = c1['Close']
            drift_t6 = abs(curr_price_t6 - strike_price) / strike_price
            
            if drift_t6 > DRIFT_THRESHOLD:
                side = "UP" if curr_price_t6 > strike_price else "DOWN"
                
                # Estimate Price
                up_p, down_p = polymarket_pricing_model(curr_price_t6, strike_price, 540, vol_sec)
                entry_price = up_p if side == "UP" else down_p
                
                # Execute
                # Dynamic Sizing: Scale from 5% to 33% of balance based on certainty (Price 0.5 -> 1.0)
                # Base 5% + Scaling Component
                # If Price 0.5: 0.05 + 0 = 5%
                # If Price 1.0: 0.05 + (0.5 * 0.56) = 0.05 + 0.28 = 33%
                wager_pct = 0.05 + max(0, (entry_price - 0.5)) * 0.56
                wager_pct = min(0.33, wager_pct) # Cap at 33%
                
                cost = self.balance * wager_pct
                shares = cost / entry_price
                
                self.balance -= cost
                active_trade = {"side": side, "entry": entry_price, "shares": shares, "cost": cost, "time": "T+6"}
                # Debug Calc
                # z = abs((curr_price_t6 - strike_price)/strike_price) / (vol_sec * np.sqrt(540))
                print(f"  [T+6] DRIFT {drift_t6:.4%} > {DRIFT_THRESHOLD}. BUY {side} @ {entry_price:.3f} (Vol/s: {vol_sec:.2e})")
                print(f"        -> Certainty {entry_price:.1%}: Wager {wager_pct:.1%} of Bal (${cost:.2f})")

            # --- Checkpoint B (T+9) ---
            if not active_trade:
                # Time is end of c2 (9 minutes elapsed)
                # Remaining time = 6 minutes = 360 seconds
                curr_price_t9 = c2['Close']
                drift_t9 = abs(curr_price_t9 - strike_price) / strike_price
                
                if drift_t9 > DRIFT_THRESHOLD:
                    side = "UP" if curr_price_t9 > strike_price else "DOWN"
                    
                    # Estimate Price
                    up_p, down_p = polymarket_pricing_model(curr_price_t9, strike_price, 360, vol_sec)
                    entry_price = up_p if side == "UP" else down_p
                    
                     # Execute
                    # Dynamic Sizing
                    wager_pct = 0.05 + max(0, (entry_price - 0.5)) * 0.56
                    wager_pct = min(0.33, wager_pct)
                    
                    cost = self.balance * wager_pct
                    shares = cost / entry_price
                    
                    self.balance -= cost
                    active_trade = {"side": side, "entry": entry_price, "shares": shares, "cost": cost, "time": "T+9"}
                    print(f"  [T+9] DRIFT {drift_t9:.4%} > {DRIFT_THRESHOLD}. BUY {side} @ {entry_price:.3f}")
                    print(f"        -> Certainty {entry_price:.1%}: Wager {wager_pct:.1%} of Bal (${cost:.2f})")

            # --- Settlement ---
            winner = "UP" if final_price > strike_price else "DOWN"
            payout = 0.0
            
            if active_trade:
                if active_trade["side"] == winner:
                    payout = active_trade["shares"] * 1.00 # $1 per share
                    self.balance += payout
                    profit = payout - active_trade["cost"]
                    self.wins += 1
                    print(f"  [RES] WON ({winner}). Payout: ${payout:.2f} (Profit: ${profit:.2f})")
                else:
                    self.losses += 1
                    print(f"  [RES] LOST ({active_trade['side']} vs {winner}). Loss: -${active_trade['cost']:.2f}")
            else:
                print(f"  [RES] NO TRADE. Result: {winner}")

            print(f"  Balance: ${self.balance:.2f}\n")
            
        # Final Report
        total = self.wins + self.losses
        wr = (self.wins / total * 100) if total > 0 else 0
        print("========================================")
        print(f"FINAL REPORT")
        print(f"End Balance: ${self.balance:.2f}")
        print(f"Trades: {total} (Wins: {self.wins} | Losses: {self.losses})")
        print(f"Win Rate: {wr:.1f}%")
        print("========================================")

# --- Main Entry ---
def main():
    # 1. Scan for CSVs (Current Dir or Subdir)
    files = sorted(glob.glob("data/*.csv") + glob.glob("poly_sim_shell/data/*.csv"))
    if not files:
        print("No CSV files found in poly_sim_shell/")
        return

    print("Available Data Files:")
    for idx, f in enumerate(files[:5]):
        print(f"{idx+1}. {f}")
    
    choice = input("Select File [1]: ")
    file_idx = int(choice) - 1 if choice.strip() else 0
    
    if 0 <= file_idx < len(files):
        selected_file = files[file_idx]
        
        bal = input("Starting Balance [50]: ")
        balance = float(bal) if bal.strip() else 50.0
        
        sim = LocalSimulation(selected_file, balance)
        sim.run()
    else:
        print("Invalid selection.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
