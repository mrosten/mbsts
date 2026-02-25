import sys
import os
import glob
import csv

def analyze_all_logs(log_dir):
    pattern = os.path.join(log_dir, "sim_log_5M_*.csv")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No files matching 'sim_log_5M_*.csv' found in {log_dir}")
        return

    print(f"Found {len(files)} log files to analyze.\n")

    # Let's collect ALL instances where a side hit >= 0.90
    # Store them as: (time_remaining_seconds, actual_btc_diff_absolute, won_or_lost)
    data_points = []
    
    for f in files:
        parse_file(f, data_points)
        
    print(f"Extracted {len(data_points)} moments where option price reached >= 90c.")
    
    wins = [dp for dp in data_points if dp[2] == 'WIN']
    losses = [dp for dp in data_points if dp[2] == 'LOSS']
    
    print(f"Total Wins: {len(wins)}")
    print(f"Total Losses: {len(losses)}")
    print("-" * 50)
    
    if not losses:
        print("There are no losses to optimize out! Any positive curve works.")
        return
        
    print("ANALYZING LOSSES TO FIND OPTIMAL FLOOR (100% Win Rate):")
    
    # To achieve 100% win rate, our curve must sit ABOVE every single losing trade.
    # Group losses by time segments to suggest a 3-point curve
    
    # Segment 1: e.g. 5 minutes down to 2 minutes
    # Segment 2: e.g. 2 minutes down to 30 seconds
    # Segment 3: e.g. under 30 seconds
    
    l_seg1 = [l for l in losses if l[0] > 120]
    l_seg2 = [l for l in losses if 30 <= l[0] <= 120]
    l_seg3 = [l for l in losses if l[0] < 30]
    
    max_loss_seg1 = max([l[1] for l in l_seg1]) if l_seg1 else 0
    max_loss_seg2 = max([l[1] for l in l_seg2]) if l_seg2 else 0
    max_loss_seg3 = max([l[1] for l in l_seg3]) if l_seg3 else 0
    
    print(f"Segment 1 (> 120s remaining): Worst Fake-Out had BTC Diff of ${max_loss_seg1:.2f}")
    print(f"Segment 2 (30s-120s remaining): Worst Fake-Out had BTC Diff of ${max_loss_seg2:.2f}")
    print(f"Segment 3 (< 30s remaining): Worst Fake-Out had BTC Diff of ${max_loss_seg3:.2f}")
    
    print("\nPROPOSED FOOLPROOF 3-POINT CURVE:")
    print(f"Pt1 (t-290): ${max(max_loss_seg1 + 5, 50):.2f}")
    print(f"Pt2 (t-120): ${max(max_loss_seg2 + 5, 20):.2f}")
    print(f"Pt3 (t-20):  ${max(max_loss_seg3 + 5, 5):.2f}")
    
    # Calculate how many winning trades this strict curve would sacrifice
    surviving_wins = 0
    for w in wins:
        t_rem = w[0]
        diff = w[1]
        
        # Simple floor check based on our tightest segments
        if t_rem > 120 and diff > max_loss_seg1: surviving_wins += 1
        elif 30 <= t_rem <= 120 and diff > max_loss_seg2: surviving_wins += 1
        elif t_rem < 30 and diff > max_loss_seg3: surviving_wins += 1
        
    print(f"\nApplying this foolproof curve would result in: {surviving_wins} Wins, 0 Losses.")
    print(f"(Sacrificed {len(wins) - surviving_wins} wins to guarantee 100% safety)")


def parse_file(filepath, data_points):
    """
    Parses a single sim log.
    Finds every minute where UP/DOWN goes >= 0.90, links it to the round's settlement.
    """
    # Because we check every 15s in the log, we need to associate the trades with the 5M round
    # The end of a 5M round is marked by a SETTLE TRADE_EVENT row.
    
    current_round_hits = [] # Store potential trades in this round
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            for row in reader:
                if not row: continue
                
                if row[0] == "TRADE_EVENT":
                    action = row[2]
                    side = row[3]
                    
                    if action == "SETTLE":
                        # Round ended. The winning side is `side`.
                        for hit in current_round_hits:
                            hit_side = hit['side']
                            won = "WIN" if hit_side == side else "LOSS"
                            data_points.append((hit['trem'], hit['diff'], won))
                            
                        current_round_hits.clear()
                else:
                    # It's a SIM data row
                    time_rem_str = row[5]
                    try:
                        mins, secs = map(int, time_rem_str.split(':'))
                        t_rem = mins * 60 + secs
                    except:
                        continue
                        
                    try:
                        up_price = float(row[20])
                        dn_price = float(row[21])
                        btc_diff = abs(float(row[8]))
                    except: continue
                    
                    if up_price >= 0.90:
                        current_round_hits.append({'side': 'UP', 'trem': t_rem, 'diff': btc_diff})
                    if dn_price >= 0.90:
                        current_round_hits.append({'side': 'DOWN', 'trem': t_rem, 'diff': btc_diff})
                        
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

if __name__ == "__main__":
    analyze_all_logs("logs")
