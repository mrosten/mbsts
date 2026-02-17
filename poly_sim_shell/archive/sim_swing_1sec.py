"""
Simulator: Swing Strategy (1-Sec Data)

The backtesting engine for the 1-second "Swing Hunter" strategy.
- Loads 1s CSV data from data/.
- Simulates 15m Polymarket windows.
- Metrics: Win Rate, ROI, Efficiency Ratio.
- Includes T+9 Trend logic (optional/commented) and Hedge logic.
"""
import os
import glob
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- Configuration ---
DEFAULT_BUDGET = 50.0
MAX_BET_AMOUNT = 100.0           # Cap max bet to $100 for realism (Liquidity)
DRIFT_THRESHOLD = 0.0015         # 0.15% (Trigger Momentum)
REVERSION_THRESHOLD = 0.0035     # 0.35% (Trigger Reversion)
SWING_VOL_PERCENTILE = 0.80      # Top 20%
EFFICIENCY_THRESHOLD = 0.35      # Efficiency < 0.35
SPREAD = 0.02
ROLLING_WINDOW_SEC = 60          # Lookback for volatility/efficiency

# --- Pricing Model ---
def polymarket_pricing_model(current_price, strike_price, time_remaining_seconds, volatility_per_second):
    """
    Estimate UP/DOWN prices using normal distribution model
    """
    if time_remaining_seconds <= 0:
        return (0.99, 0.01) if current_price > strike_price else (0.01, 0.99)

    # Calculate divergence (Percentage)
    div_pct = (current_price - strike_price) / strike_price

    # Calculate volatility over remaining time
    volatility_remaining = volatility_per_second * np.sqrt(time_remaining_seconds)

    # Avoid division by zero
    if volatility_remaining == 0:
        up_price = 0.99 if div_pct > 0 else 0.01
        return up_price, 1.0 - up_price

    # Calculate z-score
    z_score = div_pct / volatility_remaining

    # Calculate probability using error function (cumulative normal distribution)
    prob_up = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
    prob_down = 1 - prob_up

    # Add market spread
    up_price = max(0.001, min(0.999, prob_up * (1 - SPREAD)))
    down_price = max(0.001, min(0.999, prob_down * (1 - SPREAD)))

    return up_price, down_price

