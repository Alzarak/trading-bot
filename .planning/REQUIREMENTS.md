# Requirements: Trading Bot Plugin

**Defined:** 2026-03-21
**Core Value:** After initial setup, the bot trades autonomously without human intervention — scanning markets, making decisions (using Claude for analysis), and executing trades on a loop.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Plugin Commands

- [x] **CMD-01**: User can run `/initialize` to start an interactive setup wizard that captures all trading preferences
- [x] **CMD-02**: Initialize wizard adapts questions based on beginner vs expert user
- [x] **CMD-03**: Initialize wizard captures: risk tolerance, budget, paper vs live, autonomy level, strategies, market hours, ticker watchlist
- [x] **CMD-04**: Initialize wizard includes autonomous risk mode option where Claude decides aggression per trade
- [x] **CMD-05**: Initialize wizard outputs a complete config file that all other commands consume
- [ ] **CMD-06**: User can run `/build` to generate all Python trading scripts from initialize config
- [ ] **CMD-07**: Build command generates tailored scripts based on selected strategies and preferences
- [ ] **CMD-08**: Build command enforces `.env` pattern for API keys — never writes literal secrets to generated files
- [ ] **CMD-09**: Build command auto-creates `.gitignore` with `.env` and sensitive files excluded
- [ ] **CMD-10**: User can run `/run` to start the autonomous trading loop
- [ ] **CMD-11**: Run command supports both Claude Code agent mode and standalone Python execution
- [x] **CMD-12**: User can select from momentum, mean reversion, breakout, and VWAP strategies during initialize

### Alpaca Integration

- [x] **ALP-01**: Plugin authenticates with Alpaca API using environment variables (paper and live keys)
- [x] **ALP-02**: Plugin supports paper trading mode with Alpaca's paper endpoint
- [x] **ALP-03**: Plugin supports live trading mode with Alpaca's live endpoint
- [x] **ALP-04**: Alpaca MCP server is configured in `.mcp.json` for real-time market data access within Claude
- [x] **ALP-05**: Plugin queries Alpaca market clock to enforce market hours (9:30am-4:00pm ET)

### Order Management

- [x] **ORD-01**: Bot can submit market orders for immediate execution
- [x] **ORD-02**: Bot can submit limit orders for controlled entry price
- [x] **ORD-03**: Bot can submit bracket orders (entry + stop-loss + take-profit in one call)
- [x] **ORD-04**: Bot can submit trailing stop-loss orders to lock in profits
- [x] **ORD-05**: Bot uses ATR-based dynamic stop placement that scales with volatility

### Position Management

- [x] **POS-01**: Bot sizes positions as percentage of account equity (configurable)
- [x] **POS-02**: Bot enforces maximum position count limit
- [ ] **POS-03**: Bot closes or logs all open positions on graceful shutdown (SIGINT/SIGTERM)
- [x] **POS-04**: Bot reconciles local state against Alpaca's actual positions on startup (crash recovery)

### Risk Management

- [x] **RISK-01**: Bot halts all trading when daily drawdown exceeds configured threshold (circuit breaker)
- [x] **RISK-02**: Bot tracks day trade count and warns/blocks when approaching PDT limit (4 trades per 5 days under $25K)
- [x] **RISK-03**: Bot wraps all API calls with exponential backoff and retry logic
- [x] **RISK-04**: Bot handles network failures during order submission without creating ghost positions
- [x] **RISK-05**: Claude dynamically adjusts aggression (position size, entry thresholds) based on market conditions and recent performance

### Technical Analysis

- [x] **TA-01**: Bot computes RSI indicator on configured timeframe
- [x] **TA-02**: Bot computes MACD indicator (signal line, histogram)
- [x] **TA-03**: Bot computes EMA (exponential moving average) for trend detection
- [x] **TA-04**: Bot computes ATR (average true range) for volatility-based stops
- [x] **TA-05**: Bot computes Bollinger Bands for mean reversion signals
- [x] **TA-06**: Bot computes VWAP for intraday price reference

### Trading Strategies

