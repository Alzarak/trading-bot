# Phase 3: Core Trading Loop - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the full Market Scanner → Signal Generator → Risk Manager → Order Executor → Portfolio Tracker pipeline running end-to-end in paper mode. Includes all 6 technical indicators (RSI, MACD, EMA, ATR, Bollinger Bands, VWAP), all 4 order types (market, limit, bracket, trailing stop), 4 strategy modules (momentum, mean reversion, breakout, VWAP), SQLite state persistence, crash recovery via position reconciliation, graceful shutdown, market hours enforcement, and trade logging.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/risk_manager.py` — RiskManager class with circuit breaker, position sizing, PDT tracking, submit_with_retry
- `references/risk-rules.md` — Risk rules reference (circuit breaker formulas, position sizing, ATR stops)
- `references/trading-strategies.md` — All 4 strategies with signal logic, entry/exit conditions, default params
- `references/alpaca-api-patterns.md` — Complete alpaca-py SDK patterns for all order types, account, positions
- `skills/trading-rules/SKILL.md` — Domain context for Claude
- `tests/conftest.py` — Shared fixtures (sample_config, mock_trading_client, plugin_data_dir)
- `tests/test_risk_manager.py` — 35 risk manager tests, `tests/test_config.py` — 20 config tests

### Established Patterns
- Python with alpaca-py SDK (alpaca-py==0.43.2)
- pandas-ta for technical indicators (pandas-ta==0.4.71b0)
- APScheduler <4.0 for scheduling
- pydantic-settings for config management
- pytest for testing with mocked Alpaca clients
- loguru for structured logging

### Integration Points
- `config.json` provides strategy selection, watchlist, risk params
- `RiskManager` validates every trade before order submission
- Alpaca paper trading endpoint (paper=True on TradingClient)
- SQLite database in ${CLAUDE_PLUGIN_DATA} for state persistence
- Signal handlers for graceful SIGINT/SIGTERM shutdown

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
