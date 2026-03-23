# Trading Bot Setup Context

## User Profile
- **Experience Level:** Beginner
- **Involvement:** Notify — bot trades autonomously, sends summaries and alerts
- **Risk Tolerance:** Conservative — max 5% per position, 2% daily loss limit

## Trading Setup
- **Budget:** $10 USD
- **Trading Mode:** Paper trading (simulated)
- **MCP Server:** Enabled — Claude has direct Alpaca API access via MCP tools
- **Market Hours Only:** Yes

## Strategy Plan
- **Strategies:** Momentum (weight: 1.0)
  - RSI period: 14, MACD fast/slow/signal: 12/26/9, EMA short/long: 9/21
- **Autonomy Mode:** Fixed parameters — bot uses configured settings exactly

## Stock Discovery
- **Discovery Mode:** Auto-discover — bot scans market movers, volume leaders, and sector trends each session
- **Watchlist:** None (fully autonomous discovery)

## Build Instructions
Generate trading scripts that:
1. **MarketScanner** — scans for high-volume movers and trending stocks at session start
2. **Momentum strategy engine** — implements RSI + MACD + EMA crossover logic with fixed params above
3. **RiskManager** — enforces conservative limits: max 5% per position, 2% daily loss limit, circuit breaker, PDT compliance
4. **OrderExecutor** — submits orders via Alpaca API (paper mode), never bypasses risk checks
5. **Notification system** — logs trade decisions and summaries for user review
6. **Main trading loop** — orchestrates scan → analyze → risk-check → execute cycle autonomously
7. **Claude analysis integration** — uses Claude to evaluate setups before trading, within fixed param bounds
8. All API calls through alpaca-py SDK. MCP server available for conversational queries but scripts use SDK directly.
9. Budget constraint: $10 total capital, position sizes calculated accordingly
10. Error handling for market closures, API failures, and edge cases — safe to run unattended
