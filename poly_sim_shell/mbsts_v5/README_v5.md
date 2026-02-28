# Polymarket Sniper — Version 5

A Textual-based terminal UI for automated and semi-automated trading on Polymarket BTC 5-minute binary options markets.

---

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point — launches the app, accepts `--live` flag |
| `app.py` | Main Textual application, UI, scanner loop, settlement, TP/SL |
| `broker.py` | `SimBroker`, `LiveBroker`, `TradeExecutor` — all buy/sell execution |
| `market.py` | `MarketDataManager` — BTC price (Kraken WS + Chainlink + Binance), Polymarket prices |
| `risk.py` | `RiskManager` — bankroll, bet sizing, register/reset per window |
| `scanners.py` | All scanner algorithms (NPattern, Momentum, RSI, etc.) |
| `config.py` | `TradingConfig` — window duration, risk divisor, constants |

---

## Running

```bash
# Simulation mode
python -m poly_sim_shell.mbsts_v5.main

# Live mode (auto-enables LIVE checkbox on startup)
python -m poly_sim_shell.mbsts_v5.main --live
```

---

## UI Layout

### Top Bar
- **Bal** — current wallet/sim balance
- **RUN** — session runtime
- **WIN** — time remaining in current 5-min window

### Settings Row
| Field | Description |
|---|---|
| Bet $ | Fixed amount per trade (used by MOM and manual buys) |
| Bankroll | Risk bankroll cap (auto-set from balance on live toggle) |
| TP % | Take Profit price threshold (e.g. 95 = sell when price hits 95¢) |
| SL % | Stop Loss ROI threshold (e.g. 40 = sell when down 40% ROI) |
| Min Diff | Minimum BTC price move from open before entering |
| Min/Max Price | Option price bounds — skips trades outside this range |

### Scanner Grid
Each scanner button has a checkbox (on/off) and a label that blinks yellow when a pending (queued) bet is waiting.

Click any scanner label to open its **Settings Modal** (weight, mode, thresholds).

### Checkboxes
| Checkbox | Effect |
|---|---|
| TP/SL | Enables automatic Take Profit and Stop Loss monitoring |
| Strong Only | Restricts to Strong-signal scanners |
| 1 Trade Max | Only one active position allowed per window |
| Whale Protect | (reserved) |
| LIVE MODE | Switches from simulation to live Polymarket execution |

### Manual Buttons
- **BUY UP / BUY DN** — Immediate manual buy at current ask
- **SELL UP / SELL DN** — Immediate sell of current UP/DOWN position

### Command Box
Type admin commands and press Enter:

| Command | Effect |
|---|---|
| `sl+` | Enable SL+ Recovery Mode |
| `sl-` | Disable SL+ Recovery Mode |
| `lo=true/false` | Manual lockout toggle |

---

## Order Execution

All orders are placed as **limit orders at $0.99** — this ensures they fill immediately as market taker orders while bypassing Polymarket's 5-share minimum rule for small buys.

Sell orders query the exact token balance from Polymarket and sell the entire position for that token.

Each Polymarket 5-minute window has unique UP and DOWN token IDs, so positions from different windows cannot interfere with each other.

---

## Scanners

| Code | Name | Signal Type |
|---|---|---|
| COB | Cobra | Momentum reversal from 60m candles |
| FAK | Fakeout | False breakout detection |
| GRI | GrindSnap | Sustained grind exhaustion |
| LAT | LateReversal | Late-window mean reversion |
| LIQ | Liquidity | Liquidity vacuum fill |
| MEA | MeanReversion | Bollinger Band extremes + 4H trend |
| MES | Mesa | Choppy distribution top collapse |
| MID | MidGame | Mid-window trend continuation |
| MIN | MinOne | Last-minute wick pattern |
| MOM | Momentum | Price/time-based momentum (see below) |
| MOS | Moshe | Multi-stage time+diff signal |
| NPA | NPattern | N-shaped price pattern |
| POS | PostPump | Post-pump fade |
| RSI | RSI | Overbought/oversold reversion |
| SLI | Slingshot | Elastic band snapback |
| STA | BullFlag | Staircase breakout |
| STE | StepClimber | Step pattern continuation |
| TRA | TrapCandle | Candle trap reversal |
| VOL | VolCheck | Volume+price divergence |
| ZSC | ZScore | Statistical z-score breakout |

### MOM Scanner — Buy Mode

The Momentum scanner has two buy modes, set in its Settings Modal:

- **Standard** — fires on threshold/time/duration signal and buys the current window
- **Pre-Buy Next** — ignores signals; instead, 15 seconds before the current window ends, fetches the **next** window's prices and buys the higher-ask side (= more market demand). Falls back to 4H trend direction on a 50/50 split. The position is invisible to TP/SL until the new window begins.

---

## TP / SL Logic

| Trigger | Threshold | Action |
|---|---|---|
| Max Profit | Price ≥ 99¢ | Immediate sell |
| Take Profit | Price ≥ TP% setting | Sell |
| Stop Loss | ROI ≤ −SL% | Sell |
| Clearly Lost | Final-second bid < 10¢ | Skip sell, let expire |

**SL+ Recovery Mode** (`sl+` command): on an SL hit, automatically places a counter-trade on the opposite side for the same dollar amount at the same price, aiming to recover the loss in the next move.

---

## Settlement

At window close:
1. BTC settle direction (UP/DOWN) is determined from open vs close price
2. Sim shares at $1.00 each — net PnL logged to console
3. Live mode: winning unclosed positions are refilled at $1.00/share
4. `window_bets` cleared for the next window

---

## Bankroll Exhaustion Guard

After each settlement, if:
- A bet was placed this window (confirmed loss), **and**
- Bankroll < Bet $ (or < $1.00 hard floor)

The bot **freezes**:
- Final CSV snapshot written
- Final `═══ FINAL LOG ═══` appended to console log
- All market fetching and scanning stops
- Full-screen **🔴 BOT FROZEN** modal appears

Dismiss with OK. Bot stays halted until restart.

---

## Persistent Settings

All UI settings are auto-saved to `v5_settings.json` on every change and restored on next startup:

- Bet $, TP%, SL%, Min Diff, Min Price, Max Price
- TP/SL Active, 1 Trade Max checkboxes
- SL+ mode, MOM Buy Mode
- All scanner weights

---

## Next Window Preview

At **20 seconds** before each window end, the bot fetches the next window's UP/DOWN bid/ask prices and logs them:

```
🔭 NEXT WINDOW (btc-updown-5m-XXXXXXXXXX): UP bid=52.0¢ ask=53.0¢  DN bid=48.0¢ ask=48.0¢
```

If the next market isn't published yet, logs `Next window not yet available`.
