import json

def analyze_data(data):
    last_10 = data['memory']
    current_scanners = set(data['current_window']['Scanners that fired'])
    
    up_after_up_with_scanners = 0
    total_up_with_scanners = 0
    
    relevant_windows = []
    for i in range(len(last_10) - 1, -1, -2): #only look at result windows
      if 'Winner' in last_10[i].keys():
        relevant_windows.append(last_10[i])
        if len(relevant_windows) >= 5:
          break
    
    for i in range(len(relevant_windows)):
      window = relevant_windows[i]
      prev_scanners = window['Scanners that fired']
      prev_result = window['Winner']

      if prev_result == "UP":
          total_up_with_scanners += 1
          if i > 0:
            prev_window = relevant_windows[i-1]
            if prev_window['Winner'] == 'UP':
              up_after_up_with_scanners+=1
    
    if total_up_with_scanners > 0:
      prob = up_after_up_with_scanners / total_up_with_scanners
    else:
      prob = 0.5
    
    print(f"Probability of UP after UP with these scanners: {prob}")

# Dummy data mimicking the environment - replace with actual data when running
data = {
    'memory': [
        {'hypothesis': '...', 'winner': 'UP', 'Scanners that fired': ['A', 'B']}, # Dummy UP win
        {'hypothesis': '...', 'winner': 'DOWN', 'Scanners that fired': ['C']}, # Dummy DOWN win
        {'hypothesis': '...', 'winner': 'UP', 'Scanners that fired': ['A', 'B', 'C']}, # Dummy UP win
        {'hypothesis': '...', 'winner': 'DOWN', 'Scanners that fired': ['B']}, # Dummy DOWN win
        {'hypothesis': '...', 'winner': 'UP', 'Scanners that fired': ['A']},  # Dummy UP win
        {'hypothesis': '...', 'winner': 'DOWN', 'Scanners that fired': ['C']}, # Dummy DOWN win
        {'hypothesis': '...', 'winner': 'UP', 'Scanners that fired': ['A', 'B', 'C']}, # Dummy UP win
        {'hypothesis': '...', 'winner': 'DOWN', 'Scanners that fired': ['B']}, # Dummy DOWN win
        {'hypothesis': '...', 'winner': 'UP', 'Scanners that fired': ['A']},  # Dummy UP win
        {'hypothesis': '...', 'winner': 'DOWN', 'Scanners that fired': ['C']}
    ],
    'current_window': {
        'Scanners that fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT', 'Darwin']
    }
}

analyze_data(data)
