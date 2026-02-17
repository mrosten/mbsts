import os
import sys
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient

load_dotenv()
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")

def main():
    try:
        key_acct = Account.from_key(PRIVATE_KEY)
        funder = PROXY_ADDRESS if PROXY_ADDRESS else key_acct.address
        client = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=1 if PROXY_ADDRESS else 0, funder=funder)
        
        from py_clob_client.clob_types import BalanceAllowanceParams
        print("--- Source of BalanceAllowanceParams ---")
        import inspect
        try:
            src = inspect.getsource(BalanceAllowanceParams)
            with open("params_source.txt", "w") as f:
                f.write(src)
            print("Done dumping source.")
        except Exception as e:
            print(f"Could not get source: {e}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
