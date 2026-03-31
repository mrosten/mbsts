import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    vsn_nitro_up_wins = 0
    vsn_nitro_up_losses = 0
    vsn_nitro_down_wins = 0
    vsn_nitro_down_losses = 0

    vsn_alone_up_wins = 0
    vsn_alone_up_losses = 0
    vsn_alone_down_wins = 0
    vsn_alone_down_losses = 0

    nitro_alone_up_wins = 0
    nitro_alone_up_losses = 0
    nitro_alone_down_wins = 0
    nitro_alone_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        winner = item.get('winner', 'N/A')

        if 'VSN' in fired_scanners and 'NIT' in fired_scanners and len(fired_scanners) == 2:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                if winner == 'UP':
                    vsn_nitro_up_wins += 1
                elif winner == 'DOWN':
                    vsn_nitro_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                if winner == 'DOWN':
                    vsn_nitro_down_wins += 1
                elif winner == 'UP':
                    vsn_nitro_down_losses += 1

        elif 'VSN' in fired_scanners and len(fired_scanners) == 1:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                if winner == 'UP':
                    vsn_alone_up_wins += 1
                elif winner == 'DOWN':
                    vsn_alone_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                if winner == 'DOWN':
                    vsn_alone_down_wins += 1
                elif winner == 'UP':
                    vsn_alone_down_losses += 1

        elif 'NIT' in fired_scanners and len(fired_scanners) == 1:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                if winner == 'UP':
                    nitro_alone_up_wins += 1
                elif winner == 'DOWN':
                    nitro_alone_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                if winner == 'DOWN':
                    nitro_alone_down_wins += 1
                elif winner == 'UP':
                    nitro_alone_down_losses += 1

    print(f'VSN and Nitro together, trend down:\nUP predictions: Wins={vsn_nitro_up_wins}, Losses={vsn_nitro_up_losses}\n')
    print(f'VSN and Nitro together, trend up:\nDOWN predictions: Wins={vsn_nitro_down_wins}, Losses={vsn_nitro_down_losses}\n')

    print(f'VSN alone, trend down:\nUP predictions: Wins={vsn_alone_up_wins}, Losses={vsn_alone_up_losses}\n')
    print(f'VSN alone, trend up:\nDOWN predictions: Wins={vsn_alone_down_wins}, Losses={vsn_alone_down_losses}\n')

    print(f'Nitro alone, trend down:\nUP predictions: Wins={nitro_alone_up_wins}, Losses={nitro_alone_up_losses}\n')
    print(f'Nitro alone, trend up:\nDOWN predictions: Wins={nitro_alone_down_wins}, Losses={nitro_alone_down_losses}\n')

except Exception as e:
    print(f'Runtime Error: {e}')