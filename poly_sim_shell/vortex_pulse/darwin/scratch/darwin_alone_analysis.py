import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)
    
down_darwin_up_wins = 0
    down_darwin_up_losses = 0
    down_darwin_down_wins = 0
    down_darwin_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        btc_move = mdata.get('btc_move_pct', 0.0)
        outcome = item.get('winner', 'N/A')
        
        if 'Darwin' in fired and len(fired) == 1 and btc_move < 0:
            if outcome == 'UP':
                down_darwin_up_wins += 1
            elif outcome == 'DOWN':
                down_darwin_up_losses += 1
        
        if 'Darwin' in fired and len(fired) == 1 and btc_move > 0:
            if outcome == 'DOWN':
                down_darwin_down_wins += 1
            elif outcome == 'UP':
                down_darwin_down_losses += 1

    print(f"Darwin fired alone (After DOWN move): Wins={down_darwin_up_wins}, Losses={down_darwin_up_losses}")
    print(f"Darwin fired alone (After UP move): Wins={down_darwin_down_wins}, Losses={down_darwin_down_losses}")

except FileNotFoundError:
    print("Error: The file 'darwin/experiment_log.json' was not found.")
except Exception as e:
    print(f"Runtime Error: {e}")