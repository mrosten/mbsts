import sys
import os

# Add directory to path
sys.path.append(r"c:\MyStuff\coding\turbindo-master\poly_sim_shell")

print("Attempting to import mbsts_algo_v4...")

try:
    import mbsts_algo_v4
    print("Import successful!")
    
    app = mbsts_algo_v4.SniperApp()
    print("SniperApp instantiated.")
    
    # Check if attributes exist
    if hasattr(app, 'last_second_exit_triggered'):
        print("Attribute 'last_second_exit_triggered' found.")
    else:
        print("ERROR: Attribute 'last_second_exit_triggered' MISSING.")
        
    print("Verification passed!")
except ImportError as e:
    print(f"Import Error: {e}")
except Exception as e:
    print(f"Runtime Error: {e}")
    import traceback
    traceback.print_exc()
