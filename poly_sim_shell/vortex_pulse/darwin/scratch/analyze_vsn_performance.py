import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)
    
    vsn_up_wins = 0
    vsn_up_losses = 0
    vsn_down_wins = 0
    vsn_down_losses = 0
    
    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        outcome = item.get('outcome', 'N/A')
        
        if 'VSN' in fired and len(fired) == 1:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                if outcome == 'UP':
                    vsn_up_wins += 1
                elif outcome == 'DOWN':
                    vsn_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                if outcome == 'UP':
                    vsn_down_wins += 1
                elif outcome == 'DOWN':
                    vsn_down_losses += 1
    
    print(f"VSN alone UP predictions: Wins={vsn_up_wins}, Losses={vsn_up_losses}")
    print(f"VSN alone DOWN predictions: Wins={vsn_down_wins}, Losses={vsn_down_losses}")
    
except Exception as e:
    print(f'Runtime Error: {e}')