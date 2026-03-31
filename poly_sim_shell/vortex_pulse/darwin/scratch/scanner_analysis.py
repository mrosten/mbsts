def analyze_scanners(window_data):
    scanners = window_data['scanners_that_fired']
    odds_score = window_data['Odds Score']
    btc_move = window_data['BTC Move']

    nitro_fired = 'Nitro' in scanners
    grindsnap_fired = 'GrindSnap' in scanners
    positive_odds = float(odds_score[:-1]) > 0  # Remove '¢' and convert to float

    if nitro_fired and grindsnap_fired and positive_odds:
        print("Nitro and GrindSnap fired with positive Odds Score.")
    else:
        print("Conditions not met.")

window_data = {
    'scanners_that_fired': ['Nitro', 'GrindSnap'],
    'Odds Score': '+47.0¢',
    'BTC Move': '+0.003%'
}

analyze_scanners(window_data)