from py_clob_client.client import ClobClient
import os
from dotenv import load_dotenv

load_dotenv()
pk = os.getenv("PRIVATE_KEY")
if not pk:
    print("No PK")
    exit()

try:
    client = ClobClient(host="https://clob.polymarket.com", key=pk, chain_id=137)
    print("Client attributes:")
    for d in dir(client):
        if not d.startswith("__"):
            print(f"- {d}")
    
    print("\nCheck for session:")
    if hasattr(client, 'session'):
        print(f"client.session found: {client.session}")
        print(f"headers: {client.session.headers}")
    elif hasattr(client, '_session'):
         print(f"client._session found: {client._session}")
    elif hasattr(client, 'http_client'):
         print(f"client.http_client found: {client.http_client}")

except Exception as e:
    print(f"Error: {e}")
