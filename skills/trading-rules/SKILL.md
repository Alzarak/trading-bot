---
name: trading-rules
description: "This skill should be used when the conversation involves trading decisions, risk management, strategy execution, order placement, market analysis, position sizing, PDT rules, or circuit breaker checks. Provides core trading rules and safety constraints."
---

## Core Trading Rules

These rules apply to ALL trading operations, regardless of strategy, autonomy mode, or experience level. No rule may be bypassed without explicit user action.

### Market Hours

- US stock market hours: 9:30 AM - 4:00 PM Eastern Time (Monday through Friday)
- Pre-market: 4:00 AM - 9:30 AM ET (not supported in v1)
- After-hours: 4:00 PM - 8:00 PM ET (not supported in v1)
- Use `zoneinfo.ZoneInfo("America/New_York")` for timezone handling (stdlib, no install required)
- Always check Alpaca market clock before submitting orders (`client.get_clock().is_open`)
- Never submit orders outside market hours unless `market_hours_only: false` is explicitly set in config

### Position Sizing

- Position size = `max_position_pct` of account equity (from config.json)
- Default by risk tolerance: 5% per position (conservative), 10% (moderate), 15% (aggressive)
- Maximum concurrent positions: 10 (hard limit, configurable down via `max_positions` config)
- Never risk more than `max_daily_loss_pct` of portfolio in a single day
- Formula: `position_value = equity * (max_position_pct / 100)`; `shares = floor(position_value / price)`
- Reject position if calculated shares < 1

### Pattern Day Trader (PDT) Rule

- Accounts under $25,000: max 3 day trades per rolling 5-business-day window
- A day trade = buying and selling the same security on the same calendar day
- Track day trade count in SQLite state; warn user when count reaches 2
- Block new entries when day trade count >= 3 (hard block, no exceptions)
- PDT applies to both paper and live accounts on Alpaca
- PDT count resets on a rolling 5-business-day basis, not calendar week

### Risk Controls

- Circuit breaker: halt ALL trading immediately when daily loss exceeds `max_daily_loss_pct`
- Circuit breaker requires manual restart — never auto-resume after trigger
- Every order MUST have a stop-loss (bracket order or explicit stop order — no naked positions)
- ATR-based stops: `stop_price = entry_price - (ATR * multiplier)` (default multiplier: 1.5x)
- Minimum stop distance: 0.5% of entry price (regardless of ATR calculation)
- No averaging down into losing positions under any autonomy mode
- Trailing stops trail by `ATR * multiplier` as price moves in favorable direction

### Alpaca API — Two Modes

The plugin supports two ways to interact with Alpaca, configured during `/trading-bot:initialize`:

**MCP mode** (`use_mcp: true` in config):
- Alpaca MCP server provides 44 tools directly to Claude (market data, positions, account info)
- Added via `claude mcp add alpaca` during setup — lives in the project's `.mcp.json`
- Use MCP tools for real-time queries during conversations (quotes, positions, account status)
- Order execution still goes through Python OrderExecutor — MCP is read-only for market data
- Paper trading is the default (`ALPACA_PAPER_TRADE` defaults to `True` in the MCP server)

**SDK-only mode** (`use_mcp: false` in config):
- All API calls go through the Python `alpaca-py` SDK via MarketScanner and OrderExecutor
- No MCP server configured — Claude cannot query Alpaca directly
- Do not attempt to call `mcp__alpaca__*` tools in this mode

**Common conventions (both modes):**
- Use `alpaca-py` SDK (not deprecated `alpaca-trade-api`)
- `TradingClient(api_key, secret_key, paper=True)` for paper trading (safe default)
- API keys loaded from environment variables via pydantic-settings — never hardcoded
- All API calls wrapped with exponential backoff retry: 1s / 2s / 4s / 8s, max 4 retries
- Skip retry on HTTP 422 (validation error) — retrying will not fix a malformed request
- Use `client_order_id=str(uuid.uuid4())` on every order for idempotency

### Strategy Framework

- Available strategies: `momentum`, `mean_reversion`, `breakout`, `vwap`
- Each strategy has independent parameters defined in config.json strategies array
- Strategies produce signals: BUY, SELL, or HOLD with confidence score 0.0-1.0
- Multiple strategies can run simultaneously with configurable weights
- Strategy weights are relative (normalized to sum to 1.0 before signal aggregation)
- A signal is only acted on if aggregated confidence exceeds the strategy's entry threshold

### Claude's Role

- Claude is a strategy-level analyst ONLY — not a trade executor
- Claude analyzes market opportunities and returns structured JSON recommendations
- Claude NEVER submits orders directly — all execution goes through the Python risk manager
- All Claude recommendations must pass through deterministic Python risk checks before execution
- Every Claude decision is audit-logged with full reasoning (symbol, signal, confidence, rationale)
- Claude may tighten (not loosen) entry thresholds and may widen (not tighten) stop-loss in `claude_decides` mode
