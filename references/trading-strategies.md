# Trading Strategies Reference

This document describes all four strategies available in the trading bot. During `/initialize`, users select which strategies to enable. Each strategy runs independently with its own parameters and produces BUY/SELL/HOLD signals with a confidence score (0.0–1.0).

Strategy config names (used in `config.json` strategies array): `momentum`, `mean_reversion`, `breakout`, `vwap`

---

## Momentum Strategy

**Config name:** `momentum`

Trades in the direction of an existing trend by identifying when short-term momentum aligns with medium-term direction. Best in trending markets with consistent volume.

### Signal Logic

Produces a BUY signal when upward momentum is confirmed by multiple indicators. Produces a SELL signal (exit) when momentum reverses. HOLD when indicators are mixed or neutral.

### Entry Conditions (BUY)

- RSI crosses above 30 (recovering from oversold) AND MACD histogram turns positive
- EMA 9 crosses above EMA 21 (short-term average above medium-term)
- Current volume above 20-period average volume (confirms participation)
- All three conditions must be true simultaneously

### Exit Conditions (SELL)

- RSI crosses above 70 (overbought territory) OR MACD histogram turns negative
- EMA 9 crosses below EMA 21 (momentum reversal)
- Stop-loss hit (ATR-based, calculated at entry)

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

Produces a BUY signal when price is statistically oversold relative to its recent mean. Produces a SELL signal when price returns to the mean. HOLD when price is near the mean or trending strongly.

### Entry Conditions (BUY — Long)

- Price touches or crosses below the lower Bollinger Band (SMA 20, 2 standard deviations)
- RSI below 30 (confirms oversold condition, not just band touch)
- Price is within 2% of the lower band (avoids chasing extreme deviations)
- All three conditions must be true simultaneously

### Exit Conditions (SELL)

- Price returns to the middle Bollinger Band (SMA 20 — the mean)
- Stop-loss hit (ATR-based, calculated at entry)

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `bb_period` | 20 | Bollinger Band SMA period |
| `bb_std_dev` | 2.0 | Standard deviations for band width |
| `rsi_period` | 14 | RSI lookback period |
| `rsi_oversold` | 30 | RSI threshold for oversold entry |
| `rsi_overbought` | 70 | RSI threshold for overbought exit |

---

## Breakout Strategy

**Config name:** `breakout`

Trades a price break above a significant resistance level, expecting continuation. Best in volatile markets with clear consolidation patterns followed by volume spikes.

### Signal Logic

Produces a BUY signal when price breaks above the 20-period high with confirming volume. Produces a SELL signal when the breakout fails (price returns below the breakout level). HOLD during consolidation.

### Entry Conditions (BUY)

- Price breaks above the 20-period high (new N-bar high on current bar)
- Volume on breakout bar is > 1.5x the 20-period average volume (volume confirmation)
- ATR is expanding (current ATR > previous ATR — indicates increasing volatility at breakout)
- MACD is positive (overall trend is up)

### Exit Conditions (SELL)

- Price falls back below the breakout level (breakout failure)
- Volume drops for 3 consecutive bars below average (momentum exhaustion)
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

Produces a BUY signal when price drops significantly below VWAP (statistical overextension below institutional benchmark). Produces a SELL signal when price returns to VWAP. HOLD near VWAP or outside the active trading window.

### Entry Conditions (BUY — Long)

- Price drops more than 1.5% below VWAP (statistically significant deviation)
- RSI below 40 (confirms weakness, not just an early dip)
- Time is between 10:00 AM and 3:00 PM ET (VWAP is unreliable in first/last 30 minutes)

### Exit Conditions (SELL)

- Price returns to VWAP (target reached — mean reversion achieved)
- Price moves 2% further below VWAP (stop-loss — deviation becoming structural)

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `deviation_threshold_pct` | 1.5 | % below VWAP to trigger entry |
| `rsi_period` | 14 | RSI lookback period |
| `max_deviation_pct` | 2.0 | % below VWAP for stop-loss |
| `trading_start_hour` | 10 | Earliest entry hour (ET, 24h) |
| `trading_end_hour` | 15 | Latest entry hour (ET, 24h) |