# --- Simulation Logic ---
class Local1SecSimulation:
    def __init__(self, csv_file, balance):
        self.df = pd.read_csv(csv_file)
        self.df['Open Time'] = pd.to_datetime(self.df['Open Time'])
        self.balance = float(balance)
        self.start_balance = float(balance)
        
        self.trades = []
        self.wins = 0
        self.losses = 0
        
        # Pre-calc global volatility stats for "High Volatility" threshold
        # We need log returns of the 1-second closes
        self.df['Log_Ret'] = np.log(self.df['Close'] / self.df['Close'].shift(1))
        self.df['Roll_Std'] = self.df['Log_Ret'].rolling(window=ROLLING_WINDOW_SEC).std()
        
        # Calculate Volatility Threshold (e.g., 80th percentile of rolling std)
        self.vol_threshold = self.df['Roll_Std'].quantile(SWING_VOL_PERCENTILE)
        print(f"Global Volatility Threshold (Top {100*(1-SWING_VOL_PERCENTILE):.0f}%): {self.vol_threshold:.2e}")

    def calculate_efficiency(self, prices):
        """
        Efficiency Ratio = Net Change / Sum of Absolute Changes
        """
        if len(prices) < 2: return 1.0
        
        net_change = abs(prices[-1] - prices[0])
        total_path = np.sum(np.abs(np.diff(prices)))
        
        if total_path == 0: return 1.0
        return net_change / total_path

    def run(self):
        print(f"\nProcessing {len(self.df)} datapoints...")
        
        # Identify 15m Windows
        # We assume data is sorted. We'll group by 15 minute frequency.
        # Floor timestamps to 15m
        self.df['Window_Start'] = self.df['Open Time'].dt.floor('15min')
        windows = self.df.groupby('Window_Start')
        
        for window_start, group in windows:
            if len(group) < 60: continue # Skip partial/tiny windows
            
            # --- Window Setup ---
            # Re-index to be 0..N
            g = group.reset_index(drop=True)
            
            open_price = g.iloc[0]['Open'] # Fixed Strike Price for this window
            final_price = g.iloc[-1]['Close'] # Settlement Price
            final_time = g.iloc[-1]['Open Time']
            
            # Local State for this Window
            window_trades = []
            has_swing_trade = False
            has_t9_trade = False
            window_vol_buffer = [] # Store recent prices for efficiency calc
            
            print(f"--- Window {window_start.strftime('%H:%M')} | Open: {open_price:.2f} ---")
            
            # --- Linear Playback (Second by Second) ---
            for i, row in g.iterrows():
                # Current Status
                elapsed_sec = i # Since we reset index, i is roughly seconds elapsed (assuming 1s data)
                if elapsed_sec >= 900: break # Stop at 15m mark
                
                curr_price = row['Close']
                curr_time = row['Open Time']
                
                # Update Buffer
                window_vol_buffer.append(curr_price)
                if len(window_vol_buffer) > ROLLING_WINDOW_SEC:
                    window_vol_buffer.pop(0)
                
                # Skip first minute to build buffer
                if i < ROLLING_WINDOW_SEC: continue
                if elapsed_sec > 850: continue # Too close to close
                
                # --- T+9 Trend Confirmation Strategy ---
                # At 9 minutes (540s), if price is > $0.80, Buy $5.50 Flat
                # We check this INDEPENDENTLY of Swing Trades
                # if elapsed_sec >= 540 and not has_t9_trade:
                #     # Calculate Prices first
                #     time_left_t9 = 900 - elapsed_sec
                #     vol_t9 = row['Roll_Std'] if row['Roll_Std'] > 0 else 0.0001
                #     up_t9, down_t9 = polymarket_pricing_model(curr_price, open_price, time_left_t9, vol_t9)
                #     
                #     t9_side = None
                #     t9_price = 0.0
                #     
                #     if up_t9 > 0.80:
                #         t9_side = "UP"
                #         t9_price = up_t9
                #     elif down_t9 > 0.80:
                #         t9_side = "DOWN"
                #         t9_price = down_t9
                #         
                #     if t9_side:
                #         # MEANINGFUL FILTER: Don't buy if price is basically 99 cents (no upside)
                #         if t9_price < 0.98:
                #             # Execute T+9 Trade
                #             cost = 5.50 # Flat $5.50
                #             shares = cost / t9_price
                #             self.balance -= cost
                #             
                #             trade = {
                #                 "type": "T+9",
                #                 "side": t9_side,
                #                 "entry": t9_price,
                #                 "shares": shares,
                #                 "cost": cost,
                #                 "time": curr_time.strftime('%H:%M:%S'),
                #                 "btc_entry": curr_price,
                #                 "reason": "T+9 Trend (>0.80)"
                #             }
                #             window_trades.append(trade)
                #             has_t9_trade = True
                #             
                #             print(f"  [{curr_time.strftime('%H:%M:%S')}] SIGNAL TRIGGERED (T+9)")
                #             print(f"    -> BTC: {curr_price:.2f}")
                #             print(f"    -> ACTION: BUY {t9_side} @ ${t9_price:.3f}")
                #             print(f"    -> Wager: ${cost:.2f} (Flat) for {shares:.2f} shares")

                # --- Swing Strategy ---
                if not has_swing_trade:
                    # 1. Check Drift
                    drift = (curr_price - open_price) / open_price
                    abs_drift = abs(drift)
                    
                    if abs_drift > DRIFT_THRESHOLD:
                        # 2. Check Swing Zone (Volatility + Efficiency)
                        
                        # Volatility (from pre-calc)
                        curr_vol = row['Roll_Std']
                        
                        # Efficiency
                        eff = self.calculate_efficiency(window_vol_buffer)
                        
                        # Condition: High Activity AND Low Efficiency (Chop/Swing)
                        if curr_vol > self.vol_threshold and eff < EFFICIENCY_THRESHOLD:
                            # SIGNAL!
                            
                            # Determine Direction (Hybrid Momentum / Extreme Reversion)
                            side = "UP"
                            strategy_type = "MOMENTUM"
                            
                            if abs_drift > REVERSION_THRESHOLD:
                                # EXTREME REVERSION (Fade the loser)
                                side = "DOWN" if drift > 0 else "UP"
                                strategy_type = "REVERSION"
                            else:
                                # MOMENTUM (Follow the winner)
                                side = "UP" if drift > 0 else "DOWN"

                            # Pricing
                            time_left = 900 - elapsed_sec
                            vol_per_sec = curr_vol if curr_vol > 0 else 0.0001
                            
                            up_p, down_p = polymarket_pricing_model(curr_price, open_price, time_left, vol_per_sec)
                            entry_price = up_p if side == "UP" else down_p
                            
                            # Filter bad prices
                            if 0.05 < entry_price < 0.95:
                                # Symmetric Dynamic Sizing (Aggressive)
                                dist = abs(entry_price - 0.5)
                                wager_pct = 0.15 + (dist * 1.20) # Scale up to ~75%
                                wager_pct = min(0.75, wager_pct)
                                cost = self.balance * wager_pct
                                cost = min(cost, MAX_BET_AMOUNT) # Liquidity Cap
                                shares = cost / entry_price
                                self.balance -= cost
                                
                                trade = {
                                    "type": "SWING",
                                    "side": side,
                                    "entry": entry_price,
                                    "shares": shares,
                                    "cost": cost,
                                    "time": curr_time.strftime('%H:%M:%S'),
                                    "btc_entry": curr_price,
                                    "reason": f"Vol:{curr_vol:.2e} Eff:{eff:.2f}"
                                }
                                window_trades.append(trade)
                                has_swing_trade = True
                                
                                print(f"  [{curr_time.strftime('%H:%M:%S')}] SIGNAL TRIGGERED ({strategy_type})")
                                print(f"    -> BTC: {curr_price:.2f} (Drift: {drift:.4%})")
                                print(f"    -> ACTION: BUY {side} @ ${entry_price:.3f}")
                                print(f"    -> Wager: ${cost:.2f} ({wager_pct:.1%}) for {shares:.2f} shares")
                                
                                # --- SPECIAL HEDGE LOGIC ---
                                # If entry price is very high (> 0.90), the opposite side is very cheap (< 0.10).
                                # We wager a small amount ($2.00) on the opposite outcome as insurance/lotto.
                                if entry_price > 0.90:
                                    hedge_side = "DOWN" if side == "UP" else "UP"
                                    hedge_price = down_p if side == "UP" else up_p
                                    
                                    # Double check it's cheap
                                    if hedge_price < 0.15:
                                        hedge_cost = 2.00
                                        hedge_shares = hedge_cost / hedge_price
                                        self.balance -= hedge_cost
                                        
                                        hedge_trade = {
                                            "type": "HEDGE",
                                            "side": hedge_side,
                                            "entry": hedge_price,
                                            "shares": hedge_shares,
                                            "cost": hedge_cost,
                                            "time": curr_time.strftime('%H:%M:%S'),
                                            "btc_entry": curr_price,
                                            "reason": f"Hedge against {side} (>0.90)"
                                        }
                                        window_trades.append(hedge_trade)
                                        print(f"    -> [HEDGE] Buying {hedge_side} @ ${hedge_price:.3f} (Cost: $2.00)")

            # --- Settlement at End of Window ---
            winner = "UP" if final_price > open_price else "DOWN"
            
            if window_trades:
                print(f"  [WINDOW CLOSE {window_start.strftime('%H:%M')} -> {final_price:.2f}] Winner: {winner}")
                
                for trade in window_trades:
                    opt_exit = 1.00 if trade["side"] == winner else 0.00
                    payout = 0.0
                    
                    if trade["side"] == winner:
                        payout = trade["shares"] * 1.00
                        profit = payout - trade["cost"]
                        self.balance += payout
                        self.wins += 1
                        print(f"    -> [{trade['type']}] WIN! Profit: +${profit:.2f} (ROI: {profit/trade['cost']*100:.1f}%)")
                    else:
                        self.losses += 1
                        print(f"    -> [{trade['type']}] LOSS. Loss: -${trade['cost']:.2f}")
            else:
                pass 
            
            print(f"  Bal: ${self.balance:.2f}\n")

        # --- Final Report ---
        self.print_final_report()

    def print_final_report(self):
        print("\n========================================")
        print("          FINAL SIMULATION REPORT       ")
        print("========================================")
        total_pnl = self.balance - self.start_balance
        total_trades = self.wins + self.losses
        win_rate = (self.wins / total_trades * 100) if total_trades > 0 else 0.0
        
        print(f"Start Balance:   ${self.start_balance:.2f}")
        print(f"Final Balance:   ${self.balance:.2f}")
        print(f"Net Profit/Loss: ${total_pnl:.2f} ({total_pnl/self.start_balance*100:+.1f}%)")
        print(f"----------------------------------------")
        print(f"Total Trades:    {total_trades}")
        print(f"Wins:            {self.wins}")
        print(f"Losses:          {self.losses}")
        print(f"Win Rate:        {win_rate:.1f}%")
        print("========================================")

# --- Main Entry ---
def main():
    # 1. Scan for CSVs
    files = sorted(glob.glob("data/*.csv") + glob.glob("poly_sim_shell/data/*.csv"))
    if not files:
        print("No CSV files found.")
        return

    print("\nSelect Data File:")
    for idx, f in enumerate(files):
        print(f"{idx+1}. {f}")
    
    try:
        choice = input("Select [1]: ").strip()
        idx = int(choice) - 1 if choice else 0
        selected_file = files[idx]
        
        bal_input = input(f"Starting Budget [{DEFAULT_BUDGET}]: ").strip()
        balance = float(bal_input) if bal_input else DEFAULT_BUDGET
        
        sim = Local1SecSimulation(selected_file, balance)
        sim.run()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
