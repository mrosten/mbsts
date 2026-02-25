import sys
import csv

def analyze_trades(csv_file):
    print(f"Analyzing trades in: {csv_file}\n")
    
    trades = {}
    wins = []
    losses = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            for row in reader:
                if not row: continue
                
                # Check if it's a TRADE_EVENT line
                if row[0] == "TRADE_EVENT":
                    # Format: TRADE_EVENT, Time, Action, Side, Amount, Price, ...
                    time = row[1]
                    action = row[2]
                    side = row[3]
                    
                    if action == "BUY":
                        price = float(row[5])
                        algo_info = row[13] if len(row) > 13 else "Unknown"
                        
                        if "MOSHE" in algo_info:
                            # We found a Moshe buy, record it temporarily
                            trades[time] = {
                                'time': time,
                                'side': side,
                                'buy_price': price,
                                'algo': algo_info
                            }
                    
                    elif action == "SETTLE":
                        # A round settled, check if any of our open trades won or lost
                        settle_side = side
                        
                        for buy_time, trade_data in list(trades.items()):
                            # If the round settled on the side we bought, we won
                            if trade_data['side'] == settle_side:
                                trade_data['result'] = 'WIN'
                                wins.append(trade_data)
                            else:
                                trade_data['result'] = 'LOSS'
                                losses.append(trade_data)
                                
                        # Clear open trades after settlement
                        trades.clear()
                        
    except FileNotFoundError:
        print(f"Error: File '{csv_file}' not found.")
        return
        
    print(f"Total Moshe Trades: {len(wins) + len(losses)}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)}\n")
    
    if len(losses) > 0:
        print("-" * 50)
        print("LOSING TRADE ANALYSIS:")
        print("-" * 50)
        for loss in losses:
            print(f"Time: {loss['time']}")
            print(f"Direction: {loss['side']}")
            print(f"Execution Price: ${loss['buy_price']:.2f}")
            print(f"Signal: {loss['algo']}")
            print("-" * 30)
            # Now we hunt through the CSV again just to get the exact BTC metrics at the time of that buy
            # We look for the most recent SIM row right BEFORE or ON the trade time
            best_sim_row = None
            with open(csv_file, 'r', encoding='utf-8') as f:
                log_reader = csv.reader(f)
                header = next(log_reader, None)
                for log_row in log_reader:
                    if not log_row: continue
                    
                    if log_row[0] != "TRADE_EVENT":
                        # It's a SIM row. Check if it's before or exactly on our trade time
                        if log_row[0] <= loss['time']:
                            best_sim_row = log_row
                        else:
                            # We've passed the trade time, break out
                            break
                            
            if best_sim_row:
                time_rem = best_sim_row[5]
                btc_diff = best_sim_row[8]
                print(f"  -> Time Remaining: {time_rem}")
                print(f"  -> BTC Difference: ${btc_diff}")
            else:
                print("  -> Could not find matching SIM row for BTC metrics.")
            print("-" * 30)
    else:
        print("No losing Moshe trades found in this log.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_moshe.py <path_to_csv>")
    else:
        analyze_trades(sys.argv[1])
