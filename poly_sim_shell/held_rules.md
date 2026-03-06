# Held & Deferred Rules - mbsts_v5

This file serves as a permanent record of rules and features that are currently **ON HOLD** or **DEFERRED**. These should not be implemented until explicitly requested.

---

## 1. Strictly Enforced Bet Sizing & $1 Minimum (ON HOLD)

### Goal
Standardize all executed bets to be 12% of the **Global Risk Bankroll**, multiplied by the **Algorithm Weight**, with a strict **$1.00 floor**.

### Proposed Changes
- **config.py**: Set `MIN_BET = 1.00`.
- **risk.py**: Update `calculate_bet_size` to enforce $1.00 floor and use global bankroll.
- **app.py**: Ensure algorithm weights are applied before the $1.00 floor check.
- **Momentum Fix**: Force `MOM` to use global bankroll instead of sub-portfolio balance.

---

## 2. Testing Mode & Shorthand Language (DEFERRED)

### Testing Mode
- Constrain bets to $1-$3 for safe testing.
- Scale between $1.00 and $3.00 based on algorithm weight/confidence.

### Shorthand Language
- Quick setup via strings like `FAK:1.5, MOM:0.5`.
- Parser should selectively check boxes and apply weights based on the string.

---

## 3. MOMENTUM (MOM) BET SIZING TOGGLE (DEFERRED)
- Add a Checkbox to `MOMExpertModal` to toggle between "Use Fixed Bet $" and "Use 12% Bankroll".
- Persist the setting in `app.py`.
