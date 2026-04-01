
import os
import re

# Configuration
SOURCE_DIR = r"C:\MyStuff\coding\turbindo-master\poly_sim_shell\vortex_pulse\lg\graphs"
OUTPUT_DIR = r"C:\MyStuff\coding\turbindo-master\poly_sim_shell\vortex_pulse\ptp_tests"

PROMINENCE = 4.0 
T_MID = 170.0    
MIN_SLOPE = 0.02 

def parse_polyline_points(svg_path):
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'<polyline points="([^"]+)"', content)
        if not match: return []
        points_str = match.group(1)
        coords = []
        for pair in points_str.split():
            x, y = map(float, pair.split(','))
            coords.append({'x': x, 'y': y})
        return coords
    except Exception as e:
        print(f"Error parsing {svg_path}: {e}")
        return []

def run_ptp_logic(points):
    valid_peaks = []
    last_max_y = 1e10 
    last_min_y = -1e10 
    seeking_state = "trough"
    
    eval_points = [p for p in points if p['x'] <= T_MID]
    if not eval_points: return [], 0.0, False
    
    for p in eval_points:
        curr_y = p['y']
        if seeking_state == "peak":
            if curr_y < last_max_y:
                last_max_y = curr_y
            elif curr_y > last_max_y + PROMINENCE:
                peak_time = p['x']
                new_peak = {'x': peak_time, 'y': last_max_y}
                if not valid_peaks:
                    valid_peaks.append(new_peak)
                elif new_peak['y'] < valid_peaks[-1]['y']: 
                    valid_peaks.append(new_peak)
                seeking_state = "trough"
                last_min_y = curr_y
        else: 
            if curr_y > last_min_y:
                last_min_y = curr_y
            elif curr_y < last_min_y - PROMINENCE:
                seeking_state = "peak"
                last_max_y = curr_y

    if len(valid_peaks) < 2:
        return valid_peaks, 0.0, False
    p1 = valid_peaks[0]
    pn = valid_peaks[-1]
    delta_y_virtual = p1['y'] - pn['y'] 
    delta_x = pn['x'] - p1['x']
    if delta_x <= 0: return valid_peaks, 0.0, False
    slope = delta_y_virtual / delta_x
    triggered = slope >= MIN_SLOPE
    return valid_peaks, slope, triggered

def annotate_svg(svg_path, output_path, peaks, points, slope, triggered, correlation_text):
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        insert_idx = -1
        for i, line in enumerate(reversed(lines)):
            if '</svg>' in line:
                insert_idx = len(lines) - 1 - i
                break
        if insert_idx == -1: return
        
        # Determine background color based on price diff
        bg_color = "#121212"
        if len(points) >= 2:
            price_diff = abs(points[-1]['y'] - points[0]['y']) # Y-units are price-scaled in this mock
            if price_diff >= 100: bg_color = "#831843"   # Tier 4
            elif price_diff >= 50: bg_color = "#312e81"  # Tier 3
            elif price_diff >= 25: bg_color = "#4c1d95"  # Tier 2
            elif price_diff >= 1: bg_color = "#1e293b"   # Tier 1

        # Update the background rect
        for i, line in enumerate(lines):
            if '<rect width="340" height="190"' in line:
                lines[i] = line.replace('fill="#121212"', f'fill="{bg_color}"')
                break

        new_elements = []
        for i, p in enumerate(peaks):
            new_elements.append(f' <circle cx="{p["x"]}" cy="{p["y"]}" r="2" fill="#ff00ff" stroke="white" stroke-width="0.5" />\n')
            new_elements.append(f' <text x="{p["x"]+2}" y="{p["y"]-2}" font-size="6" fill="#ff00ff">P{i+1}</text>\n')
        if len(peaks) >= 2:
            p1 = peaks[0]; pn = peaks[-1]
            color = "#00ff00" if triggered else "#ffaa00"
            new_elements.append(f' <line x1="{p1["x"]}" y1="{p1["y"]}" x2="{pn["x"]}" y2="{pn["y"]}" stroke="{color}" stroke-width="1.5" stroke-dasharray="3,2" />\n')
        
        new_elements.append(f' <text x="10" y="180" font-family="monospace" font-size="9" fill="cyan" font-weight="bold">{correlation_text}</text>\n')

        lines = lines[:insert_idx] + new_elements + lines[insert_idx:]
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"Error annotating {svg_path}: {e}")

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    svg_files = [f for f in os.listdir(SOURCE_DIR) if f.endswith('.svg')]
    svg_files.sort()
    
    # Process batch 10 to 40 (30 more files) for better statistical data
    batch = svg_files[10:40]
    print(f"Running PTP Rising Peak Experiment on {len(batch)} SVG graphs...")
    
    stats = {"rising_total": 0, "rising_correct": 0, "non_rising_total": 0, "non_rising_up": 0}
    
    for filename in batch:
        src = os.path.join(SOURCE_DIR, filename)
        dst = os.path.join(OUTPUT_DIR, filename)
        points = parse_polyline_points(src)
        if len(points) < 2: continue
        
        peaks, slope, triggered = run_ptp_logic(points)
        
        # Analyze Rising Trend Correlation
        is_rising = False
        if len(peaks) >= 2:
            is_rising = peaks[1]['y'] < peaks[0]['y'] # P2 price > P1 price
            
        start_y = points[0]['y']
        end_y = points[-1]['y']
        actual_up = end_y < start_y # Price at end > Start
        
        if is_rising:
            stats["rising_total"] += 1
            if actual_up: stats["rising_correct"] += 1
        else:
            stats["non_rising_total"] += 1
            if actual_up: stats["non_rising_up"] += 1
            
        corr_text = f"Pattern: {'RISING' if is_rising else 'NONE'} | Result: {'UP' if actual_up else 'DOWN'}"
        annotate_svg(src, dst, peaks, points, slope, triggered, corr_text)
        print(f"  Processed {filename}: {corr_text}")

    print("\n--- EXPERIMENT SUMMARY ---")
    rising_acc = (stats["rising_correct"] / stats["rising_total"] * 100) if stats["rising_total"] > 0 else 0
    non_rising_up_rate = (stats["non_rising_up"] / stats["non_rising_total"] * 100) if stats["non_rising_total"] > 0 else 0
    
    print(f"Total Rising Peak Patterns Found: {stats['rising_total']}")
    print(f"Rising Pattern Accuracy (Result=UP): {stats['rising_correct']}/{stats['rising_total']} ({rising_acc:.1f}%)")
    print(f"Non-Rising Pattern Up Rate: {stats['non_rising_up']}/{stats['non_rising_total']} ({non_rising_up_rate:.1f}%)")
    print(f"Conclusion: Rising peaks provide a {rising_acc - non_rising_up_rate:+.1f}% predictive edge.")

if __name__ == "__main__":
    main()
