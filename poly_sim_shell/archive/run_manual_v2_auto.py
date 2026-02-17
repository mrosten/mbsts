
import asyncio
import sys
from manual_buy_v2 import ManualBuyerV2

# Redirect stdout to capture all prints
class Tee(object):
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stdout = sys.stdout
        sys.stdout = self
    def __del__(self):
        sys.stdout = self.stdout
        self.file.close()
    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)
    def flush(self):
        self.file.flush()

async def run():
    print("--- Auto Running ManualBuyerV2 ---")
    buyer = ManualBuyerV2()
    await buyer.fetch_current_market()
    
    # Determine winning side
    up_price = buyer.market_data["up_price"]
    down_price = buyer.market_data["down_price"]
    
    side = "UP" if up_price > down_price else "DOWN"
    token_id = buyer.market_data["up_id"] if side == "UP" else buyer.market_data["down_id"]
    
    print(f"Auto-selected side: {side} (Price: {max(up_price, down_price)})")
    
    # Execute buy for $1
    await buyer.execute_market_buy(side, token_id, 1.0)

if __name__ == "__main__":
    # We don't need Tee if we use shell redirection, but let's keep it simple and just print to stdout
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
