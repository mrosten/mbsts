import os

target_files = [
    "trade_engine.py",
    "scanners.py",
    "risk.py",
    "app.py",
    "test_pbn_standalone.py",
    "test_pbn_analysis.py"
]

for filename in target_files:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace occurrences
        new_content = content.replace("trend_4h", "trend_1h")
        new_content = new_content.replace("Trend 4H", "Trend 1H")
        new_content = new_content.replace("Trend_4H", "Trend_1H")
        
        if new_content != content:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Updated {filename}")
        else:
            print(f"No changes in {filename}")
    else:
        print(f"File not found: {filename}")
