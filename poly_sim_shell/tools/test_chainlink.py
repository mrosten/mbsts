
from web3 import Web3

# Correct Address
CHAINLINK_BTC_FEED = "0xc907E116054Ad103354f2D350FD2514433D57F6f"
CHAINLINK_ABI = '[{"inputs":[],"name":"latestAnswer","outputs":[{"internalType":"int256","name":"","type":"int256"}],"stateMutability":"view","type":"function"}]'

RPC_URL = "https://polygon-rpc.com"

try:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    print(f"Connected: {w3.is_connected()}")
    
    contract = w3.eth.contract(address=CHAINLINK_BTC_FEED, abi=CHAINLINK_ABI)
    price = contract.functions.latestAnswer().call()
    print(f"Price: {price / 10**8}")

except Exception as e:
    print(f"Error: {e}")
