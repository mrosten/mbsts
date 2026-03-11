import os
import sys
import importlib

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory
parent_dir = os.path.dirname(current_dir)

# Add the parent directory to sys.path so we can import the folder as a package
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import dynamically based on the actual folder name
pkg_name = os.path.basename(current_dir)
try:
    _main_module = importlib.import_module(f"{pkg_name}.main")
    main = getattr(_main_module, "main")
    print(f"DEBUG: Successfully bootstrapped '{pkg_name}' as a package.")
except ImportError as e:
    print(f"DEBUG: Failed to bootstrap package '{pkg_name}': {e}")
    # Absolute last resort fallback
    import main as _main_module
    from main import main

if __name__ == "__main__":
    main()
