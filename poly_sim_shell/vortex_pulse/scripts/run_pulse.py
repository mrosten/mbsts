import os
import sys
import importlib
from dotenv import load_dotenv

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (vortex_pulse folder) - go up one level from scripts
parent_dir = os.path.dirname(current_dir)

# Load environment variables from .env in the root folder
load_dotenv(os.path.join(parent_dir, '.env'))

# Add the parent directory to sys.path so we can import the modules directly
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import main directly from the scripts folder (it was moved here)
try:
    import main as _main_module
    main = getattr(_main_module, "main")
except ImportError as e:
    print(f"ERROR: Failed to import main: {e}")
    sys.exit(1)

if __name__ == "__main__":
    main()
