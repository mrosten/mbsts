def analyze_wcp(memory):
  wcp_up_count = 0
  wcp_down_count = 0
  total_up_count = 0
  total_down_count = 0
  
  for window in memory:
    scanners = window.get('scanners_that_fired', [])
    winner = window.get('winner')
    
    if winner == 'UP':
      total_up_count += 1
      if 'WCP' in scanners:
        wcp_up_count += 1
    elif winner == 'DOWN':
      total_down_count += 1
      if 'WCP' in scanners:
        wcp_down_count += 1
  
  print(f"WCP fired and price went UP: {wcp_up_count} times")
  print(f"Total UP windows: {total_up_count}")
  print(f"WCP fired and price went DOWN: {wcp_down_count} times")
  print(f"Total DOWN windows: {total_down_count}")
  
  if total_up_count > 0:
    up_percentage = (wcp_up_count / total_up_count) * 100
    print(f"Percentage of UP windows where WCP fired: {up_percentage:.2f}%\n")
  if total_down_count > 0:
    down_percentage = (wcp_down_count / total_down_count) * 100
    print(f"Percentage of DOWN windows where WCP fired: {down_percentage:.2f}%\n")

analyze_wcp(memory)