- [ ] **STRAT-01**: Momentum strategy — enters on strong RSI + MACD confirmation, exits on reversal signals
- [ ] **STRAT-02**: Mean reversion strategy — enters on oversold/overbought extremes, exits on return to mean
- [ ] **STRAT-03**: Breakout strategy — enters on volume-confirmed price breakouts, exits on failed continuation
- [ ] **STRAT-04**: VWAP reversion strategy — enters on significant deviation from VWAP, exits on reversion
- [ ] **STRAT-05**: Each strategy is a configurable module selectable via config

### Claude AI Integration

- [ ] **AI-01**: Claude analyzes each trade opportunity with structured JSON output (action, confidence, reasoning)
- [ ] **AI-02**: Claude accesses real-time market data via Alpaca MCP server during analysis
- [ ] **AI-03**: Claude operates as strategy-level analyst — never submits orders directly
- [ ] **AI-04**: All Claude recommendations pass through deterministic Python risk manager before execution
- [ ] **AI-05**: Claude's reasoning is logged for every trade decision (inspectable audit trail)

### Plugin Architecture

- [x] **PLUG-01**: Plugin follows Claude Code plugin directory structure (commands/, agents/, skills/, hooks/)
- [x] **PLUG-02**: Separate agent for market scanning/analysis
- [x] **PLUG-03**: Separate agent for risk management validation
- [x] **PLUG-04**: Separate agent for trade execution
- [x] **PLUG-05**: Trading rules skill provides domain context to all agents
- [x] **PLUG-06**: SessionStart hook installs Python dependencies into plugin data directory
- [x] **PLUG-07**: PreToolUse hook validates safety constraints before order submission
- [x] **PLUG-08**: Reference files document trading strategies, risk rules, and Alpaca API patterns

### Observability

- [ ] **OBS-01**: Bot logs every trade to file (timestamp, ticker, action, price, quantity, P&L)
- [ ] **OBS-02**: Bot tracks portfolio P&L (daily and total return) using Alpaca account endpoint
- [ ] **OBS-03**: Bot generates end-of-day summary report (P&L, trades taken, win rate, biggest winner/loser)
- [ ] **OBS-04**: Bot sends notifications on key events (circuit breaker fired, daily summary, large win/loss)
- [ ] **OBS-05**: Notification channels configurable (Slack webhook, email)

### State Management

- [x] **STATE-01**: Bot persists trading state to SQLite database (positions, orders, trade history)
- [x] **STATE-02**: Bot recovers from crashes by reconciling SQLite state against Alpaca positions
- [x] **STATE-03**: Bot maintains configuration in JSON file editable without code changes

### Distribution

- [ ] **DIST-01**: Plugin is installable via `claude plugin install` from marketplace
- [ ] **DIST-02**: Plugin includes `plugin.json` manifest with version, description, dependencies
- [ ] **DIST-03**: Plugin is publishable to Claude Code plugin marketplace via GitHub
- [ ] **DIST-04**: Generated Python scripts can run standalone on a VPS/server without Claude Code
- [ ] **DIST-05**: Standalone mode includes cron/systemd setup instructions or scripts

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhanced Analysis

- **ANAL-01**: News sentiment analysis via Alpaca's news endpoint for signal confirmation
- **ANAL-02**: Self-improving strategy tuning based on historical performance data

### Expanded Markets

