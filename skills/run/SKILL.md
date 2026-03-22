---
name: run
description: "This skill should be used when the user runs /trading-bot:run, wants to start the trading loop, begin autonomous trading, or execute the bot in agent or standalone mode."
---

Start the autonomous trading bot. Follow steps in order.

## Pre-check

Verify config.json exists:

```bash
test -f "${CLAUDE_PLUGIN_DATA}/config.json" && echo "EXISTS" || echo "NOT_FOUND"
```

If NOT_FOUND: tell the user to run `/trading-bot:initialize` first. Stop.

Read the config to determine `watchlist`, `autonomy_mode`, and `strategies`.

## Mode Selection

If user's message includes "standalone" OR config has no `autonomy_mode`: run **STANDALONE MODE**.
Otherwise: run **AGENT MODE** (default).

---

## STANDALONE MODE

Verify standalone directory exists, then run:

```bash
cd "${CLAUDE_PLUGIN_DATA}/trading-bot-standalone" && python bot.py
```

If directory missing: tell user to run `/trading-bot:build` first.

---

## AGENT MODE

Run the trading loop within Claude Code. Act as the market analyst — analyze indicator data and produce JSON recommendations. The Python risk manager validates all signals before order execution.

**NEVER call Alpaca order APIs directly. All orders go through OrderExecutor and RiskManager.**

### Step 1 — Initialize Components

Load config, print watchlist and active strategies.

### Step 2 — Market Hours Check

Check if market is open via MarketScanner. If closed: ask user whether to continue (testing) or wait for market hours.

### Step 3 — Scan Indicators

For each watchlist symbol, use `MarketScanner.scan()` and `ClaudeAnalyzer.build_analysis_prompt()` to fetch indicator data and generate analysis prompts.

### Step 4 — Analyze Each Symbol

For each symbol's indicator data:

1. Read the indicator table carefully
2. Apply strategy analysis logic:
   - **momentum**: RSI extremes, MACD histogram direction, EMA crossovers
   - **mean_reversion**: Bollinger Band extremes, RSI reversals
   - **breakout**: Price breaking resistance with volume, ATR expansion
3. Return ClaudeRecommendation JSON:

```json
{
  "symbol": "AAPL",
  "action": "BUY",
  "confidence": 0.78,
  "reasoning": "explicit explanation",
  "strategy": "momentum",
  "atr": 1.45,
  "stop_price": 148.55
}
```

### Step 5 — Execute Signals

Parse recommendations through ClaudeAnalyzer, route valid signals through OrderExecutor:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" -c "
# ... parse and execute recommendations through risk manager
"
```

Replace placeholder with actual JSON recommendations from Step 4.

### Step 6 — Loop Control

Display scan cycle summary. Ask user to continue (scan again in 60s) or stop. If stopping, display final portfolio summary.

---

## Safety

- Paper trading by default — all configs use `paper_trading: true`
- Risk checks mandatory — OrderExecutor runs RiskManager before every order
- No direct Alpaca order calls — always route through OrderExecutor
- ClaudeAnalyzer bridges analysis to execution with consistent JSON validation
