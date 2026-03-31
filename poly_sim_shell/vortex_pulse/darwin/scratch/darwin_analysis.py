import json

def analyze_darwin():
    try:
        with open('darwin/experiment_log.json', 'r') as f:
            history = json.load(f)
        
        up_wins = 0
        up_losses = 0
        down_wins = 0
        down_losses = 0

        for item in history:
            mdata = item.get('market_data', {})
            fired = mdata.get('fired_scanners', [])
            trend = mdata.get('trend_1h', 'N/A')
            btc_move = mdata.get('btc_move_pct', 0.0)
            winner = item.get('winner', 'N/A')
            atr = mdata.get('atr_5m', 0.0)
            
            if len(fired) == 1 and 'Darwin' in fired:
                if abs(btc_move) > 0.01:
                    if trend == 'S-UP':
                        if winner == 'UP':
                            up_wins += 1
                        elif winner == 'DOWN':
                            up_losses += 1
                    elif trend == 'S-DOWN':
                        if winner == 'DOWN':
                            down_wins += 1
                        elif winner == 'UP':
                            down_losses += 1

        print(f"Darwin fired alone (abs(BTC Move) > 0.01):\n")
        print(f"S-UP Trend:\n  UP predictions: Wins={up_wins}, Losses={up_losses}\n")
        print(f"S-DOWN Trend:\n  DOWN predictions: Wins={down_wins}, Losses={down_losses}")

    except Exception as e:
        print(f'Runtime Error: {e}')

analyze_darwin()