import os
import sys

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (so we can import 'mbsts_v5')
parent_dir = os.path.dirname(current_dir)

# Add the parent directory to sys.path
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now we can import from the package correctly
try:
    from mbsts_v5.main import main
except ImportError:
    # Fallback for when running from within the folder directly without parent in path
    from main import main

if __name__ == "__main__":
    main()
