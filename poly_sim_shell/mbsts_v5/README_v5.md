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
| Whale Protect | (v4 Legacy — see MOM ADV Whale Shield) |
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
| MOM | Momentum | Price/time-based momentum (v5.9 Expert) |

### MOM Scanner — Buy Modes (v5.9)

The Momentum scanner now supports four exclusive buy modes (2x2 Grid):

- **Standard (STN)** — Basic threshold/time signals.
- **Pre-Buy (PBN)** — Advanced entry at -15s based on next-window demand. Follows spreads $\ge$ 2¢; reverses on < 2¢.
- **Hybrid (HBR)** — Only Pre-Buys on $\ge$ 2¢ leads. If the gap is small, it waits for the window to start (standard behavior).
- **Expert (ADV)** — Uses **5m ATR** to dynamically shift thresholds and behaviors. Requires configuration via the `CONFIGURE ADV` modal.

---

## Expert & Volatility Logic (v5.9)

The **MOM ADV** mode introduces Tier-based trading:
- **ATR Gateways**: Define Boundaries for "Stable" vs. "Chaos" tiers.
- **Dynamic Offsets**: Automatically adds/subtracts from the base threshold (e.g. +10¢ in Chaos).
- **Whale Shield**: Emergency exit triggered in the final seconds if the price stays within a "reach" (e.g. 5¢) of the 50¢ neutral zone.

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

## Momentum Analytics Log (v5.9.4)

A specialized session log `logs/momentum_adv_YYYYMMDD_HHMMSS.csv` is generated automatically to help optimize momentum parameters. It captures one consolidated row per window with these fields:

| Category | Fields |
|---|---|
| **Timing** | Window ID (start_ts), Winner (UP/DOWN) |
| **Pre-Window** | BTC Price & Gap at -15s and -60s. **BTC Velocity** (Move in last 60s). |
| **Early Open** | BTC Price & Poly Gap at 5s, 10s, and 15s. |
| **Entry Depth** | UP/DOWN Bids and **Spread** at the 15s mark. |
| **Milestones** | First side and elapsed time to hit **55¢, 60¢, and 65¢**. |
| **Volume/RSI** | **1m BTC Volume** and **1m RSI** at settlement. |
| **Drawdown** | **Max Against** (Window High/Low vs Open) to calculate optimal SL. |
| **ATR** | 5m Average True Range at settlement. |

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

If the next market isn't published yet, logs `Next window not yet available`.

---

## Chat Summary & Future Roadmap (Session Feb 2026)

This session focused on hardening the bot for high-volatility environments and refining log accuracy.

### Implemented Specs:
- **v5.8 Refinements**: Accurate accuracy displays (starts at Window 2), `Esc` key dismissal, and proper log event serialization.
- **v5.9/v5.9.1/v5.9.2**: The MOM Expert overhaul including ATR-based tiering, Whale Shielding, and a compact 2x2 Grid UI.
- **v5.9.3 Logic Guard**: Refactored scanner loops to use persistent state (`base_threshold`), resolving background errors when UI modals are closed.

### Discarded / Future Priority Ideas:
- **Multi-Scanner Expert Tiering**: Applying the ATR-based Gateway logic to other scanners (Cobra, RSI) to dynamically adjust their sensitivity.
- **Dynamic Bet Scaling**: Automatically increasing $ bet size during "Stable" tiers and reducing it during "Chaos".
- **Global Whale Shield**: A protection layer that monitors all open positions (not just MOM) for flip-risk near 50¢ in the final seconds.
- **Historical Gap Guard**: Implementing a data-validation step on boot to ensure no phantom signals are generated from stale Binance/Chainlink data during initial backfill.

> [!IMPORTANT]
> This chat history is closed as of v5.9.3. Refer to the Roadmap above for priority items in the next development cycle.
