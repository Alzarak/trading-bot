# Risk Rules Reference

This document defines all risk parameters, safety constraints, and enforcement logic for the trading bot. All values in this document correspond to config.json fields. Trading scripts must enforce every rule deterministically — no exceptions.

---

## Circuit Breaker

**Purpose:** Halt all trading when daily losses reach the configured threshold.

**Trigger:** `(start_equity - current_equity) / start_equity * 100 >= max_daily_loss_pct`

**Defaults by risk tolerance:**
| Risk Tolerance | `max_daily_loss_pct` |
|---------------|----------------------|
| conservative  | 2%                   |
| moderate      | 3%                   |
| aggressive    | 5%                   |

**Enforcement:**
- Calculate `start_equity` at market open (9:30 AM ET) using `client.get_account().equity`
- Check circuit breaker status before processing every signal
- When triggered: cancel all open orders, halt signal processing, log the event with equity values
- Manual restart required — the bot does NOT auto-resume after circuit breaker triggers
- Restart resets the `start_equity` baseline for the new session

---

## Position Sizing

**Purpose:** Limit capital exposure per trade.

**Formula:**
```
position_value = equity * (max_position_pct / 100)
shares = floor(position_value / current_price)
```

**Defaults by risk tolerance:**
| Risk Tolerance | `max_position_pct` |
|---------------|---------------------|
| conservative  | 5%                  |
| moderate      | 10%                 |
| aggressive    | 15%                 |

**Enforcement:**
- Reject position if calculated `shares < 1` (position too small for current price)
- Reject if `position_value > budget_usd` (enforce budget cap from config)
- Reject if adding position would exceed `max_positions` concurrent positions
- Default `max_positions`: 10 (configurable down, never up past 10 in v1)

---

## Stop-Loss Rules

**Purpose:** Every position must have a defined exit if the trade goes against us.

**Requirement:** Every order MUST have a stop-loss. No naked positions allowed.

**ATR-based stop formula:**
```
stop_price = entry_price - (ATR * multiplier)
```

**Defaults by risk tolerance:**
| Risk Tolerance | ATR Multiplier |
|---------------|----------------|
| conservative  | 1.5x           |
| moderate      | 1.25x          |
| aggressive    | 1.0x           |

**Minimum stop distance:** 0.5% of entry price (hard floor regardless of ATR result)

**Implementation:**
- Use bracket orders (`OrderClass.BRACKET`) when possible — stop-loss and take-profit submitted atomically
- If bracket order not available: submit stop-loss order immediately after fill confirmation
- Trailing stops: trail distance = `ATR * multiplier` (recalculate on each bar)
- Never move a stop-loss further from entry (widening stops in a loss is forbidden)

---

## PDT Protection

**Purpose:** Prevent Pattern Day Trader rule violations for accounts under $25,000.

**Rule:** Maximum 3 day trades per rolling 5-business-day window (accounts < $25K equity).

**Definition:** A day trade = opening and closing a position in the same security on the same calendar day.

**Enforcement:**
- Track day trade count in SQLite state table (`day_trades` table with timestamp and symbol)
- Query count of day trades in last 5 business days before each potential entry
- At count == 2: warn in log and (if `autonomy_mode == "claude_decides"`) notify Claude
- At count >= 3: block the trade with hard rejection — no exceptions
- PDT check applies to both paper and live accounts on Alpaca

---

## Maximum Position Count

**Purpose:** Limit portfolio concentration and cognitive load.

**Default:** `max_positions = 10`

**Enforcement:**
- Count open positions via `client.get_all_positions()` before each new entry
- Block new entry if `len(open_positions) >= max_positions`
- `max_positions` is configurable via config.json (always <= 10 in v1)

---

## Order Safety

**Purpose:** Prevent duplicate orders, ghost positions, and cascading failures.

**Idempotency:**
- Every order submission includes `client_order_id = str(uuid.uuid4())`
- Before retrying a failed order, check if a position already exists for the symbol
- If position exists (order may have been filled before the error): skip retry

**Retry logic:**
```
Attempt 1: submit immediately
Attempt 2: wait 1s, retry
Attempt 3: wait 2s, retry
Attempt 4: wait 4s, retry
Attempt 5: wait 8s, retry
After 5 attempts: log failure, skip trade, continue loop
```

**Skip retry on:**
- HTTP 422 (validation error) — malformed request, retrying will not help
- HTTP 403 (forbidden) — auth issue, retrying will not help
- Position already exists for the symbol (ghost position prevention)

**Ghost position prevention:**
- After any order failure, verify position state via `client.get_open_position(symbol)`
- If position exists despite error response: treat as successful, log the discrepancy
- Never submit a second order for a symbol that already has an open position

---

## Signal Aggressiveness

**Purpose:** Control signal sensitivity — how many weighted conditions must align before the bot considers a setup tradeable.

**Important:** Aggressiveness controls ONLY signal sensitivity. It does NOT change risk exposure — position sizing, daily loss limits, circuit breaker, PDT, and stop-loss rules remain unchanged regardless of aggressiveness level.

| Level | `confidence_threshold` | Behavior |
|-------|----------------------|----------|
| conservative | 0.6 | Most conditions must align — fewer trades, higher quality |
| moderate | 0.45 | Trades on reasonable setups — balanced frequency and quality |
| aggressive | 0.3 | Trades on partial signals — more trades, some marginal |

**Enforcement:** Applied in `bot.py` `scan_and_trade()` (strategy pipeline) and `ClaudeAnalyzer.parse_response()` (Claude pipeline). Both use the same `confidence_threshold` from `config.json`.

**Config fields:**
- `signal_aggressiveness`: `"conservative"` | `"moderate"` | `"aggressive"`
- `confidence_threshold`: `0.6` | `0.45` | `0.3`

---

## Autonomy Modes

**Purpose:** Control how much discretion Claude has vs deterministic config values.

### `fixed_params` Mode

- All trading parameters are taken exactly from config.json values
- Position size = exactly `max_position_pct` % of equity (no deviation)
- Entry threshold = exactly the strategy's configured threshold (no deviation)
- Stop-loss = exactly `ATR * multiplier` (no deviation)
- Claude's analysis is informational only — it does not affect execution parameters

### `claude_decides` Mode

- Claude analyzes each opportunity and may adjust parameters within bounds:
  - Position size: 50%–150% of configured `max_position_pct` (e.g., 50%–150% of 5% = 2.5%–7.5%)
  - Entry threshold: may be tightened (higher confidence required), never loosened
  - Stop-loss: may be widened (more room given), never tightened
- Claude must provide structured JSON with: adjusted parameters + explicit reasoning for each adjustment
- All Claude adjustments are audit-logged with the original config values and final values used
- Risk manager applies all other rules (circuit breaker, PDT, max positions) regardless of Claude's output
