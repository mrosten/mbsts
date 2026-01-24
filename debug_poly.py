import sys
import traceback
import runpy
import os

print("Starting debug runner...")
# Ensure logs dir exists
os.makedirs("logs", exist_ok=True)

# Set args for the app
sys.argv = ["polytrading", "--run_app"]

try:
    runpy.run_module("example_sprout_apps.polytrading.main", run_name="__main__", alter_sys=True)
except Exception:
    with open("logs/crash_report.txt", "w") as f:
        traceback.print_exc(file=f)
    print("Crashed. See logs/crash_report.txt")
except SystemExit:
    pass # Expected if app exits