- **MKT-01**: Cryptocurrency trading via Alpaca's crypto API
- **MKT-02**: Extended hours trading (pre-market/after-hours)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Backtesting engine | Full backtesting (slippage, fills, spread) is a product in itself; paper trading is the honest equivalent |
| Web dashboard / UI | Adds web server, frontend, auth — this is a CLI plugin, not SaaS; use Alpaca's built-in dashboard |
| WebSocket streaming | REST polling on 1-min bars is sufficient for day trading strategies in scope; WebSockets add reconnect complexity |
| Multiple broker support | Each broker has different APIs/fills; doubles testing surface; Alpaca is free with no commissions |
| Options trading | Fundamentally different domain (Greeks, expiry, margin); overwhelming complexity |
| Leverage / margin trading | Margin calls can liquidate accounts; contradicts "safe to run unattended" constraint |
| Social / copy trading | Privacy and regulatory complexity (investment advice laws); requires backend + moderation |
| Social media sentiment | Expensive/unreliable APIs; low predictive value for single-day trades; Alpaca news endpoint is sufficient |
| Custom ML model training | Requires datasets, validation pipelines, overfitting prevention; Claude's LLM judgment is the differentiator |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CMD-01 | Phase 1 | Complete |
| CMD-02 | Phase 1 | Complete |
| CMD-03 | Phase 1 | Complete |
| CMD-04 | Phase 1 | Complete |
| CMD-05 | Phase 1 | Complete |
| CMD-06 | Phase 4 | Pending |
| CMD-07 | Phase 4 | Pending |
| CMD-08 | Phase 4 | Pending |
| CMD-09 | Phase 4 | Pending |
| CMD-10 | Phase 5 | Pending |
| CMD-11 | Phase 5 | Pending |
| CMD-12 | Phase 1 | Complete |
| ALP-01 | Phase 1 | Complete |
| ALP-02 | Phase 1 | Complete |
| ALP-03 | Phase 1 | Complete |
| ALP-04 | Phase 1 | Complete |
| ALP-05 | Phase 3 | Complete |
| ORD-01 | Phase 3 | Complete |
| ORD-02 | Phase 3 | Complete |
| ORD-03 | Phase 3 | Complete |
| ORD-04 | Phase 3 | Complete |
| ORD-05 | Phase 3 | Complete |
| POS-01 | Phase 2 | Complete |
| POS-02 | Phase 2 | Complete |
| POS-03 | Phase 3 | Pending |
| POS-04 | Phase 3 | Complete |
| RISK-01 | Phase 2 | Complete |
| RISK-02 | Phase 2 | Complete |
| RISK-03 | Phase 2 | Complete |
| RISK-04 | Phase 2 | Complete |
| RISK-05 | Phase 2 | Complete |
| TA-01 | Phase 3 | Complete |
| TA-02 | Phase 3 | Complete |
| TA-03 | Phase 3 | Complete |
| TA-04 | Phase 3 | Complete |
| TA-05 | Phase 3 | Complete |
| TA-06 | Phase 3 | Complete |
| STRAT-01 | Phase 3 | Pending |
| STRAT-02 | Phase 3 | Pending |
| STRAT-03 | Phase 3 | Pending |
| STRAT-04 | Phase 3 | Pending |
| STRAT-05 | Phase 3 | Pending |
| AI-01 | Phase 5 | Pending |
| AI-02 | Phase 5 | Pending |
| AI-03 | Phase 5 | Pending |
| AI-04 | Phase 5 | Pending |
| AI-05 | Phase 5 | Pending |
| PLUG-01 | Phase 1 | Complete |
| PLUG-02 | Phase 5 | Complete |
| PLUG-03 | Phase 2 | Complete |
| PLUG-04 | Phase 5 | Complete |
| PLUG-05 | Phase 1 | Complete |
| PLUG-06 | Phase 1 | Complete |
| PLUG-07 | Phase 2 | Complete |
| PLUG-08 | Phase 1 | Complete |
| OBS-01 | Phase 3 | Pending |
| OBS-02 | Phase 3 | Pending |
| OBS-03 | Phase 6 | Pending |
| OBS-04 | Phase 6 | Pending |
| OBS-05 | Phase 6 | Pending |
| STATE-01 | Phase 3 | Complete |
| STATE-02 | Phase 3 | Complete |
| STATE-03 | Phase 1 | Complete |
| DIST-01 | Phase 6 | Pending |
| DIST-02 | Phase 6 | Pending |
| DIST-03 | Phase 6 | Pending |
| DIST-04 | Phase 4 | Pending |
| DIST-05 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 68 total
- Mapped to phases: 68
- Unmapped: 0

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after roadmap creation — traceability complete*
