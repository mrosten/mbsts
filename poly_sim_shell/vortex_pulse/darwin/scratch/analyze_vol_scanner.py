import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    up_successes = 0
    up_attempts = 0
    down_successes = 0
    down_attempts = 0

    for item in history:
        mdata = item.get('market_data', {})
        scanners = mdata.get('fired_scanners', [])
        odds_score = mdata.get('odds_score', 0.0)
        trend_1h = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'VOL' in scanners and abs(odds_score) < 20:
            winner = item.get('winner', 'N/A')

            if odds_score > 0:
                up_attempts += 1
                if winner == 'UP':
                    up_successes += 1
            else:
                down_attempts += 1
                if winner == 'DOWN':
                    down_successes += 1

    print(f"VOL scanner (abs(odds_score) < 20) performance:\n")
    if up_attempts > 0:
        up_accuracy = (up_successes / up_attempts) * 100
        print(f"UP predictions: {up_accuracy:.2f}% ({up_successes}/{up_attempts})")
    else:
        print("No UP predictions found.")

    if down_attempts > 0:
        down_accuracy = (down_successes / down_attempts) * 100
        print(f"DOWN predictions: {down_accuracy:.2f}% ({down_successes}/{down_attempts})")
    else:
        print("No DOWN predictions found.")

except Exception as e:
    print(f'Runtime Error: {e}')