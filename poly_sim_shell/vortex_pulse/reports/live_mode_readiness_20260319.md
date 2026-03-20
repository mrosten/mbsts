# Live Mode Readiness Audit
_Generated: 2026-03-19 10:10_

---

## ✅ Credentials & Connection

| Item | Status |
|---|---|
| `PRIVATE_KEY` | ✅ Loaded from `.env` — never hardcoded |
| `PROXY_ADDRESS` | ✅ Loaded from `.env` |
| `CHAIN_ID` | ✅ 137 (Polygon) |
| `HOST` | ✅ `https://clob.polymarket.com` |
| LiveBroker init | ✅ Background worker (won't freeze startup) |

---

## 💸 Buy / Sell Execution

| Item | Status |
|---|---|
| Live buy uses limit `0.99` sweep | ✅ Acts as market order — bypasses 5-share minimum |
| Token IDs (`up_id` / `down_id`) passed from market data | ✅ |
| Live sell queries Polymarket for actual held shares | ✅ |
| Tranche limit orders supported | ✅ `$5.50` minimum guard before placing |
| Custom TP/SL per algorithm | ✅ Applied in `_handle_successful_buy()` |
| `is_live` flag stored in `window_bets` per position | ✅ |

---

## 🛡️ Safety & Risk Guards

| Item | Status |
|---|---|
| Sync drift checker | ✅ Fixed: now includes `pre_buy_shares`, latched (logs once) |
| `broker.sell()` negative share guard | ✅ Fixed: clamps to 0 (no more -21.74 drift) |
| `exec_safety_mode` (SAFE/NORMAL/AGGRO) | ✅ Configurable in Global Settings |
| `total_risk_cap` window enforcement | ✅ |
| Whale Shield | ✅ Active |
| `app_active` thread guard (crash prevention on shutdown) | ✅ |

---

## ⚙️ Settings to Change for Full-Balance Live Mode

To make live mode behave **identically to sim** using your full balance:

### 1. `config.py` — `LIVE_RISK_DIVISOR`

```python
# Before (conservative — divides all position sizes by 8 in live mode):
LIVE_RISK_DIVISOR: int = 8

# After (matches sim sizing 1:1):
LIVE_RISK_DIVISOR: int = 1
```

### 2. Global Settings → "Auto-Sync Risk" → **Turn ON**

This syncs the risk bankroll to your actual wallet balance at the start of each window.

### 3. Global Settings → "Exec Safety Mode" → Set to **`NORMAL`**

`SAFE` mode adds extra price filters that make the bot more selective than sim. `NORMAL` matches sim behavior.

### 4. Starting Risk Bankroll

Manually set the risk bankroll in Global Settings to your wallet balance the first time. Auto-Sync will keep it updated after that.

---

## 🟢 Already Identical Between Sim and Live

- Same scanners, signals, and TP/SL logic
- Same price filters (min/max price, skeptic penalties)
- Same risk cap, tranche, and Whale Shield settings
- Same window timing and pre-buy behavior

---

## ⚠️ Caution

> Before running with a full bankroll, do a **1-window test** with `MAX_BET_SESSION_CAP` set low (e.g., `$5`) to confirm orders are going through correctly on Polymarket before releasing full sizing.

---

## 🚫 Known Limitation

The **Sync Drift checker** (`SYNC DRIFT` error) only runs in SIM mode. In live mode, positions are tracked via on-chain balance queries — not the internal `window_bets` dict — so local drift is not applicable.
