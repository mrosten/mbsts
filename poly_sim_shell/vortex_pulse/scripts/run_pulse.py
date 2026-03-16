import os
import sys
import importlib

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (vortex_pulse folder)
parent_dir = current_dir

# Add the parent directory to sys.path so we can import the modules directly
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import main directly from the scripts folder (it was moved here)
try:
    import main as _main_module
    main = getattr(_main_module, "main")
    print(f"DEBUG: Successfully imported main from scripts folder.")
except ImportError as e:
    print(f"DEBUG: Failed to import main: {e}")
    sys.exit(1)

if __name__ == "__main__":
    main()
