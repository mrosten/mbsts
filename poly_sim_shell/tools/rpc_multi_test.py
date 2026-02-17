"""Test multiple RPCs to query proxy ownership."""
import sys, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PROXY = '0x988a5750C8277c68A893DC8FF9E9D7362199B9c2'
EOA = '0x536191CAC18a2e1936BfEd0dAc7831dDA3CC8010'
eoa_pad = EOA[2:].lower().zfill(64)

rpcs = [
    'https://polygon.llamarpc.com',
    'https://rpc.ankr.com/polygon',
    'https://polygon-bor-rpc.publicnode.com',
    'https://1rpc.io/matic',
]

calls = [
    ('isOwner(EOA)', '0x2f54bf6e' + eoa_pad),
    ('getOwner()', '0x893d20e8'),
    ('owner()', '0x8da5cb5b'),
    ('getOwners()', '0xa0e67e2b'),
    ('getThreshold()', '0xe75235b8'),
]

for rpc in rpcs:
    print(f"--- {rpc[:50]} ---")
    for name, data in calls:
        try:
            r = requests.post(rpc, json={
                'jsonrpc': '2.0', 'method': 'eth_call',
                'params': [{'to': PROXY, 'data': data, 'gas': '0x100000'}, 'latest'],
                'id': 1
            }, timeout=8).json()
            result = r.get('result')
            error = r.get('error')
            if error:
                print(f"  {name}: ERROR {error.get('message','?')[:60]}")
            elif result is None:
                print(f"  {name}: None")
            elif result == '0x':
                print(f"  {name}: 0x (reverted)")
            elif len(result) <= 66:
                val = int(result, 16)
                if val == 0:
                    print(f"  {name}: 0 (FALSE)")
                elif val == 1:
                    print(f"  {name}: 1 (TRUE)")
                else:
                    addr = '0x' + result[-40:]
                    match = ' <-- YOUR EOA!' if addr.lower() == EOA.lower() else ''
                    print(f"  {name}: {addr}{match}")
            else:
                # Could be array - try to decode
                raw = result[2:]
                if len(raw) >= 192:  # array with at least 1 element
                    offset = int(raw[:64], 16) * 2
                    arr_len = int(raw[offset:offset+64], 16)
                    print(f"  {name}: array[{arr_len}]")
                    for i in range(min(arr_len, 5)):
                        start = offset + 64 + i * 64
                        addr = '0x' + raw[start:start+64][-40:]
                        match = ' <-- YOUR EOA!' if addr.lower() == EOA.lower() else ''
                        print(f"    [{i}] {addr}{match}")
                else:
                    print(f"  {name}: {result[:60]}...")
        except Exception as e:
            print(f"  {name}: EXCEPTION {str(e)[:50]}")
    print()
