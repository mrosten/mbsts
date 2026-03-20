# HTML Verification Log — Improvement Recommendations
_Generated: 2026-03-19 20:17_

---

## 🔧 Structural Improvements

### 1. Session Summary Header *(High Priority)*
Add a stats bar at the top showing:
- Total trades, Win rate, Net PnL, Session duration

Currently you have to scan the whole table manually to get a sense of performance.

### 2. Row Color-Coding by Result
| Result | Style |
|---|---|
| WIN | Subtle green row tint |
| LOSS | Red row tint |
| PUSH / no-trade | Neutral |

Currently only `discrepancy` (mismatch) gets color treatment.

### 3. Collapse "Algorithms Fired" Sub-Row
The separate `<tr>` below each trade doubles table height. Move it to a small inline line or a `▼` expand toggle inside the main row.

### 4. Sticky Table Header
```css
thead { position: sticky; top: 0; }
```
Column names should stay visible when scrolling many rows.

---

## 📊 Chart / Graph Improvements

### 5. Per-Session PnL Equity Curve *(High Priority)*
A Chart.js or plain SVG equity curve at the top of the page:
- One dot per trade window
- Cumulative PnL over time
- Most useful addition for session review

### 6. Algorithm Breakdown Bar Chart *(Optional)*
Small SVG or canvas showing **wins vs losses grouped by algorithm** (MOM, MM2, NIT, etc.).
Great for spotting which scanner is dragging performance.

### 7. SVG Lightbox on Click
Trade window graphs should go **full-screen on click** (lightbox modal) rather than just CSS scale — the current zoom is too small for detail review.

---

## 🛠️ Functional Improvements

### 8. Sortable Columns
Basic JavaScript `onclick` column sorting so you can sort by PnL, algorithm, or result.

### 9. Relative Timestamps
Show `"5m ago"` / `"2h ago"` next to timestamp using JavaScript — useful when reviewing mid-session.

---

## 🏆 Top 3 Recommendations (Ranked)

| Priority | Feature | Impact |
|---|---|---|
| 🥇 | Session summary stats bar (trades, win rate, net PnL) | Instant session overview |
| 🥈 | Cumulative PnL equity curve chart | Critical for performance review |
| 🥉 | Sticky header + WIN/LOSS row color coding | Usability |
