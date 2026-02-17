"""
Sophisticated analysis of Polymarket sim trading log.
Parses all trades, categorizes by strategy type, and identifies patterns.
"""
import re
import json
from collections import defaultdict
from datetime import datetime

LOG_FILE = r"c:\MyStuff\coding\turbindo-master\poly_sim_shell\data\sim_live_v2_log_20260201_223855.txt"

def parse_log(filepath):
    trades = []
    current_trade = None
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            
            # Match entry lines
            # "Entered UPTREND (DOWN) @ 0.810 | Cost: $5.50"
            # "Entered HIGH-CONF (UP) @ 0.880 | Cost: $5.50"
            # "Entered FALLBACK-T9 (DOWN) @ 0.810 | Cost: $5.50"
            entry_match = re.search(
                r'\[(\d{2}:\d{2}:\d{2})\] Entered (\S+) \((\w+)\) @ ([\d.]+) \| Cost: \$([\d.]+)',
                line
            )
            if entry_match:
                time_str, strategy, direction, entry_price, cost = entry_match.groups()
                current_trade = {
                    'entry_time': time_str,
                    'strategy': strategy,
                    'direction': direction,
                    'entry_price': float(entry_price),
                    'cost': float(cost),
                    'momentum': None,
                    'consecutive': None,
                }
                continue
            
            # Match momentum details on UPTREND entries
            mom_match = re.search(r'Momentum: ([+-][\d.]+) \| Consecutive: (\d+)', line)
            if mom_match and current_trade:
                current_trade['momentum'] = float(mom_match.group(1))
                current_trade['consecutive'] = int(mom_match.group(2))
                continue
            
            # Match WIN/LOSS lines
            win_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\] WIN: \+\$([\d.]+) \| Bal: \$([\d.]+)', line)
            loss_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\] LOSS: -\$([\d.]+) \| Bal: \$([\d.]+)', line)
            
            if win_match and current_trade:
                current_trade['result'] = 'WIN'
                current_trade['pnl'] = float(win_match.group(2))
                current_trade['balance_after'] = float(win_match.group(3))
                current_trade['exit_time'] = win_match.group(1)
                trades.append(current_trade)
                current_trade = None
            elif loss_match and current_trade:
                current_trade['result'] = 'LOSS'
                current_trade['pnl'] = -float(loss_match.group(2))
                current_trade['balance_after'] = float(loss_match.group(3))
                current_trade['exit_time'] = loss_match.group(1)
                trades.append(current_trade)
                current_trade = None
    
    return trades

def time_to_hour(t_str):
    """Convert HH:MM:SS to float hour"""
    parts = t_str.split(':')
    return int(parts[0]) + int(parts[1])/60

