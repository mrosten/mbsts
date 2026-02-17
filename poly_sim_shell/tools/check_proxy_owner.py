"""Check who owns the Polymarket proxy by calling the implementation."""
import os, sys, requests, json
from dotenv import load_dotenv
from eth_account import Account

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv()

RPC = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
PROXY = os.getenv("PROXY_ADDRESS")
PK = os.getenv("PRIVATE_KEY")
EOA = Account.from_key(PK).address

def call(to, data):
    r = requests.post(RPC, json={"jsonrpc":"2.0","method":"eth_call",
        "params":[{"to":to,"data":data,"gas":"0x100000"},"latest"],"id":1}, timeout=10).json()
    return r.get("result")

print(f"EOA:   {EOA}")
print(f"Proxy: {PROXY}")
print(f"Impl:  0x44e999d5c2f66ef0861317f9a4805ac2e90aeb4f")
print()

# Call through the proxy (delegatecall to implementation)
eoa_pad = EOA[2:].lower().zfill(64)

tests = {
    "getOwners()":       "0xa0e67e2b",
    "owner()":           "0x8da5cb5b",
    "getOwner()":        "0x893d20e8",
    "getThreshold()":    "0xe75235b8",
    "isOwner(EOA)":      "0x2f54bf6e" + eoa_pad,
    "nonce()":           "0xaffed0e0",
    "VERSION()":         "0xffa1ad74",
}

for name, data in tests.items():
    result = call(PROXY, data)
    if result is None:
        print(f"  {name}: RPC returned None (error/revert)")
    elif result == "0x":
        print(f"  {name}: empty (reverted)")
    elif len(result) <= 66 and result != "0x" + "0"*64:
        val = int(result, 16) if result != "0x" else 0
        # Check if it looks like an address
        if val > 0 and len(hex(val)) > 20:
            addr = "0x" + result[-40:]
            match = " <-- YOUR EOA!" if addr.lower() == EOA.lower() else ""
            print(f"  {name}: {addr}{match}")
        elif val == 1:
            print(f"  {name}: TRUE (1)")
        elif val == 0:
            print(f"  {name}: FALSE/ZERO (0)")
        else:
            print(f"  {name}: {val}")
    elif result == "0x" + "0"*64:
        print(f"  {name}: 0x000...000 (zero/false)")
    else:
        print(f"  {name}: {result[:80]}...")

# Also try reading the Polygonscan verified source for the impl
print("\nChecking Polygonscan for impl contract source...")
try:
    url = f"https://api.polygonscan.com/api?module=contract&action=getabi&address=0x44e999d5c2f66ef0861317f9a4805ac2e90aeb4f"
    resp = requests.get(url, timeout=10).json()
    if resp.get("status") == "1":
        abi = json.loads(resp["result"])
        fn_names = [item.get("name","") for item in abi if item.get("type") == "function"]
        print(f"  ABI has {len(fn_names)} functions: {', '.join(fn_names)}")
    else:
        print(f"  ABI not available: {resp.get('message','?')}")
except Exception as e:
    print(f"  Error: {e}")

# Also check: does Polygonscan list proxy creation tx?
print("\nChecking contract creation tx...")
try:
    url = f"https://api.polygonscan.com/api?module=contract&action=getcontractcreation&contractaddresses={PROXY}"
    resp = requests.get(url, timeout=10).json()
    if resp.get("status") == "1" and resp.get("result"):
        for r in resp["result"]:
            print(f"  Creator: {r.get('contractCreator','?')}")
            match = " <-- YOUR EOA!" if r.get('contractCreator','').lower() == EOA.lower() else ""
            print(f"  {match}")
            print(f"  Tx: {r.get('txHash','?')}")
    else:
        print(f"  Not found: {resp.get('message','?')}")
except Exception as e:
    print(f"  Error: {e}")
