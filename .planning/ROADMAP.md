# Roadmap: Trading Bot Plugin

## Overview

This roadmap delivers an autonomous stock day trading Claude Code plugin in six phases. The dependency chain is strict: plugin foundation before runtime, risk controls before order execution, deterministic loop before Claude analysis, and distribution last. Each phase delivers a coherent, verifiable capability. Users can validate the bot in paper mode before ever touching live funds.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Plugin Foundation** - Installable plugin structure with `/initialize` wizard and config schema (completed 2026-03-22)
- [x] **Phase 2: Risk Management** - Circuit breakers, position sizing, PDT guard, and safety hook wired before any order code exists (completed 2026-03-22)
- [x] **Phase 3: Core Trading Loop** - Deterministic market scan → signal → order → track pipeline running in paper mode (completed 2026-03-22)
- [ ] **Phase 4: Build Command** - `/build` generates tailored Python scripts with secure secret management
- [ ] **Phase 5: Run Command and Claude Analysis** - `/run` orchestrates multi-agent execution; Claude added as strategy-level reasoning layer
- [ ] **Phase 6: Distribution and Observability** - Marketplace publishing, standalone mode, end-of-day reports, and notifications

## Phase Details

### Phase 1: Plugin Foundation
**Goal**: Users can install the plugin and complete an interactive setup wizard that captures all trading preferences and produces a valid config file
**Depends on**: Nothing (first phase)
**Requirements**: CMD-01, CMD-02, CMD-03, CMD-04, CMD-05, CMD-12, ALP-01, ALP-02, ALP-03, ALP-04, PLUG-01, PLUG-05, PLUG-06, PLUG-08, STATE-03
**Success Criteria** (what must be TRUE):
  1. User can run `/initialize` and receive adaptive questions based on their stated experience level (beginner vs expert)
  2. Initialize wizard captures risk tolerance, budget, paper vs live mode, autonomy level, strategies, market hours, and ticker watchlist without requiring the user to write any code
  3. User can select autonomous risk mode (Claude decides aggression) or fixed risk parameters during setup
  4. Running `/initialize` produces a `config.json` file that all downstream commands can consume without modification
  5. Plugin installs Python dependencies on session start (ALP-04 MCP server DROPPED -- SDK-only approach)
**Plans:** 3/3 plans complete

Plans:
- [x] 01-01-PLAN.md — Plugin scaffold: manifest, directory structure, SessionStart hook, and tests
- [x] 01-02-PLAN.md — Domain knowledge: trading-rules skill, reference files, config schema tests
- [x] 01-03-PLAN.md — /initialize wizard command with adaptive beginner/expert flow

### Phase 2: Risk Management
**Goal**: All risk controls are in place as foundational infrastructure — circuit breakers, position sizing, PDT tracking, and a PreToolUse safety hook — before any order execution code exists
**Depends on**: Phase 1
**Requirements**: RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, POS-01, POS-02, PLUG-03, PLUG-07
**Success Criteria** (what must be TRUE):
  1. The bot halts all trading when daily drawdown exceeds the configured threshold and does not resume until manually restarted
  2. The bot tracks the rolling 5-day day-trade count and blocks new entries when the count reaches 3 (approaching PDT limit)
  3. Position sizing is calculated as a configurable percentage of account equity, never a fixed dollar amount
  4. Any order submission attempt is intercepted by the PreToolUse hook, which rejects orders that violate safety constraints before they reach Alpaca
  5. All Alpaca API calls are wrapped with exponential backoff and network failures during order submission do not create ghost positions
**Plans:** 2/2 plans complete

Plans:
- [x] 02-01-PLAN.md — RiskManager class: circuit breaker, position sizing, PDT tracking, max positions, retry with ghost prevention
- [x] 02-02-PLAN.md — PreToolUse safety hook (validate-order.sh) and risk-manager agent definition

### Phase 3: Core Trading Loop
**Goal**: The full Market Scanner → Signal Generator → Risk Manager → Order Executor → Portfolio Tracker pipeline runs end-to-end in paper mode with one working strategy, crash recovery, and full trade logging
**Depends on**: Phase 2
**Requirements**: ORD-01, ORD-02, ORD-03, ORD-04, ORD-05, POS-03, POS-04, TA-01, TA-02, TA-03, TA-04, TA-05, TA-06, STRAT-01, STRAT-02, STRAT-03, STRAT-04, STRAT-05, ALP-05, STATE-01, STATE-02, OBS-01, OBS-02, PLUG-02, PLUG-04
**Success Criteria** (what must be TRUE):
  1. Bot scans configured watchlist tickers, computes RSI, MACD, EMA, ATR, Bollinger Bands, and VWAP on live Alpaca data, and produces trade signals without Claude involvement
  2. Bot submits market, limit, bracket, and trailing stop-loss orders via alpaca-py and all orders include a stop-loss (bracket or explicit)
  3. Bot recovers from a crash by reading SQLite state and reconciling against Alpaca's live positions on startup — no phantom positions
  4. Bot closes or logs all open positions on SIGINT/SIGTERM graceful shutdown
  5. Bot respects market hours by checking Alpaca's market clock before each loop iteration and skips iteration if market is closed
