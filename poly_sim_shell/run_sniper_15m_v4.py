from mbsts_v4.config import TradingConfig
from mbsts_v4.main import main

if __name__ == "__main__":
    # Override for 15M mode
    TradingConfig.WINDOW_SECONDS = 900
    main()
