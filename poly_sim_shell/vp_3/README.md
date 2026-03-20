# Polymarket Vortex Pulse V5 — Complete System Reference

> **Version:** 5.9.11  
> **Runtime:** Python 3.12+ with [Textual](https://textual.textualize.io/) TUI  
> **Market:** Polymarket BTC 5-minute binary options (UP / DOWN)

---

## 1. Overview

Polymarket Vortex Pulse V5 is a fully automated, high-frequency execution bot that trades short-term directional binary options (UP/DOWN) on the Polymarket BTC 5-minute market. It runs inside a rich terminal UI (Textual TUI), evaluates **20 independent technical scanners** every second, manages risk dynamically, and can execute both simulated and live limit orders against the Polymarket CLOB.

Key capabilities:
- **Trade Protection Suite (v5.9.11)** — Configurable **Late-Window Lockout (LWL)** and **Sentiment Guard** to prevent losses from last-second volatility and oracle mismatches.
- **20 scanners** running in parallel, each with independent signal logic and full configurability
- **Advanced scanner configuration modals** for all algorithms with individual parameter tuning
- **Global skepticism filters** for odds and guess conflicts with premium adjustments
- **Simulation and Live modes** — identical execution path, switchable at runtime
- **Session-Specific Logging** — automated creation of a dedicated subfolder for every run
- **Low-Resolution Verification Graphs** — compact 160x80 diagnostic charts saving 80% disk space
- **Pending order queue** with automatic delayed execution when price enters bounds
- **TP/SL monitoring** with SL+ counter-trade recovery and per-scanner whale shield
- **Pre-buy system** for next-window anticipatory entries with mode selection
- **ATR-based dynamic tiering** (Expert/ADV mode) for volatility-aware thresholds
- **BriefingScanner** for automated macroscopic window analysis at start
- **Enhanced MOM/MM2** with Select widgets, mode explanations, and VECTOR scoring
- **Safe UI thread calls** preventing crashes during shutdown
- **Comprehensive CSV + console logging** with full field documentation
- **Persistent settings** saved to `pulse_settings.json` across sessions

---

## 2. Project Structure

```
vortex_pulse/
├── main.py              Entry point — mode selection, balance input, session folder creation
├── app.py               Core PulseApp class (TUI, compose, event handlers, settings persistence)
├── trade_engine.py      TradeEngineMixin — market loop, scanners, TP/SL, settlement logic
├── broker.py            SimBroker, LiveBroker, TradeExecutor — all buy/sell execution
├── market.py            MarketDataManager — BTC prices, Polymarket CLOB, trends, ATR
├── risk.py              RiskManager + AlgorithmPortfolio — bankroll, bet sizing
├── scanners.py          All 20 scanner algorithm classes + ALGO_INFO registry
├── ui_modals.py         Modal screens (GlobalSettings, AlgoInfo, MOMExpert, BullFlag, etc.)
├── config.py            TradingConfig dataclass, Web3/RPC constants, env vars
├── __init__.py          Package init
├── pulse_settings.json  Auto-generated persistent settings (created on first run)
└── lg/                  Log archive root
    └── session_YYYYMMDD_HHMMSS/     Unique folder for each run
        ├── pulse_log_5M_*.csv           Main session CSV log
        ├── pulse_log_5M_*_console.txt    Rich console mirror (ASCII-scrubbed)
        ├── pulse_log_5M_*_verification.html  HTML verification report
        ├── momentum_adv_*.csv             MOM Expert analytics log
        └── graphs/                      Verification graph PNGs (160x80)
```

### File Responsibilities

| File | Size (bytes) | Lines | Role |
|---|---|---|---|
| `main.py` | 1,800 | 50 | CLI entry point. Creates unique `session_` subdirectories. Prompts for SIM/LIVE mode, initial balance, and optional log filename override. |
| `app.py` | 65,000 | ~2,000 | `PulseApp` — TUI layout, event handlers (`on_checkbox_changed`, `on_input_changed`, `on_bet_mode_changed`), `on_mount` (timer setup, robust settings restore), `save_settings` (auto-persistence). |
| `trade_engine.py` | 85,000 | ~1,900 | `TradeEngineMixin` — 1Hz tick, TP/SL logic, settlement flow, and the corrected HTML audit generator that ensures window PnL matches console truth. |
| `broker.py` | 16,267 | ~276 | `SimBroker` (balance, shares, CSV log writer, buy/sell/settle/promote_prebuy), `LiveBroker` (Polymarket CLOB client via `py_clob_client`, real buy/sell against on-chain order book), `TradeExecutor` (routes buy/sell to sim or live broker). |
| `market.py` | 14,464 | ~328 | `MarketDataManager` — Kraken WebSocket (primary BTC price), Chainlink Oracle (secondary), Binance REST (tertiary fallback), Polymarket CLOB pricing, 4H/1H trend calculation, ATR, RSI, Bollinger Bands, price history tracking. |
| `risk.py` | 5,836 | ~143 | `RiskManager` — bankroll tracking, bet sizing (12% base, trend penalty, consecutive-loss reduction, min/max clamping). `AlgorithmPortfolio` — per-scanner P&L tracking, win/loss counters, active trade management. |
| `scanners.py` | 45,532 | ~888 | All 20 scanner classes inheriting from `BaseScanner` with configurable constructor parameters, plus the `ALGO_INFO` dictionary that maps 3-letter codes to names and descriptions. Includes new `BriefingScanner` and enhanced `Momentum2Scanner`. |
| `ui_modals.py` | 59,874 | ~893 | `GlobalSettingsModal` (CSV freq), `AlgoInfoModal` (scanner info + weight editor), `MOMExpertModal` (ATR tier config, Whale Shield), `BullFlagSettingsModal` (entry timing, tolerance, research logging), `BankrollExhaustedModal` (frozen state), `ResearchLogger` (BullFlag trade research CSV), **20+ individual scanner configuration modals** with Select widgets and parameter tuning. |
| `config.py` | 1,357 | 42 | `TradingConfig` dataclass (window duration, risk percentages, bet limits), Polygon RPC list, Chainlink contract address/ABI, env var loading for `PRIVATE_KEY`, `PROXY_ADDRESS`. |

---

## 3. Running

```bash
# From the parent directory of poly_sim_shell/
python -m poly_sim_shell.vortex_pulse.main
```

The CLI will prompt:
1. **Mode** — `(1) Sim Mode` (default) or `(2) Live Mode`
2. **Initial Balance** — starting USD for simulation (default `$100.00`)
3. **Log Filename** — auto-generates `lg/sim_log_5M_YYYYMMDD_HHMM.csv` if blank

### Environment Variables (Live Mode)

| Variable | Purpose |
|---|---|
| `PRIVATE_KEY` | Ethereum private key for Polymarket CLOB signing |
| `PROXY_ADDRESS` | Optional proxy/funder address for delegated signing |
| `POLYGON_RPC_URL` | Primary Polygon RPC endpoint (fallback list in `config.py`) |

---

## 4. Execution Flow (Per-Tick)

The core loop `fetch_market_loop()` in `trade_engine.py` fires every **1 second** via `set_interval`. Each tick:

### 4.1 Window Synchronization
- Computes the current 5-minute window start timestamp (`floor(minute/5)*5`)
- Detects **new window** transitions → resets scanners, pending bets, latches, revenue tracker
- If booted mid-round (>10s elapsed), activates **Mid-Window Lockout** until the next clean window
- Promotes any pre-buy positions from the previous cycle into `window_bets`

### 4.2 Data Gathering (Parallel)
Four concurrent API calls via `ThreadPoolExecutor`:
1. **Kraken WebSocket** → live BTC/USD price (primary, <5s freshness requirement)
2. **Binance REST** → 200 × 1-minute OHLCV candles → RSI(14), Bollinger Bands(20), ATR(5)
3. **Binance REST** → 4-hour and 1-hour trend (SMA crossover, updated every 15 minutes)
4. **Polymarket CLOB** → UP/DOWN bid, ask, midpoint prices, token IDs for the current window slug

Price fallback chain: Kraken WS → Chainlink Oracle → Binance REST → last known price.  
All prices are sanity-checked (reject >5% deviation from last known).

### 4.3 Market Data Update
The `market_data` dictionary is updated with all fetched values plus computed analytics:
- `btc_price`, `btc_open`, `btc_dyn_rng` (intra-window high−low range)
- `up_price`, `down_price`, `up_bid`, `down_bid`, `up_ask`, `down_ask`
- `odds_score` (UP_bid − DN_bid in cents), `trend_4h`, `trend_1h`
- `rsi_1m`, `atr_5m`

### 4.4 Pending Bet Execution
Before scanning, the engine checks `pending_bets` (queued signals waiting for price to enter bounds). If the current ask price is now within `[Min Price, Max Price]` and bankroll allows, it executes immediately.

### 4.5 Scanner Evaluation
All 20 scanners are iterated. For each enabled scanner:
1. Call its `analyze()` method with the appropriate data slice
2. Capture the signal into `tick_signals` for CSV analytics
3. If result is `WAIT` or `NONE` → skip
4. If result contains `BET_UP` or `BET_DOWN`:
   - **1-Trade-Max** guard (optional)
   - **Strong Only** filter (optional — requires keywords like STRONG, CONFIRMED, MAX)
   - **Min Diff** filter (minimum BTC move from open)
   - **Bet sizing** via `RiskManager.calculate_bet_size()` × scanner weight
   - **Whale Protect** cap (optional — max 25% of bankroll per trade)
   - **Price bounds** check → execute immediately or queue as pending

### 4.6 Scanner Analytics Push
After the scanner loop, aggregated analytics are pushed to `market_data`:
- `master_score` = (# UP signals) − (# DOWN signals)
- `master_status` = `BUY_UP` / `BUY_DN` / `NEUTRAL`
- `active_scanners` = count of scanners with BET signals
- Individual flags: `sling_signal`, `cobra_signal`, `flag_signal`

### 4.7 TP/SL Monitoring
For every open position in `window_bets`:
- **Max Profit** — price ≥ 99¢ → immediate sell
- **Take Profit** — price ≥ TP setting (default 95¢) → sell
- **Stop Loss** — ROI ≤ −SL setting (default 40%) → sell
- **SL+ Recovery** — on SL hit, automatically places a counter-trade on the opposite side for the same dollar amount

### 4.8 UI Update
Updates all UI labels: BTC price, open, diff, trend, ATR, option prices, balance, sell button values.

---

## 5. v5.9.5 Major Features

### 5.1 Advanced Scanner Configuration System

**Individual Scanner Modals**
- **20+ dedicated configuration modals** - one for each scanner algorithm
- **Click any scanner label** to open its configuration modal
- **Real-time parameter tuning** with immediate effect
- **Persistent settings** saved to `v5_settings.json`

**Configuration Parameters by Scanner Type:**

| Scanner | Key Parameters | Default Values |
|---|---|---|
| **RSI** | `rsi_threshold`, `time_remaining_min` | 20, 80s |
| **TrapCandle** | `start_move_pct`, `retrace_ratio` | 0.002, 0.35 |
| **MidGame** | `min_elapsed`, `max_green_ticks` | 90s, 25 |
| **LateReversal** | `min_elapsed`, `surge_pct` | 200s, 1.0003 |
| **PostPump** | `min_pump_pct`, `reversal_depth` | 0.003, 0.9985 |
| **StepClimber** | `tick_count`, `climb_pct` | 15, 1.001 |
| **Slingshot** | `ma_period` | 15 |
| **MinOne** | `wick_multiplier` | 1.5 |
| **LiquidityVacuum** | `break_structure_pct` | 1.0001 |
| **Cobra** | `ma_period`, `std_dev_mult` | 15, 1.5 |
| **Mesa** | `pump_threshold`, `cross_count` | 0.001, 2 |
| **MeanReversion** | `reversal_threshold` | 0.0005 |
| **GrindSnap** | `grind_duration`, `snap_duration`, `min_slope_pct`, `reversal_ratio` | 100s, 20s, 0.1%, 0.60 |
| **VolCheck** | `avg_3m_multiplier` | 1.0 |
| **Moshe** | `moshe_threshold`, `t1/t2/t3`, `d1/d2/d3` | 0.86, 290/80/15, 2000/80/25 |
| **ZScore** | `z_threshold`, `coil_threshold` | 3.5, 0.001 |
| **Briefing** | `rsi_low/high`, `odds_thresh`, `imb_thresh`, `signal_thresh` | 30/70, 5.0, 2.0, 2 |

### 5.2 Global Skepticism Filters

**Purpose:** Automatically apply premium adjustments when market signals conflict with scanner recommendations.

**Filter Types:**
1. **Odds Conflict Penalty** - When Polymarket odds favor the opposite direction
2. **Guess Conflict Penalty** - When automated window briefing conflicts with scanner

**Implementation:**
```python
def apply_global_skeptic_filter(self, side, price, name="Scanner"):
    # 1. Check Max Price first (Hard Bound)
    if price > max_pr and "Moshe" not in name:
        return False, f"Price {price*100:.1f}c > Max {max_pr*100:.1f}c"
    
    # 2. Odds Conflict Penalty
    odds = self.market_data.get("odds_score", 0)
    if (side == "UP" and odds < -5.0) or (side == "DOWN" and odds > 5.0):
        effective_min += odds_skeptic  # Default 5¢ premium
    
    # 3. Guess Conflict Penalty  
    guess_score = self.market_data.get("net_guess_score", 0)
    guess_side = "UP" if guess_score >= 2 else ("DOWN" if guess_score <= -2 else "NEUTRAL")
    if guess_side == "NEUTRAL" or guess_side != side:
        effective_min += guess_skeptic  # Default 3¢ premium
```

**UI Controls:**
- **Skeptic Odds:** Input field for odds conflict premium (default 0.05¢)
- **Skeptic Guess:** Input field for guess conflict premium (default 0.03¢)

### 5.3 Enhanced MOM/MM2 System

**Mode Selection with Select Widgets:**
- **TIME Mode:** Classic leader-pick after duration (default 10s)
- **PRICE Mode:** Immediate trigger on cent threshold (default 60¢)
- **DURATION Mode:** Threshold hold for sustained period
- **VECTOR Mode (MM2):** Unified scoring analysis

**Dynamic Mode Explanations:**
Real-time explanations update when mode changes:
```
TIME Mode: Classic leader-pick. Waits for the duration (default 10s) and then bets the side that is leading in cents.
PRICE Mode: Immediate trigger. Bets as soon as either side hits the specified cent threshold (e.g. 60¢).
DURATION Mode: Threshold hold. Bets if a side stays above the cent threshold for the full duration.
VECTOR Mode (MM2): Unified scoring. Analyzes Price Lead, BTC Velocity, 1H Trend, Sentiment, and RSI simultaneously.
```

**MM2 VECTOR Scoring Engine:**
- **Price Lead:** Current price advantage
- **BTC Velocity:** 60-second price momentum 
- **1H Trend:** Macro trend alignment
- **Sentiment:** RSI positioning
- **RSI:** Overbought/oversold conditions

### 5.4 BriefingScanner - Automated Window Analysis

**Activation:** Runs automatically at window start (T-05:00)

**Analysis Components:**
1. **Trend & RSI Assessment**
   - 1H trend strength (BULLISH/BEARISH/NEUTRAL)
   - 1m RSI positioning (Oversold/Overbought/Neutral)

2. **Market Context**
   - BTC velocity (Spiking UP/Dropping DN/Stable)
   - Volatility regime (HIGH/MODERATE/LOW based on ATR)

3. **Market Microstructure**
   - Polymarket odds bias (favors UP/DOWN/balanced)
   - Ask imbalance (UP premium/DN premium/balanced)

4. **Automated Guess Calculation**
   - Score-based directional prediction
   - Net score from 8 factors (trend, RSI, odds, imbalance)

**Output Format:**
```
📊 WINDOW BRIEFING (T-05:00)
1. Trend: 1H is BULLISH (S-UP), 1m RSI is Oversold (25).
2. Context: BTC is Spiking UP (+$45.2), Volatility is HIGH (ATR=52).
3. Market: Odds favors UP (+7.3¢), Ask is UP premium (+3.1¢).
🔮 MY GUESS: UP
────────────────────────────────────
```

### 5.5 Safe UI Thread Calls

**Problem:** Background threads calling UI updates during app shutdown caused crashes.

**Solution:** `safe_call()` wrapper method
```python
def safe_call(self, func, *args, **kwargs):
    """Utility for background threads to safely update UI without crashing during shutdown."""
    try:
        if not getattr(self, "app_active", False): return
        self.call_from_thread(func, *args, **kwargs)
    except RuntimeError:
        pass  # App is shutting down
```

**Usage:** All background thread UI updates now use `safe_call()` instead of `call_from_thread()`

### 5.6 Enhanced Whale Shield Protection

**Per-Scanner Configuration:**
- Each scanner (Momentum/MM2) now has independent `adv_settings`
- **Shield Time:** Activation point in seconds (default 45s = T-45s)
- **Shield Reach:** Distance from 50¢ that triggers protection (default 5¢)
- **Automatic Exit:** Sells all positions when price too tight near 50¢

**Logic Enhancement:**
```python
if (time.time() - self.market_data["start_ts"]) >= s_time_limit:
    up_p = self.market_data.get("up_bid", 0.5)
    reach = adv.get("shield_reach", 5) / 100.0
    if abs(up_p - 0.50) < reach:
        self.log_msg(f"🛡️ WHALE SHIELD ({sc_key}): Market too tight ({up_p*100:.1f}¢). Emergency Exit.")
        await self.trigger_sell_all("UP")
        await self.trigger_sell_all("DOWN")
```

---

## 6. Scanners (20 Algorithms)

| Code | Class | Signal Type | Description |
|---|---|---|---|
| **NPA** | `NPatternScanner` | Breakout | Impulse → retrace → breakout above prior high. Requires 20–85% retrace depth. |
| **FAK** | `FakeoutScanner` | Reversal | Rejected rescue attempt — price spikes above open then fails back below. |
| **MOM** | `MomentumScanner` | Momentum | Three modes: **TIME** (10s leader), **PRICE** (threshold trigger), **DURATION** (sustained hold). End-of-window guard at 280s. |
| **RSI** | `RsiScanner` | Mean Reversion | RSI < 15 + price below lower Bollinger Band + >100s remaining. |
| **TRA** | `TrapCandleScanner` | Fade | Aggressive breakout gets >75% retraced within the window. |
| **MID** | `MidGameScanner` | Failed Rescue | Bulls fail to hold green in mid-round (100–200s). Requires 4H trend ≠ UP. |
| **LAT** | `LateReversalScanner` | Late Surge | Late-window (>220s) surge from red to green after early drop. |
| **STA** | `StaircaseBreakoutScanner` | Breakout | 3+ rising lows in 15-candle window + breakout. Configurable entry timing (Aggressive/Conservative/Pullback), ATR multiplier, max price, research logging. |
| **POS** | `PostPumpScanner` | Mean Reversion | Fades price below midpoint after a prior-window pump (>0.5% move). |
| **STE** | `StepClimberScanner` | Sniper Entry | Perfect touch of 20-period MA from above (within 0.15%). |
| **SLI** | `SlingshotScanner` | MA Cross | Reclaim (UP) or breakdown (DOWN) of the 20-period Moving Average. |
| **MIN** | `MinOneScanner` | Wick Detection | Detects "Liar's Wicks" — wick length > 2× body in the first 60s candle. Active 60–130s. |
| **LIQ** | `LiquidityVacuumScanner` | Sweep Reversal | Price sweeps below swing low (grabbing liquidity) then breaks structure upward. |
| **COB** | `CobraScanner` | Volatility Breakout | Explosive move outside 2-sigma Bollinger Bands on 60m candles. Active ≤180s. |
| **MES** | `MesaCollapseScanner` | Distribution Break | Flat/choppy top ("mesa") with ≥3 MA crosses collapses below its floor. |
| **MEA** | `MeanReversionScanner` | BB Rejection | Rejection from upper Bollinger Band toward mean. Requires 4H trend ≠ UP. |
| **GRI** | `GrindSnapScanner` | Exhaustion Snap | Tight 2-minute grind followed by a sharp impulse (>60% of grind). Active >130s. |
| **VOL** | `VolCheckScanner` | Volatility Confirm | Move distance > average 3-minute range. Active in final 100–290s. Requires 85–90¢ on one side. |
| **MOS** | `MosheSpecializedScanner` | High Probability | 3-point time/diff curve interpolation. Fires when a side reaches ≥86¢. Configurable bet size and curve points. Previously 'Moshe Sniper'. |
| **ZSC** | `ZScoreBreakoutScanner` | Statistical | Z-score >3.5 deviation from window mean + breakout of prior range. Active >220s. |

### Scanner Weights
Each scanner has a configurable **weight multiplier** (default 1.0×) stored in `v5_settings.json`. Historically strong scanners default higher:
- **COB** (Cobra): 1.67×
- **LIQ** (Liquidity): 1.67×
- **LAT** (Late Reversal): 1.67×

Click any scanner label in the UI to open its settings modal (weight, mode, thresholds).

### Deprecated Scanners
Scanners marked with `~` in the UI (GRI, MID, MIN) are considered deprecated but still functional.

---

## 6. Risk Management

### 6.1 Bet Sizing Pipeline (`risk.py`)

```
Base = RiskBankroll × 12%
  → Halved if betting against 4H macro trend
  → ×0.7 if 2+ consecutive losses on this scanner
  → ×0.5 for Fakeout scanner signals
  → Clamped to [MIN_BET=$5.50, MAX_BET=$100.00]
  → Multiplied by scanner weight (e.g., 1.67× for COB)
  → Whale Protect cap: max 25% of bankroll (if enabled)
```

### 6.2 Bankroll Modes

| Mode | Bankroll Calculation |
|---|---|
| **SIM** | Bankroll = full starting balance. Clamped to `target_bankroll` (cannot grow beyond initial). |
| **LIVE** | Bankroll = wallet balance ÷ 8 (`LIVE_RISK_DIVISOR`). Target compounds with wins. Always capped by actual wallet balance. |

### 6.3 Revenue Compounding
After each TP/SL sell or window settlement, realized revenue is added back to `risk_bankroll`:
- **SIM**: Hard-clamped at `target_bankroll` (prevents artificial growth)
- **LIVE**: `target_bankroll` grows with wins for compounding. Always capped by actual wallet balance via API query.

### 6.4 Bankroll Exhaustion Guard
After each settlement, if a bet was placed this window (confirmed loss) AND bankroll < max(Bet $, $1.00 hard floor):
- Final CSV snapshot is written
- Final `═══ FINAL LOG ═══` line appended to console log
- All market fetching and scanning stops
- Full-screen **BOT FROZEN** modal appears
- Bot stays halted until restart

---

## 7. Order Execution (`broker.py`)

### 7.1 Simulation
- `SimBroker.buy()` — deducts USD from balance, credits `shares[side]`, logs `TRADE_EVENT`
- `SimBroker.sell()` — calculates `revenue = shares × price`, credits balance
- `SimBroker.settle_window()` — winning shares settle at $1.00/share, net PnL logged

### 7.2 Live Polymarket
- All orders placed as **limit orders at $0.99** — ensures immediate fill as taker orders while bypassing Polymarket's 5-share minimum rule for small buys
- `LiveBroker.buy()` — creates `OrderArgs(price=0.99, size=amount/price, side="BUY")`, posts via `ClobClient`. Actual cost refined from `takingAmount` if plausible (≥10% of sent amount).
- `LiveBroker.sell()` — queries exact token balance from Polymarket, sells entire position. Resting limit at specified price (or $0.99 for last-second exits).
- Each 5-minute window has unique UP and DOWN token IDs, so positions cannot cross windows.

### 7.3 Pre-Buy System
Pre-buy shares are held in a separate buffer (`pre_buy_shares`, `pre_buy_invested`) and **promoted** to the active window at the start of the next cycle via `promote_prebuy()`.

---

## 8. MOM Expert Mode (v5.9)

The Momentum scanner supports four exclusive buy modes:

| Mode | Code | Behaviour |
|---|---|---|
| **Standard** | STD | Basic threshold/time signals |
| **Pre-Buy** | PRE | Anticipatory entry at −15s based on next-window demand |
| **Hybrid** | HBR | Pre-Buy on ≥3¢ gaps; Standard for small gaps |
| **Expert** | ADV | ATR-based dynamic tiering with Whale Shield |

### ATR Tier System (ADV Mode)
- **Stable Tier** (ATR ≤ `atr_low`, default 20): Offset threshold by −5¢ (easier entry)
- **Normal Tier** (ATR between bounds): No offset
- **Chaos Tier** (ATR ≥ `atr_high`, default 40): Offset threshold by +10¢ (harder entry)
- Auto-switches: `auto_stn_chaos` forces Standard in Chaos; `auto_pbn_stable` forces Pre-Buy in Stable

### Whale Shield (ADV Mode)
Emergency exit in the final seconds if the UP price stays within `shield_reach` (default 5¢) of the 50¢ neutral zone. Triggers at `shield_time` (default 45s) remaining.

### Pre-Buy Decision Priority
1. **Velocity Reversion** — BTC moved ≥$300 down in 60s → bet UP (mean reversion)
2. **RSI Momentum** — RSI > 70 + uptrend/sideways → bet UP (trend continuation)
3. **Price Gap** — ≥3¢ gap → follow leader; <3¢ gap → context-dependent (trend, ATR, RSI)

---

## 9. TP / SL Logic

| Trigger | Condition | Action |
|---|---|---|
| **Max Profit** | Price ≥ 99¢ | Immediate sell |
| **Take Profit** | Price ≥ TP% setting (default 95¢) | Sell |
| **Stop Loss** | ROI ≤ −SL% (default −40%) | Sell |
| **Clearly Lost** | Final-second bid < 10¢ | Skip sell, let expire worthless |

TP is a **price threshold** (binary options cap at $1.00, so ROI-based TP from a 62¢ entry would require 111¢ — unreachable). SL is **ROI-based** (percentage loss from entry price).

### SL+ Recovery Mode
Enabled by default (`sl+` command). On SL hit with realized loss > 0:
- Places a counter-trade on the **opposite side** for the same dollar amount at the current price
- Capped so at least $1.00 remains in bankroll
- Minimum recovery size: $0.10
- **Never chains** — recovery bets (prefixed `SL+_Recovery`) cannot trigger further recoveries

---

## 10. Last-Second Exits & Settlement

### 10.1 Last-Second Exit (T−1s)
At exactly 1 second remaining:
- **LIVE**: Resting limit sell at $0.99 for all open winning positions
- **SIM**: Hypothetical logging only — calculates what a live sell would yield

### 10.2 Window Settlement (T−0s)
1. **Winner determination** — Poly-Decisive logic: if either side's bid ≥ 90¢, that side wins regardless of BTC. Otherwise, UP if BTC ≥ Open, DOWN if BTC < Open.
2. **Sim settlement** — winning shares settle at $1.00/share, net PnL computed
3. **Live settlement refill** — winning unclosed positions refilled at $1.00/share
4. **Accuracy tracking** — session win count, total trades, accuracy percentage (starts at Window 2)
5. **Revenue compounding** — payout added back to risk bankroll
6. **Bankroll exhaustion check**
7. **MOM Analytics write** — one consolidated row per window to `lg/momentum_adv_*.csv`
8. **Reset** — `window_bets` cleared, scanners reset, price history cleared

### 10.3 Next Window Preview (T−20s)
At 20 seconds before window end, fetches the next window's UP/DOWN bid/ask prices and logs them.

---

## 11. Logging

### 11.1 Main Session CSV (`lg/sim_log_5M_*.csv`)
Snapshot rows logged every ~15 seconds (configurable via Global Settings modal). TRADE_EVENT rows interleaved on buy/sell/settle.

**Snapshot fields (26 columns):**

| Field | Description |
|---|---|
| `Timestamp` | Wall-clock time of snapshot |
| `SimBal` | Simulated wallet balance (USD) |
| `LiveBal` | Live Polymarket wallet balance (USD) |
| `RiskBankroll` | Current risk-adjusted bankroll available for bets (USD) |
| `TimeRem` | Time remaining in current 5-min window (MM:SS) |
| `BTC_Price` | Live BTC/USD price from Kraken WS / Binance fallback |
| `BTC_Open` | BTC price at window open (Kraken REST) |
| `BTC_Diff` | BTC_Price minus BTC_Open (USD) |
| `BTC_Range` | Intra-window high−low price range (USD) |
| `Odds_Score` | Polymarket UP−DN bid skew in cents (+ve = UP favoured) |
| `Trend_4H` | 4-hour macro trend (S-UP / M-UP / W-UP / NEUTRAL / W-DOWN / M-DOWN / S-DOWN) |
| `Trend_1H` | 1-hour trend direction (same scale) |
| `RSI_1m` | 14-period RSI on 1-minute Binance candles |
| `ATR_5m` | 5-period Average True Range on 1-minute candles (USD) |
| `Sig_Slingshot` | Slingshot scanner signal (WAIT / OFF / BET_UP / BET_DOWN) |
| `Sig_Cobra` | Cobra scanner signal |
| `Sig_Flag` | BullFlag scanner signal |
| `Master_Score` | Net scanner consensus: (# UP signals) − (# DOWN signals) |
| `Master_Status` | Aggregate direction: BUY_UP / BUY_DN / NEUTRAL |
| `Active_Scanners` | Count of scanners firing a BET signal this tick |
| `UP_Price` | Polymarket UP option midpoint price |
| `DN_Price` | Polymarket DOWN option midpoint price |
| `UP_Bid` | Polymarket UP option best bid |
| `DN_Bid` | Polymarket DOWN option best bid |
| `Shares_UP` | Current UP shares held |
| `Shares_DN` | Current DOWN shares held |

**TRADE_EVENT fields (interleaved rows):**

```
TRADE_EVENT,Time,Type,Side,Amount,ExecPrice,SigPrice,Slippage,Shares,RSI,Trend,RiskBal,MainBal,Note
```

### 11.2 Console Log (`lg/*_console.txt`)
ASCII-scrubbed mirror of the Rich TUI log output. All Rich markup tags and non-ASCII characters (emojis) are stripped. Each line prefixed with `[HH:MM:SS]`.

### 11.3 MOM Analytics Log (`lg/momentum_adv_*.csv`)
One consolidated row per 5-minute window, written at settlement. Fields:

| Category | Fields |
|---|---|
| **Timing** | `Window_ID` (start_ts), `Winner` (UP/DOWN) |
| **Pre-Window** | `BTC_Pre_15s`, `BTC_Pre_60s`, `Pre_15s_Gap`, `BTC_Velocity_60s` |
| **Early Open** | `Gap_5s`, `BTC_5s`, `Gap_10s`, `BTC_10s`, `Gap_15s`, `BTC_15s` |
| **Entry Depth** | `UP_Bid_15s`, `DN_Bid_15s`, `Poly_Spread_15s` |
| **Milestones** | `First_55c_Side/Time`, `First_60c_Side/Time`, `First_65c_Side/Time` |
| **Volume/RSI** | `RSI_1m`, `V_1m` (1-minute BTC volume) |
| **Drawdown** | `Drawdown_UP` (Open − Window_Low), `Drawdown_DN` (Window_High − Open) |
| **Structure** | `ATR_5m`, `BTC_Open`, `BTC_Close` |

---

## 12. UI Layout

### 12.1 Top Bar
- **Mode + Balance** — `5-SIM | Bal: $100.00 (B.R.: $100.00)` or `5-LIVE | Bal: $94.74`
- **RUN** — session uptime `HH:MM:SS`
- **WIN** — time remaining in current window `MM:SS`

### 12.2 Price Cards
- **BTC Card** (large, left) — Live price, Open, Diff, 1H Trend, ATR 5m
- **UP/DN Cards** (right column) — Current ask prices in cents

### 12.3 Settings Row 1

| Field | ID | Default | Description |
|---|---|---|---|
| Bet $ | `inp_amount` | 1.00 | Fixed amount per trade (used by MOM and manual buys) |
| Bankroll | `inp_risk_alloc` | (auto) | Risk bankroll cap. Auto-set from balance. |
| TP % | `inp_tp` | 95 | Take Profit price threshold (95 = sell at 95¢) |
| SL % | `inp_sl` | 40 | Stop Loss ROI threshold (40 = sell when down 40%) |

### 12.4 Settings Row 2

| Field | ID | Default | Description |
|---|---|---|---|
| Sim Bal | `inp_sim_bal` | (auto) | Display-only sim balance |
| Min Diff | `inp_min_diff` | 0 | Minimum BTC price move from open before entering |
| Min Price | `inp_min_price` | 0.55 | Minimum option ask price to execute (below → pending queue) |
| Max Price | `inp_max_price` | 0.80 | Maximum option ask price to execute (above → skip) |

### 12.5 Action Buttons
- **BUY UP / BUY DN** — immediate manual buy at current ask
- **SELL UP / SELL DN** — immediate sell of current position (shows dollar value when holding)

### 12.6 Scanner Grid
5 rows × 5 columns of scanner checkboxes. Each has:
- **Checkbox** — enable/disable the scanner
- **Label** (3-letter code) — click to open settings modal. Blinks yellow when a pending bet is queued.
- **ALL / NONE** buttons — bulk toggle

### 12.7 Control Row

| Control | Description |
|---|---|
| **TP/SL** checkbox | Enables automatic Take Profit and Stop Loss monitoring |
| **Strong Only** checkbox | Restricts to Strong-signal scanners only |
| **1 Trade Max** checkbox | Only one active position allowed per window |
| **Whale Protect** checkbox | Caps individual bets at 25% of bankroll |

### 12.8 Live Row
- **LIVE MODE** checkbox — switches from simulation to live Polymarket execution. Auto-deselects all scanners for safety.
- **Command Box** — admin commands (see below)
- **Settings Button** — opens Global Settings modal

### 12.9 Log Window
Full-height `RichLog` with color-coded output:
- **Blue** (ADMIN) — system events, window transitions
- **Gray** (SCAN) — scanner skip/queue messages
- **Green** (TRADE) — buy executions, profits
- **Red** — losses, errors, failures
- **Gold** (MONEY) — TP/SL hits, revenue events

---

## 13. Commands

Type in the command box and press Enter:

| Command | Effect |
|---|---|
| `sl+` | Enable SL+ Recovery Mode |
| `sl-` | Disable SL+ Recovery Mode |
| `lo=false` | Cancel mid-window lockout (force enable trading) |

---

## 14. Configuration Constants (`config.py`)

| Constant | Value | Description |
|---|---|---|
| `WINDOW_SECONDS` | 300 | 5-minute window duration |
| `LOG_INTERVAL` | 15 | Default CSV snapshot frequency (seconds) |
| `PHASE1_DURATION` | 60 | Standard impulse phase for scanners (seconds) |
| `DEFAULT_RISK_PCT` | 0.12 | Base bet = 12% of bankroll |
| `STRONG_RISK_PCT` | 0.20 | Strong-signal bet = 20% of bankroll |
| `MIN_BET` | 5.50 | Minimum bet size (USD) |
| `MAX_BET_SESSION_CAP` | 100.00 | Maximum single bet (USD) |
| `LIVE_RISK_DIVISOR` | 8 | Live bankroll = wallet ÷ 8 |
| `TOLERANCE_PCT` | 0.002 | Price tolerance for pattern matching (0.2%) |

---

## 15. Persistent Settings (`v5_settings.json`)

Auto-saved on every UI change and restored on next startup:

```json
{
    "scanner_weights": { "NPA": 1.0, "COB": 1.67, ... },
    "inp_amount": "1.00",
    "inp_tp": "95",
    "inp_sl": "40",
    "inp_min_diff": "0",
    "inp_min_price": "0.55",
    "inp_max_price": "0.80",
    "cb_tp_active": true,
    "cb_one_trade": false,
    "sl_plus_mode": true,
    "mom_buy_mode": "STD"
}
```

---

## 16. Data Sources & Fallback Chain

| Data | Primary | Secondary | Tertiary |
|---|---|---|---|
| **BTC Price** | Kraken WebSocket (`wss://ws.kraken.com/`) | Chainlink Oracle (Polygon) | Binance REST API |
| **BTC Open** | Kraken REST OHLC (1m candle at window start) | Price history first entry | — |
| **Candles (60m)** | Binance REST (`/api/v3/klines`, 200 × 1m) | — | — |
| **4H Trend** | Binance REST (10 × 4h candles, SMA crossover) | — | Cached 15 min |
| **1H Trend** | Binance REST (12 × 1h candles, SMA crossover) | — | Cached 15 min |
| **Polymarket Prices** | Gamma API (slug→token IDs) + CLOB API (bid/ask) | — | Default 50¢/50¢ |

### Trend Strength Scale
Computed from `(short_SMA / long_SMA − 1) × 100`:

| 4H Threshold | 1H Threshold | Label |
|---|---|---|
| ≥ 0.5% | ≥ 0.3% | `S-UP` (Strong UP) |
| ≥ 0.2% | ≥ 0.15% | `M-UP` (Medium UP) |
| ≥ 0.05% | ≥ 0.05% | `W-UP` (Weak UP) |
| −0.05% to +0.05% | same | `NEUTRAL` |
| ≤ −0.05% | ≤ −0.05% | `W-DOWN` |
| ≤ −0.2% | ≤ −0.15% | `M-DOWN` |
| ≤ −0.5% | ≤ −0.3% | `S-DOWN` |

---

## 17. Web3 & Blockchain

- **Polygon RPC** — rotates through a list of 5 endpoints until one connects
- **Chainlink BTC/USD Oracle** — contract `0xc907E116054Ad103354f2D350FD2514433D57F6f` on Polygon, ABI with single `latestAnswer()` view function
- **Polymarket CLOB** — orders posted via `py_clob_client` with signature type 0 (direct) or 1 (proxy/delegated)
- Web3 initialization runs in a background thread (`@work(exclusive=True, thread=True)`) to avoid blocking the UI

---

## 18. Development History

| Version | Highlights |
|---|---|
| **v5.0** | Base architecture — 20 scanners, sim/live broker, pending order queue |
| **v5.8** | Accurate accuracy displays (starts Window 2), Esc key dismissal, log event serialization |
| **v5.9** | MOM Expert overhaul — ATR tiering, Whale Shield, 2×2 mode grid |
| **v5.9.1** | Pre-Buy logic refinement, velocity reversion, RSI momentum |
| **v5.9.2** | BullFlag configurable settings modal, research logging |
| **v5.9.3** | Scanner loop refactor — persistent `base_threshold` state, background error fix |
| **v5.9.4** | MOM Analytics log, CSV log overhaul (26 live fields, descriptive headers), 1H trend |
| **v5.9.5** | **Major Feature Release:** Advanced scanner configuration modals, global skepticism filters, BriefingScanner, enhanced MOM/MM2 with Select widgets, safe UI thread calls, per-scanner whale shield, HDO threshold settings fix |

### v5.9.5 Technical Deep Dive

**Scanner Architecture Refactor:**
- All scanner classes now accept constructor parameters for configuration
- Settings persistence moved from UI element access to scanner object attributes
- Defensive error handling added throughout modal initialization
- Individual `adv_settings` dictionaries per scanner type

**UI/UX Enhancements:**
- 20+ new configuration modals with Select widgets and dynamic explanations
- Mode explanations update in real-time when settings change
- Enhanced briefing display with comprehensive market analysis
- Safe UI thread wrapper prevents shutdown crashes

**Risk Management Improvements:**
- Global skepticism filters automatically apply premium adjustments
- Per-scanner whale shield configuration with independent timing
- Enhanced HDO threshold persistence (KeyError fix)
- Improved settings loading with defensive error handling

**New Scanner: BriefingScanner**
- Automated macroscopic window analysis at T-05:00
- 8-factor directional prediction system
- Market microstructure analysis and volatility assessment
- Integrated with global skepticism filtering

**Bug Fixes & Stability:**
- Fixed KeyError 'inp_hdo_thresh' in settings loading
- Added comprehensive error handling for UI element access
- Fixed duplicate window_bets initialization in RiskManager
- Enhanced thread safety for background UI updates

### Major Architecture Refactor (Latest)
The original monolithic `app.py` (2,556 lines) was split into three focused modules:
- **`app.py`** (58,658 bytes) — Core PulseApp class with UI, event handlers, settings management
- **`trade_engine.py`** (72,950 bytes) — TradeEngineMixin with all trade execution, settlement, TP/SL logic
- **`ui_modals.py`** (59,874 bytes) — All modal classes and screens (GlobalSettings, AlgoInfo, MOMExpert, etc.)

### Recent Git History
- **v5.9.5** - Major feature release: Advanced scanner configuration, global skepticism, BriefingScanner
- **0cd0dd0** - Fix modal bugs and standardize log paths
- **29c82c5** - Major refactor: Split monolithic app.py into 3 modules
- **38b4bb6** - Pre-refactor checkpoint with BullFlag modal fixes
- **c995a4f** - v5.9.4: Advanced Momentum Analytics with comprehensive logging

### Code Quality Metrics
- **Total Python code**: ~274KB across 8 core modules
- **Documentation**: 28K+ line comprehensive README with full API reference
- **Test coverage**: Extensive logging system for debugging and optimization
- **Error handling**: Bankroll exhaustion protection, modal bug fixes, path standardization
- **State persistence**: JSON-based settings with session restoration

---

## 19. System Architecture Overview

### Enterprise-Level Features
- **Modular architecture** with clear separation of concerns
- **Professional logging infrastructure** with CSV analytics and console output
- **Risk management system** with dynamic bet sizing and exhaustion protection
- **Real-time market data** from multiple sources (Kraken, Binance, Chainlink, Polymarket)
- **Advanced UI/UX** with Textual TUI and modal configuration system
- **Persistent configuration** with JSON-based settings management

### Development Quality
- **Iterative AI-assisted development** through multiple enhancement cycles
- **Comprehensive error handling** and safety mechanisms
- **Performance optimization** with parallel data fetching and efficient scanner loops
- **Maintainable codebase** with clear module boundaries and documentation
- **Production-ready** with live trading capabilities and risk controls

---

## 21. v5.9.5 Technical Notes & Troubleshooting

### 21.1 Settings Persistence Changes

**HDO Threshold Fix:**
- **Problem:** KeyError 'inp_hdo_thresh' during settings loading
- **Solution:** Moved threshold storage from UI element to scanner object
- **Implementation:** `hdo_scanner.trigger_threshold` instead of UI field access
- **Settings Key:** `"hdo_threshold"` (not `"inp_hdo_thresh"`)

**Scanner Configuration Storage:**
```json
{
    "hdo_threshold": 0.59,
    "cco_settings": {
        "thresh": 0.25,
        "history": 60,
        "recent": 10
    },
    "mom_adv_settings": {
        "atr_low": 20,
        "atr_high": 40,
        "shield_time": 45,
        "shield_reach": 5
    },
    "nit_settings": { /* NPatternScanner params */ },
    "vsn_settings": { /* VolCheckScanner params */ }
}
```

### 21.2 UI Thread Safety

**Background Thread UI Updates:**
- All background thread calls to UI now use `safe_call()`
- Prevents RuntimeError during app shutdown
- Example usage:
```python
# Old (crashes on shutdown):
self.call_from_thread(self.log_msg, "message")

# New (safe):
self.safe_call(self.log_msg, "message")
```

### 21.3 Modal Initialization Order

**Defensive UI Element Access:**
```python
def on_mount(self):
    # Scanner settings loading with error handling
    try:
        self.query_one("#inp_hdo_thresh").value = str(int(hdo.trigger_threshold * 100))
    except:
        pass  # UI element might not be ready yet
```

### 21.4 Global Skepticism Filter Logic

**Filter Application Order:**
1. **Max Price Check** - Hard bound (except Moshe scanner)
2. **Odds Conflict** - Apply premium when odds favor opposite side
3. **Guess Conflict** - Apply premium when briefing conflicts with signal
4. **Final Price Validation** - Check against adjusted minimum

**Premium Calculation:**
```python
# Example: UP signal with odds conflict
base_min_price = 0.55
odds_conflict_premium = 0.05  # 5¢
effective_min = 0.60  # Must be ≥60¢ to execute
```

### 21.5 BriefingScanner Integration

**Automatic Execution:**
- Runs at T-05:00 (window start)
- Results stored in `market_data["net_guess_score"]`
- Used by global skepticism filter for guess conflicts
- Output displayed in main log window

**Scoring Factors:**
- Trend alignment (±2 points)
- RSI positioning (±1 point)
- Odds bias (±2 points)
- Ask imbalance (±1 point)
- BTC velocity (±1 point)
- Volatility regime (±0.5 points)

### 21.6 Whale Shield Per-Scanner Configuration

**Independent Settings:**
Each Momentum/MM2 scanner has separate `adv_settings`:
```python
adv_settings = {
    "shield_time": 45,    # Seconds remaining to activate
    "shield_reach": 5,   # Distance from 50¢ in cents
    "atr_low": 20,        # ATR tier thresholds
    "atr_high": 40
}
```

**Activation Logic:**
```python
if time_remaining <= shield_time and abs(price - 0.50) < shield_reach/100:
    # Emergency sell all positions
```

---

## 22. Future Roadmap

- **Multi-Scanner Expert Tiering** — apply ATR-based Gateway logic to Cobra, RSI, etc.
- **Dynamic Bet Scaling** — auto-increase bet size in Stable tiers, reduce in Chaos
- **Global Whale Shield** — monitor all open positions (not just MOM) for flip-risk near 50¢
- **Historical Gap Guard** — data-validation on boot to prevent phantom signals from stale data
