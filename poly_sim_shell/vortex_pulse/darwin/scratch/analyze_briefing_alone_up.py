import json

def analyze_data(filename='memory.json'):
  try:
    with open(filename, 'r') as f:
      data = json.load(f)
  except FileNotFoundError:
    print(f"Error: Could not find {filename}")
    return
  except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from {filename}")
    return

  briefing_alone_up_count = 0
  briefing_alone_up_success = 0

  for window_id, window_data in data.items():
    if 'scanners_that_fired' in window_data and 'btc_move' in window_data and 'winner' in window_data:
      scanners = window_data['scanners_that_fired']
      btc_move = window_data['btc_move']
      winner = window_data['winner']

      if len(scanners) == 1 and 'BRI' in scanners:
        if btc_move > 0:
          briefing_alone_up_count += 1
          if winner == 'DOWN':
            briefing_alone_up_success += 1

  if briefing_alone_up_count > 0:
    success_rate = (briefing_alone_up_success / briefing_alone_up_count) * 100
    print(f"'Briefing' scanner alone after positive BTC move fired {briefing_alone_up_count} times.")
    print(f"Success rate (predicting DOWN): {success_rate:.2f}%")
  else:
    print("'Briefing' scanner alone after positive BTC move did not fire in the analyzed data.")

analyze_data()