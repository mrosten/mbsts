import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TradingConfig:
    # Time Settings
    WINDOW_SECONDS: int = 900 # 15 Minutes
    LOG_INTERVAL: int = 15
    PHASE1_DURATION: int = 300  # 5 Minute Impulse Phase for 15m candles
    
    # Risk Management
    DEFAULT_RISK_PCT: float = 0.12
    STRONG_RISK_PCT: float = 0.20
    MIN_BET: float = 5.50
    MAX_BET_SESSION_CAP: float = 100.0
    LIVE_RISK_DIVISOR: int = 8  # 1/8th of balance for Live Mode
    
    # Tolerances
    TOLERANCE_PCT: float = 0.002

# --- Web3 & RPC Config ---
POLYGON_RPC_LIST = [
    os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
    os.getenv("POLYGON_RPC", "https://polygon-rpc.com"),
    "https://rpc-mainnet.maticvigil.com",
    "https://rpc.ankr.com/polygon",
    "https://1rpc.io/matic"
]
POLYGON_RPC_LIST = list(dict.fromkeys(filter(None, POLYGON_RPC_LIST)))

CHAINLINK_BTC_FEED = "0xc907E116054Ad103354f2D350FD2514433D57F6f"
CHAINLINK_ABI = '[{"inputs":[],"name":"latestAnswer","outputs":[{"internalType":"int256","name":"","type":"int256"}],"stateMutability":"view","type":"function"}]'

# Live Config
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"
