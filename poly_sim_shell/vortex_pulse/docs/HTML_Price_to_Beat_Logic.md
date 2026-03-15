# HTML Price to Beat Verification Logic

## Purpose
To provide accurate price to beat verification for whale protection and PnL correction using Polymarket's official webpage data.

## Implementation Flow

### 1. T+30 Seconds (Store HTML Price to Beat)
- **When**: 30-35 seconds into each window
- **Action**: `store_html_price_to_beat(slug, elapsed)`
- **Purpose**: Store the more accurate HTML price to beat for documentation
- **Result**: Logs `📝 HTML PTB stored at T+30s: $XX,XXX.XX`

### 2. T+300 Seconds (Window End - Preliminary PnL)
- **When**: End of window (300 seconds)
- **Action**: Standard PnL calculation using exchange data (Binance/Kraken)
- **Purpose**: Initial PnL determination based on exchange prices
- **Result**: Preliminary PnL calculated

### 3. T+330 Seconds (Compare HTML Price to Beat)
- **When**: 330-335 seconds (30 seconds after window ends)
- **Action**: `compare_html_price_to_beat(slug, elapsed)`
- **Purpose**: Compare T+30 HTML price with T+330 HTML price
- **Result**: 
  - If changed: `⚠️ HTML PTB CHANGED: $XX,XXX.XX → $YY,YYY.YY`
  - If unchanged: `✅ HTML PTB unchanged: $XX,XXX.XX`

### 4. PnL Correction (If Direction Changed)
- **When**: Only if HTML price to beat changed between T+30 and T+330
- **Action**: Log discrepancy and trigger PnL correction
- **Purpose**: Correct PnL if whale manipulation affected the outcome
- **Result**: `PnL correction needed for window [slug]`

## Key Features

### Exchange vs HTML Price to Beat
- **Exchange PTB**: Used for trading decisions (stays active throughout window)
- **HTML PTB**: Used for verification/correction only (stored at T+30, compared at T+330)

### Caching System
- `_p2b_cache` stores: `{"t30_price": float, "t330_price": float, "timestamp": float}`
- Prevents repeated webpage scraping
- Tracks which windows have been verified

### Whale Protection
- HTML verification provides authoritative price data
- Detects last-minute price manipulation
- Ensures accurate PnL determination

## Integration Points

### MarketDataManager Methods
- `store_html_price_to_beat(slug, elapsed)` - Store T+30 HTML PTB
- `compare_html_price_to_beat(slug, elapsed)` - Compare T+30 vs T+330 HTML PTB
- `_extract_price_to_beat_from_web(slug)` - Extract PTB from webpage

### TradeEngine Integration
- T+30: Calls `store_html_price_to_beat()`
- T+330: Calls `compare_html_price_to_beat()`
- Logs changes and triggers PnL correction if needed

## Expected Console Output

```
📝 HTML PTB stored at T+30s: $70,077.61
🔍 HTML PTB comparison: T+30=$70,077.61 vs T+330=$70,100.23
⚠️ HTML PTB CHANGED: $70,077.61 → $70,100.23
PnL correction needed for window btc-updown-5m-1773313200
```

## Benefits
1. **Accuracy**: Uses official Polymarket data for verification
2. **Protection**: Detects whale manipulation in critical moments
3. **Documentation**: Stores accurate PTB for audit purposes
4. **Correction**: Allows PnL adjustment when discrepancies occur
5. **Efficiency**: Minimal webpage scraping (only 2x per window)
