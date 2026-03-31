import os
import sys
# Set up sys.path to find config
sys.path.append(os.getcwd())
from config import TradingConfig, DB_PATH

print(f"DB_PATH from config: {DB_PATH}")
print(f"File exists: {os.path.exists(DB_PATH)}")
