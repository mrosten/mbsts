import json

def analyze_data(data):
    nitro_volsnap_consec_down = 0
    nitro_volsnap_consec_up = 0
    total_nitro_volsnap_consec = 0

    for i in range(1, len(data)):  # Start from the second window
        prev_window = data[i-1]
        curr_window = data[i]

        prev_scanners = prev_window.get('scanners_that_fired', [])
        curr_scanners = curr_window.get('scanners_that_fired', [])
        
        if 'Nitro' in prev_scanners and 'VolSnap' in prev_scanners and 'Nitro' in curr_scanners and 'VolSnap' in curr_scanners:
            total_nitro_volsnap_consec += 1
            if curr_window['btc_move'] < 0:
                nitro_volsnap_consec_down += 1
            else:
                nitro_volsnap_consec_up += 1
    
    if total_nitro_volsnap_consec > 0:
        down_percentage = (nitro_volsnap_consec_down / total_nitro_volsnap_consec) * 100
        up_percentage = (nitro_volsnap_consec_up / total_nitro_volsnap_consec) * 100
        print(f"Consecutive Nitro & VolSnap (Total: {total_nitro_volsnap_consec}): Down={down_percentage:.2f}%, Up={up_percentage:.2f}%"
    else:
        print("No consecutive Nitro & VolSnap firings found.")


# Simulate loading your memory data (replace with actual data loading)
memory_data = [
  {"window_id": "btc-updown-5m-1774032900", "scanners_that_fired": ["ADT", "WCP", "SSC"], "btc_move": -0.05},  
  {"window_id": "1774033200", "scanners_that_fired": ["Nitro", "VolSnap"], "btc_move": 0.02},
  {"window_id": "btc-updown-5m-1774033500", "scanners_that_fired": ["ADT", "WCP", "SSC"], "btc_move": -0.03}, 
  {"window_id": "1774033800", "scanners_that_fired": ["WCP", "Nitro", "VolSnap"], "btc_move": 0.01},
  {"window_id": "btc-updown-5m-1774033800", "scanners_that_fired": ["ADT", "WCP", "SSC"], "btc_move": 0.04},
  {"window_id": "1774034100", "scanners_that_fired": ["Briefing"], "btc_move": 0.03},
  {"window_id": "btc-updown-5m-1774034100", "scanners_that_fired": ["VolSnap", "Nitro", "GrindSnap"], "btc_move": 0.05},
  {"window_id": "1774034400", "scanners_that_fired": ["VolSnap"], "btc_move": -0.02},
  {"window_id": "btc-updown-5m-1774034400", "scanners_that_fired": ["MM2", "GrindSnap", "Nitro", "VolSnap", "Briefing", "WCP", "SSC", "ADT"], "btc_move": 0.01},
  {"window_id": "1774034700", "scanners_that_fired": ["VolSnap"], "btc_move": 0.03},
  {"window_id": "1774035000", "scanners_that_fired": ["Nitro", "VolSnap"], "btc_move": -0.11}
]


analyze_data(memory_data)
