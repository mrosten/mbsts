import json

def analyze_briefing_scanner(data):
  briefing_wins = 0
  briefing_losses = 0
  total_briefing_firings = 0

  for window in data:
    if 'scanners that fired' in window and 'Briefing' in window['scanners that fired']:
      total_briefing_firings += 1
      if window['BTC Move'] < 0 and window['UP Open'] < window['UP Close']:
        briefing_wins += 1
      elif window['BTC Move'] < 0 and window['UP Open'] > window['UP Close']:
        briefing_losses += 1

  if total_briefing_firings > 0:
    win_rate = briefing_wins / total_briefing_firings
    print(f"Briefing Scanner Win Rate (after negative BTC move and positive Odds):")
    print(f"  Total Firings: {total_briefing_firings}")
    print(f"  Wins: {briefing_wins}")
    print(f"  Losses: {briefing_losses}")
    print(f"  Win Rate: {win_rate:.2f}")
  else:
    print("Briefing scanner hasn't fired after a negative BTC move.")


# Load the last 10 experiments from memory
data = [
    {"Window": "btc-updown-5m-1774040700", "hypothesis": "The combination of high scanner activity (including 'MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT') with a low ATR (0.0) may reliably indicate a consolidation or sideways movement, regardless of the immediate direction of the last move.", "signal": "N/A", "winner": "DOWN", "outcome": "HOLD", "BTC Move": -0.01, "UP Open": 0.50, "UP Close": 0.32, "scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"Window": "btc-updown-5m-1774041000", "hypothesis": "High scanner activity, specifically the consistent firing of 'MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', and 'ADT' coupled with low ATR consistently precedes a DOWN move, irrespective of the Odds Score or previous candle direction. Let's create a scanner 'Darwin' to specifically look for this condition.", "signal": "N/A", "winner": "DOWN", "outcome": "HOLD", "BTC Move": -0.015, "UP Open": 0.50, "UP Close": 0.13, "scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"Window": "btc-updown-5m-1774041300", "hypothesis": "High scanner activity followed by an UP move may indicate a trend continuation.", "signal": "N/A", "winner": "UP", "outcome": "HOLD", "BTC Move": 0.015, "UP Open": 0.50, "UP Close": 0.76, "scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"Window": "btc-updown-5m-1774041900", "hypothesis": "The consistently high scanner activity, including 'MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', and 'ADT', may be a signal for a continuation of the current trend, which is currently UP.", "signal": "N/A", "winner": "UP", "outcome": "HOLD", "BTC Move": 0.018, "UP Open": 0.50, "UP Close": 0.71, "scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"Window": "1774042500", "hypothesis": "The 'Nitro' scanner firing alone, after a positive BTC move, continues to show a weak signal and might indicate a pullback or consolidation.", "signal": "N/A", "winner": "N/A", "outcome": "HOLD", "BTC Move": 0.005, "UP Open": 0.50, "UP Close": 0.47, "scanners that fired": ['Nitro']},
    {"Window": "1774042500", "hypothesis": "The firing of 'Nitro' and 'GrindSnap' after a positive BTC move, coupled with a positive Odds Score, may indicate continued upward pressure. Let's examine if a combination of these scanners with a positive Odds Score reliably predicts an UP move.", "signal": "N/A", "winner": "N/A", "outcome": "HOLD", "BTC Move": 0.005, "UP Open": 0.50, "UP Close": 0.47, "scanners that fired": ['Nitro', 'GrindSnap']},
    {"Window": "btc-updown-5m-1774042500", "hypothesis": "The consistent firing of 'MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT' suggests a potential reversal regardless of the 1H trend. Let's analyze the historical performance of this specific scanner combination and see if a reversal is more probable.", "signal": "N/A", "winner": "UP", "outcome": "HOLD", "BTC Move": 0.005, "UP Open": 0.50, "UP Close": 0.47, "scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"Window": "btc-updown-5m-1774042800", "hypothesis": "The 'Darwin' scanner successfully identified a pattern of high scanner activity leading to a DOWN move. Let's refine the 'Darwin' scanner by incorporating the ATR value to see if that improves its accuracy.", "signal": "N/A", "winner": "DOWN", "outcome": "HOLD", "BTC Move": -0.009, "UP Open": 0.50, "UP Close": 0.31, "scanners that fired": []},
    {"Window": "1774043100", "hypothesis": "The 'Nitro' and 'VolSnap' scanners firing together with a positive BTC move and a high positive Odds Score (+96.0¢) suggests a continuation of the UP trend, similar to window 1774040100.", "signal": "N/A", "winner": "N/A", "outcome": "HOLD", "BTC Move": 0.016, "UP Open": 0.50, "UP Close": 0.98, "scanners that fired": ['Nitro', 'VolSnap']},
    {"Window": "btc-updown-5m-1774043100", "hypothesis": "High scanner activity continues to indicate potential trend continuations. The combination of 'MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', and 'ADT' along with the Darwin scanner may be a strong indicator of trend continuation.", "signal": "N/A", "winner": "UP", "outcome": "HOLD", "BTC Move": 0.016, "UP Open": 0.50, "UP Close": 0.98, "scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']}
]

analyze_briefing_scanner(data)
