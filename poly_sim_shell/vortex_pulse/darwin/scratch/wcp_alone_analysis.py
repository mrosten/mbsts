import json

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
        odds_score = mdata.get('odds_score', 0.0)

        if len(fired) == 1 and 'WCP' in fired:
            if trend == 'S-UP' and btc_move > 0 and odds_score > 50:
                if item.get('winner') == 'UP':
                    up_wins += 1
                else:
                    up_losses += 1
            elif trend == 'S-DOWN' and btc_move < 0 and odds_score < -50:
                if item.get('winner') == 'DOWN':
                    down_wins += 1
                else:
                    down_losses += 1

    print(f'WCP fired alone (BTC UP, S-UP Trend, Odds > 50):\n  UP predictions: Wins={up_wins}, Losses={up_losses}')
    print(f'WCP fired alone (BTC DOWN, S-DOWN Trend, Odds < -50):\n  DOWN predictions: Wins={down_wins}, Losses={down_losses}')

except Exception as e:
    print(f'Runtime Error: {e}')