**Plans:** 5/5 plans complete

Plans:
- [x] 03-01-PLAN.md — Signal dataclass, MarketScanner with all 6 technical indicators (pandas-ta), market clock check
- [x] 03-02-PLAN.md — OrderExecutor with 4 order types, ATR-based stops, market-analyst and trade-executor agent definitions
- [x] 03-03-PLAN.md — SQLite StateStore with crash recovery, position reconciliation, PDT migration from JSON
- [x] 03-04-PLAN.md — Strategy modules (momentum, mean reversion, breakout, VWAP) as pluggable BaseStrategy implementations
- [x] 03-05-PLAN.md — PortfolioTracker, bot.py main loop (APScheduler), graceful shutdown, RiskManager state_store integration

### Phase 4: Build Command
**Goal**: Users can run `/build` to generate a complete, tailored set of Python trading scripts from their config — ready to run — with no secrets written to any generated file
**Depends on**: Phase 3
**Requirements**: CMD-06, CMD-07, CMD-08, CMD-09, DIST-04, DIST-05
**Success Criteria** (what must be TRUE):
  1. User can run `/build` and receive Python scripts customized to their selected strategies and preferences without writing any code
  2. Generated files load API keys from environment variables only — no key values appear in any generated file
  3. `/build` auto-creates `.gitignore` that excludes `.env` and other sensitive files
  4. Generated scripts can run standalone on a VPS or server without Claude Code installed
  5. Generated artifacts include cron entry or systemd unit file instructions for unattended server execution
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — Build generator module and /build slash command
- [ ] 04-02-PLAN.md — Secret management, .gitignore, standalone runner, deployment instructions

### Phase 5: Run Command and Claude Analysis
**Goal**: Users can run `/run` to start the autonomous trading loop via Claude Code agents, with Claude acting as a strategy-level reasoning layer that analyzes trade opportunities and returns structured JSON recommendations — never submitting orders directly
**Depends on**: Phase 4
**Requirements**: CMD-10, CMD-11, AI-01, AI-02, AI-03, AI-04, AI-05, PLUG-02, PLUG-04
**Success Criteria** (what must be TRUE):
  1. User can run `/run` to launch the autonomous trading loop in Claude Code agent mode without further interaction
  2. The market-analyst agent reads real-time Alpaca market data via the MCP server and outputs structured JSON with action, confidence, and reasoning for each trade opportunity
  3. Claude's recommendations pass through the deterministic Python risk manager before any order is submitted — Claude never calls an Alpaca order tool directly
  4. Every Claude trade decision is written to the audit log with full reasoning inspectable after the session
  5. The loop runs in both Claude Code agent mode and standalone Python mode from the same generated scripts
**Plans**: 2 plans

Plans:
- [ ] 05-01: `/run` command, market-analyst agent, and trade-executor agent wiring
- [ ] 05-02: Claude analysis integration (structured JSON prompts, confidence gating, audit logging)

### Phase 6: Distribution and Observability
**Goal**: The plugin is publishable to the Claude Code marketplace, users receive end-of-day summaries and key event notifications, and all runtime observability is in place for unattended operation
**Depends on**: Phase 5
**Requirements**: OBS-03, OBS-04, OBS-05, DIST-01, DIST-02, DIST-03
**Success Criteria** (what must be TRUE):
  1. The plugin is installable via `claude plugin install` from the marketplace using its GitHub URL
  2. Plugin includes a valid `plugin.json` manifest with version, description, and dependency declarations
  3. Bot generates an end-of-day summary report showing P&L, trade count, win rate, and biggest winner/loser
  4. Bot sends a notification when the circuit breaker fires, at end-of-day, or on a large win/loss — via at least one configurable channel (Slack or email)
**Plans**: 2 plans

Plans:
- [ ] 06-01: `plugin.json` manifest, marketplace publishing, and installation verification
- [ ] 06-02: End-of-day report, Slack/email notification webhooks

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Plugin Foundation | 3/3 | Complete   | 2026-03-22 |
| 2. Risk Management | 2/2 | Complete   | 2026-03-22 |
| 3. Core Trading Loop | 5/5 | Complete   | 2026-03-22 |
| 4. Build Command | 0/2 | Not started | - |
| 5. Run Command and Claude Analysis | 0/2 | Not started | - |
| 6. Distribution and Observability | 0/2 | Not started | - |
