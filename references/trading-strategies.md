# Trading Strategies Reference

This document describes all four strategies available in the trading bot. During `/initialize`, users select which strategies to enable. Each strategy runs independently with its own parameters and produces BUY/SELL/HOLD signals with a confidence score (0.0–1.0).

Strategy config names (used in `config.json` strategies array): `momentum`, `mean_reversion`, `breakout`, `vwap`

---

## Scoring System

All strategies use **weighted scoring** instead of binary all-or-nothing conditions. Each strategy defines a set of conditions, each contributing a weight to the total confidence score. This produces actionable signals in a wider range of market conditions while still requiring meaningful confirmation.

### How It Works

1. Each condition is evaluated independently and adds its weight to the score if met
2. Confidence = sum of met condition weights, capped at 1.0
3. **2-of-N gate**: At least 2 conditions must score > 0 for a BUY signal — this prevents single-indicator false signals
4. HOLD signals carry their partial score for transparency (e.g., 0.25 means 1 condition met)
5. The score is compared against the `confidence_threshold` from config (set during `/initialize`)

### Signal Aggressiveness

The `confidence_threshold` controls how many conditions must align before the bot acts. This is configured during `/initialize` and stored in `config.json`.

| Level | `confidence_threshold` | Behavior |
|-------|----------------------|----------|
| conservative | 0.6 | Most conditions must align — fewer trades, higher quality |
| moderate | 0.45 | Trades on reasonable setups — balanced frequency and quality |
| aggressive | 0.3 | Trades on partial signals — more trades, some marginal |

**Important:** Aggressiveness controls signal sensitivity only. Risk limits (position size, daily loss, circuit breaker, PDT) are unchanged regardless of aggressiveness level.

### Auto-Discovery

When `discovery_mode` is `auto` and `watchlist` is empty, the bot uses Alpaca's screener API to find the most actively traded stocks within the user's budget. It uses a two-tier hybrid approach: first finding stocks cheap enough to buy whole shares, then filling remaining slots with fractional-share-friendly stocks. The watchlist refreshes hourly.

### SELL Signal Scoring

- **Momentum and Breakout**: SELL signals use weighted scoring with a 2-of-N gate (same as BUY)
- **Mean Reversion and VWAP**: SELL signals remain binary — price returning to the mean/VWAP is a structural target, not a scored condition

---

## Momentum Strategy

**Config name:** `momentum`

Trades in the direction of an existing trend by identifying when short-term momentum aligns with medium-term direction. Best in trending markets with consistent volume.

### Signal Logic

Produces a BUY signal when upward momentum is confirmed by multiple weighted indicators. Produces a SELL signal (exit) when multiple reversal conditions align. HOLD when fewer than 2 conditions are met.

### Entry Conditions (BUY) — Weighted Scoring

| Condition | Weight | Description |
|-----------|--------|-------------|
| `rsi_recovering` | 0.25 | RSI < 45 AND rising (current > previous bar) |
| `rsi_oversold_bounce` | 0.10 | RSI crossed above 30 (bonus for classic oversold recovery) |
| `macd_h_positive` | 0.25 | MACD histogram > 0 |
| `macd_h_improving` | 0.10 | MACD histogram rising even if negative (partial credit) |
| `ema_bullish` | 0.25 | EMA short > EMA long |
| `high_volume` | 0.15 | Volume > 20-bar average |

Gate: at least 2 conditions must score > 0. Max possible score: 1.10 (capped at 1.0).

Note: `macd_h_positive` and `macd_h_improving` are mutually exclusive — only the higher-weight one applies.

### Exit Conditions (SELL) — Weighted Scoring

| Condition | Weight | Description |
|-----------|--------|-------------|
| `rsi_overbought` | 0.35 | RSI > 70 |
| `macd_h_negative` | 0.35 | MACD histogram < 0 |
| `ema_bearish` | 0.30 | EMA short < EMA long |

Gate: at least 2 conditions must score > 0. Stop-loss hit (ATR-based) always triggers exit.

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `rsi_period` | 14 | RSI lookback period (bars) |
| `macd_fast` | 12 | MACD fast EMA period |
| `macd_slow` | 26 | MACD slow EMA period |
| `macd_signal` | 9 | MACD signal line period |
| `ema_short` | 9 | Short EMA period for crossover |
| `ema_long` | 21 | Long EMA period for crossover |

---

## Mean Reversion Strategy

**Config name:** `mean_reversion`

Trades the assumption that price deviates temporarily from its mean and will revert. Best in range-bound, low-volatility markets. Underperforms during strong trends.

### Signal Logic

