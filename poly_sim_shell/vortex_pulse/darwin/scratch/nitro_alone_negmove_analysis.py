import json

def analyze_nitro_alone(data):
    nitro_alone_instances = []
    for window in data:
        if 'scanners_that_fired' in window and len(window['scanners_that_fired']) == 1 and window['scanners_that_fired'][0] == 'Nitro':
            nitro_alone_instances.append(window)

    nitro_alone_negmove = []
    for window in nitro_alone_instances:
        if window['btc_move'] < 0:
            nitro_alone_negmove.append(window)
    
    num_instances = len(nitro_alone_negmove)
    if num_instances == 0:
        return {"count": 0, "up_pct": 0, "down_pct": 0}

    up_count = 0
    down_count = 0
    for window in nitro_alone_negmove:
        if window['winner'] == 'UP':
            up_count += 1
        elif window['winner'] == 'DOWN':
            down_count += 1

    up_percentage = (up_count / num_instances) * 100 if num_instances > 0 else 0
    down_percentage = (down_count / num_instances) * 100 if num_instances > 0 else 0

    return {"count": num_instances, "up_pct": up_percentage, "down_pct": down_percentage}


# Load historical data (replace with actual data loading mechanism)
data = [
    {"window_id": 1774046400, "scanners_that_fired": ['Nitro'], "btc_move": -0.081, "winner": 'DOWN'},
    {"window_id": 1774046100, "scanners_that_fired": ['Nitro','MM2'], "btc_move": 0.02, "winner": 'UP'},
    {"window_id": 1774045800, "scanners_that_fired": ['Nitro'], "btc_move": -0.01, "winner": 'DOWN'},
    {"window_id": 1774045500, "scanners_that_fired": ['Nitro','VolSnap'], "btc_move": 0.05, "winner": 'UP'}
]

analysis_result = analyze_nitro_alone(data)
print(json.dumps(analysis_result))
