import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TradingConfig:
    MARKET_FREQ: int = 5  # Can be 5 or 15
    
    @property
    def WINDOW_SECONDS(self) -> int:
        return self.MARKET_FREQ * 60
        
    @property
    def PHASE1_DURATION(self) -> int:
        # 60s for 5m, 300s for 15m (consistent with v4/v5 logic)
        return 60 if self.MARKET_FREQ == 5 else 300
        
    @property
    def MIN_BET(self) -> float:
        # $1 for 5m, $5.50 for 15m (consistent with v4/v5 logic)
        return 1.00 if self.MARKET_FREQ == 5 else 5.50

    # Static settings
    LOG_INTERVAL: int = 15
    DEFAULT_RISK_PCT: float = 0.12
    STRONG_RISK_PCT: float = 0.20
    MIN_LIMIT_ORDER_SIZE: float = 5.50
    MAX_BET_SESSION_CAP: float = 100.0
    LIVE_RISK_DIVISOR: int = 8 
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