Produces a BUY signal when price is statistically oversold relative to its recent mean, scored by multiple conditions. Produces a SELL signal when price returns to the mean (binary). HOLD when fewer than 2 conditions are met.

### Entry Conditions (BUY — Long) — Weighted Scoring

| Condition | Weight | Description |
|-----------|--------|-------------|
| `near_lower_band` | 0.30 | Price within 3% of lower Bollinger Band |
| `at_lower_band` | 0.10 | Price at or below lower BB (bonus) |
| `rsi_weak` | 0.25 | RSI < 40 |
| `rsi_oversold` | 0.10 | RSI < 30 (bonus for strong oversold) |
| `price_below_middle` | 0.25 | Price below middle Bollinger Band |
| `volume_declining` | 0.10 | Volume below 20-bar average (sellers exhausted, optional) |

Gate: at least 2 conditions must score > 0.

### Exit Conditions (SELL) — Binary

- Price returns to the middle Bollinger Band (SMA 20 — the mean)
- Stop-loss hit (ATR-based, calculated at entry)

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `bb_period` | 20 | Bollinger Band SMA period |
| `bb_std_dev` | 2.0 | Standard deviations for band width |
| `rsi_period` | 14 | RSI lookback period |

---

## Breakout Strategy

**Config name:** `breakout`

Trades a price break above a significant resistance level, expecting continuation. Best in volatile markets with clear consolidation patterns followed by volume spikes.

### Signal Logic

Produces a BUY signal when price approaches or breaks the 20-period high with confirming indicators. Produces a SELL signal when the breakout fails (binary). HOLD when fewer than 2 conditions are met.

### Entry Conditions (BUY) — Weighted Scoring

| Condition | Weight | Description |
|-----------|--------|-------------|
| `new_high` | 0.35 | Price breaks above prior 20-bar high |
| `near_high` | 0.15 | Price within 1% of 20-bar high (partial credit, mutually exclusive with `new_high`) |
| `high_volume` | 0.25 | Volume > 1.5x 20-bar average |
| `elevated_volume` | 0.10 | Volume > 1.2x 20-bar average (partial credit, mutually exclusive with `high_volume`) |
| `atr_expanding` | 0.15 | ATR rising (current > previous bar — increasing volatility) |
| `macd_positive` | 0.10 | MACD histogram > 0 (optional — only scored if MACD column present) |

Gate: at least 2 conditions must score > 0.

### Exit Conditions (SELL) — Binary

- Price falls back below the 20-bar rolling high (breakout failure)
- Stop-loss hit (ATR-based, set below the pre-breakout consolidation range)

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `lookback_period` | 20 | Bars to look back for resistance high |
| `volume_multiplier` | 1.5 | Required volume ratio vs average |
| `atr_period` | 14 | ATR period for stop calculation |

---

## VWAP Reversion Strategy

**Config name:** `vwap`

Trades mean reversion relative to intraday VWAP (Volume Weighted Average Price). VWAP is the institutional benchmark — institutional buyers defend VWAP during the trading day. Best used mid-session when VWAP is well-established.

### Signal Logic

Produces a BUY signal when price drops below VWAP with confirming weakness indicators. Produces a SELL signal when price returns to VWAP (binary). HOLD when fewer than 2 conditions are met or outside the trading window.

### Entry Conditions (BUY — Long) — Weighted Scoring

| Condition | Weight | Description |
|-----------|--------|-------------|
| `below_vwap` | 0.30 | Price > 1.0% below VWAP |
| `deep_below_vwap` | 0.10 | Price > 1.5% below VWAP (bonus for strong deviation) |
| `rsi_weak` | 0.25 | RSI < 45 |
| `rsi_very_weak` | 0.10 | RSI < 35 (bonus for strong weakness) |
| `in_trading_window` | 0.20 | Between 10:00 AM and 3:00 PM ET |
| `volume_spike` | 0.15 | Volume > 20-bar average (optional) |

Gate: at least 2 conditions must score > 0.

### Exit Conditions (SELL) — Binary

- Price returns to VWAP (target reached — mean reversion achieved)
- Price moves beyond max_deviation_pct below VWAP (stop-loss — deviation becoming structural)

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `deviation_threshold_pct` | 1.5 | % below VWAP to trigger bonus entry weight |
| `rsi_period` | 14 | RSI lookback period |
| `max_deviation_pct` | 2.0 | % below VWAP for stop-loss |
| `trading_start_hour` | 10 | Earliest entry hour (ET, 24h) |
| `trading_end_hour` | 15 | Latest entry hour (ET, 24h) |