def analyze(trades):
    print("=" * 70)
    print("POLYMARKET SIMULATED TRADING ANALYSIS")
    print(f"Total Trades: {len(trades)}")
    print("=" * 70)
    
    # --- OVERALL ---
    total_pnl = sum(t['pnl'] for t in trades)
    wins = [t for t in trades if t['result'] == 'WIN']
    losses = [t for t in trades if t['result'] == 'LOSS']
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    total_cost = sum(t['cost'] for t in trades)
    
    print(f"\n--- OVERALL PERFORMANCE ---")
    print(f"Total P&L:        ${total_pnl:+.2f}")
    print(f"Win Rate:         {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Avg Win:          ${avg_win:.2f}")
    print(f"Avg Loss:         ${avg_loss:.2f}")
    print(f"Total Wagered:    ${total_cost:.2f}")
    print(f"ROI:              {total_pnl/total_cost*100:.1f}%" if total_cost else "N/A")
    print(f"Profit Factor:    {sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses)):.2f}" if losses else "inf")
    
    # --- BY STRATEGY ---
    strategies = defaultdict(list)
    for t in trades:
        strategies[t['strategy']].append(t)
    
    print(f"\n--- PERFORMANCE BY STRATEGY ---")
    print(f"{'Strategy':<16} {'Trades':>6} {'WinRate':>8} {'AvgWin':>8} {'AvgLoss':>9} {'TotalPnL':>10} {'BigLoss':>9}")
    print("-" * 70)
    
    for strat in sorted(strategies.keys()):
        ts = strategies[strat]
        w = [t for t in ts if t['result'] == 'WIN']
        l = [t for t in ts if t['result'] == 'LOSS']
        wr = len(w)/len(ts)*100
        aw = sum(t['pnl'] for t in w)/len(w) if w else 0
        al = sum(t['pnl'] for t in l)/len(l) if l else 0
        tp = sum(t['pnl'] for t in ts)
        bl = min(t['pnl'] for t in ts)
        print(f"{strat:<16} {len(ts):>6} {wr:>7.1f}% ${aw:>6.2f} ${al:>8.2f} ${tp:>9.2f} ${bl:>8.2f}")
    
    # --- BY DIRECTION ---
    print(f"\n--- PERFORMANCE BY DIRECTION ---")
    for direction in ['UP', 'DOWN']:
        ts = [t for t in trades if t['direction'] == direction]
        if not ts:
            continue
        w = [t for t in ts if t['result'] == 'WIN']
        l = [t for t in ts if t['result'] == 'LOSS']
        wr = len(w)/len(ts)*100
        tp = sum(t['pnl'] for t in ts)
        print(f"  {direction}: {len(ts)} trades, {wr:.1f}% win rate, P&L: ${tp:+.2f}")
    
    # --- ENTRY PRICE ANALYSIS ---
    print(f"\n--- ENTRY PRICE ANALYSIS ---")
    price_buckets = {
        'Very Low (0.50-0.65)': (0.50, 0.65),
        'Low (0.65-0.75)': (0.65, 0.75),
        'Medium (0.75-0.85)': (0.75, 0.85),
        'High (0.85-0.92)': (0.85, 0.92),
        'Very High (0.92-1.00)': (0.92, 1.00),
    }
    print(f"{'Price Range':<25} {'Trades':>7} {'WinRate':>8} {'TotalPnL':>10} {'AvgPnL':>9}")
    print("-" * 65)
    for label, (lo, hi) in price_buckets.items():
        ts = [t for t in trades if lo <= t['entry_price'] < hi]
        if not ts:
            continue
        w = [t for t in ts if t['result'] == 'WIN']
        wr = len(w)/len(ts)*100
        tp = sum(t['pnl'] for t in ts)
        ap = tp / len(ts)
        print(f"{label:<25} {len(ts):>7} {wr:>7.1f}% ${tp:>9.2f} ${ap:>8.2f}")
    
    # --- COST / POSITION SIZE ANALYSIS ---
    print(f"\n--- POSITION SIZE ANALYSIS ---")
    # The script uses increasing cost over time
    cost_buckets = {
        '$5-6':  (5, 6.01),
        '$6-8':  (6.01, 8.01),
        '$8-12': (8.01, 12.01),
        '$12-20': (12.01, 20.01),
        '$20+':  (20.01, 9999),
    }
    print(f"{'Cost Range':<15} {'Trades':>7} {'WinRate':>8} {'TotalPnL':>10} {'AvgPnL':>9}")
    print("-" * 55)
    for label, (lo, hi) in cost_buckets.items():
        ts = [t for t in trades if lo <= t['cost'] < hi]
        if not ts:
            continue
        w = [t for t in ts if t['result'] == 'WIN']
        wr = len(w)/len(ts)*100
        tp = sum(t['pnl'] for t in ts)
        ap = tp / len(ts)
        print(f"{label:<15} {len(ts):>7} {wr:>7.1f}% ${tp:>9.2f} ${ap:>8.2f}")
    
    # --- MOMENTUM ANALYSIS (UPTREND only) ---
    print(f"\n--- MOMENTUM ANALYSIS (UPTREND strategy only) ---")
    uptrend_trades = [t for t in trades if t['strategy'] == 'UPTREND' and t['momentum'] is not None]
    if uptrend_trades:
        mom_buckets = {
            'Low (0.10-0.14)': (0.10, 0.15),
            'Med (0.15-0.20)': (0.15, 0.20),
            'High (0.20-0.30)': (0.20, 0.30),
            'VHigh (0.30+)': (0.30, 9.0),
        }
        print(f"{'Momentum':<20} {'Trades':>7} {'WinRate':>8} {'TotalPnL':>10}")
        print("-" * 50)
        for label, (lo, hi) in mom_buckets.items():
            ts = [t for t in uptrend_trades if lo <= t['momentum'] < hi]
            if not ts:
                continue
            w = [t for t in ts if t['result'] == 'WIN']
            wr = len(w)/len(ts)*100
            tp = sum(t['pnl'] for t in ts)
            print(f"{label:<20} {len(ts):>7} {wr:>7.1f}% ${tp:>9.2f}")
        
        # Consecutive ups analysis
        print(f"\n  Consecutive Ups:")
        cons_groups = defaultdict(list)
        for t in uptrend_trades:
            if t['consecutive'] is not None:
                cons_groups[t['consecutive']].append(t)
        for c in sorted(cons_groups.keys()):
            ts = cons_groups[c]
            w = [t for t in ts if t['result'] == 'WIN']
            wr = len(w)/len(ts)*100
            tp = sum(t['pnl'] for t in ts)
            print(f"    {c} consecutive: {len(ts)} trades, {wr:.1f}% win, P&L: ${tp:+.2f}")
    
    # --- TOP 10 BIGGEST WINS ---
    print(f"\n--- TOP 10 BIGGEST WINS ---")
    sorted_wins = sorted(wins, key=lambda t: t['pnl'], reverse=True)[:10]
    for i, t in enumerate(sorted_wins, 1):
        print(f"  {i}. +${t['pnl']:.2f} | {t['strategy']} {t['direction']} @ {t['entry_price']} | Cost: ${t['cost']:.2f} | {t['entry_time']}")
    
    # --- TOP 10 BIGGEST LOSSES ---
    print(f"\n--- TOP 10 BIGGEST LOSSES ---")
    sorted_losses = sorted(losses, key=lambda t: t['pnl'])[:10]
    for i, t in enumerate(sorted_losses, 1):
        mom_str = f" Mom:{t['momentum']}" if t['momentum'] else ""
        print(f"  {i}. ${t['pnl']:.2f} | {t['strategy']} {t['direction']} @ {t['entry_price']} | Cost: ${t['cost']:.2f} | {t['entry_time']}{mom_str}")
    
    # --- STREAKS ---
    print(f"\n--- WIN/LOSS STREAKS ---")
    max_win_streak = 0
    max_loss_streak = 0
    current_streak = 0
    current_type = None
    for t in trades:
        if t['result'] == current_type:
            current_streak += 1
        else:
            current_type = t['result']
            current_streak = 1
        if current_type == 'WIN':
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, current_streak)
    print(f"  Max Win Streak:  {max_win_streak}")
    print(f"  Max Loss Streak: {max_loss_streak}")
    
    # --- BALANCE CURVE ---
    print(f"\n--- BALANCE TRAJECTORY ---")
    if trades:
        balances = [t['balance_after'] for t in trades]
        print(f"  Start:   ${trades[0]['balance_after'] - trades[0]['pnl']:.2f}")
        print(f"  Peak:    ${max(balances):.2f} (trade #{balances.index(max(balances))+1})")
        print(f"  Trough:  ${min(balances):.2f} (trade #{balances.index(min(balances))+1})")
        print(f"  Final:   ${balances[-1]:.2f}")
        
        # Max drawdown
        peak = balances[0]
        max_dd = 0
        max_dd_from = 0
        for i, b in enumerate(balances):
            if b > peak:
                peak = b
            dd = peak - b
            if dd > max_dd:
                max_dd = dd
                max_dd_from = peak
        print(f"  Max Drawdown: ${max_dd:.2f} (from ${max_dd_from:.2f})")
    
    # --- TIME-OF-DAY ANALYSIS ---
    print(f"\n--- TIME-OF-DAY ANALYSIS (UTC) ---")
    hour_groups = defaultdict(list)
    for t in trades:
        h = int(t['entry_time'].split(':')[0])
        hour_groups[h].append(t)
    
    print(f"{'Hour':>5} {'Trades':>7} {'WinRate':>8} {'TotalPnL':>10} {'AvgPnL':>9}")
    print("-" * 45)
    for h in sorted(hour_groups.keys()):
        ts = hour_groups[h]
        w = [t for t in ts if t['result'] == 'WIN']
        wr = len(w)/len(ts)*100
        tp = sum(t['pnl'] for t in ts)
        ap = tp/len(ts)
        flag = " <<<" if tp < -5 else (" ***" if tp > 5 else "")
        print(f"{h:>5} {len(ts):>7} {wr:>7.1f}% ${tp:>9.2f} ${ap:>8.2f}{flag}")
    
    # --- KEY INSIGHTS ---
    print(f"\n{'='*70}")
    print("KEY INSIGHTS & LESSONS")
    print(f"{'='*70}")
    
    # 1. Which strategy loses most
    worst_strat = min(strategies.items(), key=lambda x: sum(t['pnl'] for t in x[1]))
    best_strat = max(strategies.items(), key=lambda x: sum(t['pnl'] for t in x[1]))
    print(f"\n1. BEST STRATEGY: {best_strat[0]}")
    print(f"   P&L: ${sum(t['pnl'] for t in best_strat[1]):+.2f} over {len(best_strat[1])} trades")
    print(f"\n2. WORST STRATEGY: {worst_strat[0]}")
    print(f"   P&L: ${sum(t['pnl'] for t in worst_strat[1]):+.2f} over {len(worst_strat[1])} trades")
    
    # 2. High-conf loss pattern
    hc_losses = [t for t in trades if t['strategy'] == 'HIGH-CONF' and t['result'] == 'LOSS']
    if hc_losses:
        print(f"\n3. HIGH-CONF LOSSES ({len(hc_losses)} total):")
        for t in hc_losses[:5]:
            print(f"   {t['direction']} @ {t['entry_price']} | Cost: ${t['cost']:.2f} | Loss: ${t['pnl']:.2f} | Time: {t['entry_time']}")
    
    # 3. Increasing cost danger
    big_losses = [t for t in losses if t['cost'] > 8]
    if big_losses:
        print(f"\n4. LARGE BET LOSSES ({len(big_losses)} trades with cost > $8):")
        tot_big_loss = sum(t['pnl'] for t in big_losses)
        print(f"   Total lost: ${tot_big_loss:.2f}")
        print(f"   These trades account for {abs(tot_big_loss)/abs(sum(t['pnl'] for t in losses))*100:.1f}% of all losses")
    
    # 4. Reversal detection
    uptrend_losses = [t for t in trades if t['strategy'] == 'UPTREND' and t['result'] == 'LOSS']
    if uptrend_losses:
        print(f"\n5. UPTREND REVERSAL LOSSES ({len(uptrend_losses)}):")
        avg_entry = sum(t['entry_price'] for t in uptrend_losses) / len(uptrend_losses)
        avg_mom = sum(t['momentum'] for t in uptrend_losses if t['momentum']) / len([t for t in uptrend_losses if t['momentum']])
        print(f"   Avg entry price: {avg_entry:.3f}")
        print(f"   Avg momentum at entry: {avg_mom:+.3f}")
        print(f"   These are 'fake breakouts' - price surged but reversed before window close")
    
    # Summary recommendation
    print(f"\n{'='*70}")
    print("ACTIONABLE RECOMMENDATIONS")
    print(f"{'='*70}")
    
    # Check if HIGH-CONF at very high prices loses
    hc_very_high = [t for t in trades if t['strategy'] == 'HIGH-CONF' and t['entry_price'] >= 0.93]
    if hc_very_high:
        w = [t for t in hc_very_high if t['result'] == 'WIN']
        l = [t for t in hc_very_high if t['result'] == 'LOSS']
        wr = len(w)/len(hc_very_high)*100
        print(f"\n  a) HIGH-CONF entries >= 0.93:")
        print(f"     {len(hc_very_high)} trades, {wr:.0f}% win rate, P&L: ${sum(t['pnl'] for t in hc_very_high):+.2f}")
        if wr < 70:
            print(f"     >> AVOID entries at 0.93+ (too expensive, small upside, big downside)")
    
    # Check low entry UPTREND
    ut_low = [t for t in trades if t['strategy'] == 'UPTREND' and t['entry_price'] <= 0.72]
    if ut_low:
        w = [t for t in ut_low if t['result'] == 'WIN']
        wr = len(w)/len(ut_low)*100
        tp = sum(t['pnl'] for t in ut_low)
        print(f"\n  b) UPTREND entries <= 0.72 (low price, high upside):")
        print(f"     {len(ut_low)} trades, {wr:.0f}% win rate, P&L: ${tp:+.2f}")
    
    # Martingale / growing cost danger
    costs = [t['cost'] for t in trades]
    if max(costs) > 15:
        print(f"\n  c) POSITION SIZING WARNING:")
        print(f"     Max cost reached ${max(costs):.2f}. Growing position sizes")
        print(f"     amplify losses. Consider FIXED sizing ($5-6 per trade).")
    
    # Time-based
    worst_hours = sorted(hour_groups.items(), key=lambda x: sum(t['pnl'] for t in x[1]))[:3]
    print(f"\n  d) WORST TRADING HOURS (UTC): {', '.join(str(h)+':00' for h,_ in worst_hours)}")
    for h, ts in worst_hours:
        tp = sum(t['pnl'] for t in ts)
        print(f"     {h:02d}:00 -> P&L: ${tp:+.2f}")

    return trades

def main():
    print("Parsing log file...")
    trades = parse_log(LOG_FILE)
    print(f"Found {len(trades)} completed trades.\n")
    analyze(trades)

if __name__ == "__main__":
    main()
