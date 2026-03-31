def analyze_data(data):
  up_count = 0
  down_count = 0
  total_windows = 0

  for window in data:
    total_windows += 1
    if window['Winner'] == 'UP':
      up_count += 1
    else:
      down_count += 1

  print(f"Total UP windows: {up_count}")
  print(f"Total DOWN windows: {down_count}")
  print(f"Total windows analyzed: {total_windows}")

  # Placeholder: Expand to analyze scanner activity in relation to price movement
  print("Analysis of scanner activity to be implemented...")

data = [
    {'Window ID': 'btc-updown-5m-1774038000', 'Winner': 'DOWN', 'BTC Move': '-0.001%', 'ATR': 0.0, '1H Trend': 'M-DOWN', 'Odds Score': '-10.0¢', 'UP Open': '6993192.0¢', 'Close': '6993192.0¢', 'Next Window Tilt': 'None', 'Scanners that fired': ['MM2', 'GrindSnap', 'Nitro'], 'PnL this window': '-3.23'},
    {'Window ID': 'btc-updown-5m-1774038300', 'Winner': 'DOWN', 'BTC Move': '-0.001%', 'ATR': 0.0, '1H Trend': 'M-DOWN', 'Odds Score': '-10.0¢', 'UP Open': '6993192.0¢', 'Close': '6993192.0¢', 'Next Window Tilt': 'None', 'Scanners that fired': ['MM2'], 'PnL this window': '-3.23'},
    {'Window ID': 'btc-updown-5m-1774038600', 'Winner': 'DOWN', 'BTC Move': '-0.001%', 'ATR': 0.0, '1H Trend': 'M-DOWN', 'Odds Score': '-10.0¢', 'UP Open': '6993192.0¢', 'Close': '6993192.0¢', 'Next Window Tilt': 'None', 'Scanners that fired': ['MM2', 'GrindSnap', 'Nitro'], 'PnL this window': '-3.23'},
    {'Window ID': 'btc-updown-5m-1774038900', 'Winner': 'UP', 'BTC Move': '+0.001%', 'ATR': 0.0, '1H Trend': 'M-DOWN', 'Odds Score': '+33.0¢', 'UP Open': '6993192.0¢', 'Close': '7002650.0¢', 'Next Window Tilt': 'None', 'Scanners that fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap'], 'PnL this window': '+3.23'},
    {'Window ID': 'btc-updown-5m-1774039200', 'Winner': 'UP', 'BTC Move': '+0.001%', 'ATR': 0.0, '1H Trend': 'M-DOWN', 'Odds Score': '+33.0¢', 'UP Open': '6993192.0¢', 'Close': '7002650.0¢', 'Next Window Tilt': 'None', 'Scanners that fired': ['Nitro'], 'PnL this window': '+3.23'},
    {'Window ID': 'btc-updown-5m-1774039500', 'Winner': 'UP', 'BTC Move': '+0.001%', 'ATR': 0.0, '1H Trend': 'M-DOWN', 'Odds Score': '+33.0¢', 'UP Open': '6993192.0¢', 'Close': '7002650.0¢', 'Next Window Tilt': 'None', 'Scanners that fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT', 'Darwin'], 'PnL this window': '+3.23'}

]

analyze_data(data)
