data = memory[-10:]

adt_wcp_ssc_after_up_down_count = 0
adt_wcp_ssc_after_up_total_count = 0

for i in range(len(data) - 1):
    current_window = data[i]
    next_window = data[i+1]

    if isinstance(current_window, str): # Skip if it is a window ID string
        continue

    if isinstance(next_window, str): # Skip if it is a window ID string
        continue

    current_scanners = current_window.get('scanners_that_fired', [])

    if 'ADT' in current_scanners and 'WCP' in current_scanners and 'SSC' in current_scanners:
        if current_window.get('winner') == 'UP':
            adt_wcp_ssc_after_up_total_count += 1
            if next_window.get('winner') == 'DOWN':
                adt_wcp_ssc_after_up_down_count += 1

if adt_wcp_ssc_after_up_total_count > 0:
    adt_wcp_ssc_after_up_down_rate = adt_wcp_ssc_after_up_down_count / adt_wcp_ssc_after_up_total_count
    print(f"Rate DOWN after UP and ADT, WCP, SSC: {adt_wcp_ssc_after_up_down_rate:.2f} ({adt_wcp_ssc_after_up_down_count}/{adt_wcp_ssc_after_up_total_count})")
else:
    print("Not enough data for ADT, WCP, SSC after UP analysis.")
