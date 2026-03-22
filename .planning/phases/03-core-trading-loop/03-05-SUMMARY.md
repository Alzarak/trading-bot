---
phase: 03-core-trading-loop
plan: 05
subsystem: trading-loop
tags: [apscheduler, loguru, sqlite, portfolio-tracker, bot, graceful-shutdown, pdt]

# Dependency graph
requires:
  - phase: 03-01
    provides: MarketScanner with scan() and is_market_open()
  - phase: 03-02
    provides: OrderExecutor.execute_signal() with risk checks
  - phase: 03-03
    provides: StateStore for SQLite persistence and reconcile_positions()
  - phase: 03-04
    provides: STRATEGY_REGISTRY with 4 strategy classes
  - phase: 02-01
    provides: RiskManager with circuit breaker, PDT tracking, position sizing
provides:
  - scripts/portfolio_tracker.py — PortfolioTracker with loguru JSON trade sink + SQLite delegation
  - scripts/bot.py — main entry point with APScheduler 60-second loop, market hours guard, graceful shutdown
  - Updated scripts/risk_manager.py — optional state_store parameter for SQLite PDT delegation
  - Full trading pipeline wired: scanner -> strategies -> risk -> executor -> state_store -> trade_log
affects:
  - phase-04-claude-integration (will import bot.py and PortfolioTracker)
  - phase-05-agents (agents interact with bot.py pipeline)
  - phase-06-plugin-integration (plugin commands start/stop bot.py)

# Tech tracking
tech-stack:
  added:
    - APScheduler BackgroundScheduler with IntervalTrigger (60-second scan cycle)
    - loguru serialize=True sink for rotating NDJSON trade log (90-day retention)
  patterns:
    - Dual-sink trade logging: loguru JSON file + SQLite for redundancy
    - state_store optional parameter pattern: None = JSON fallback, provided = SQLite delegation
    - Graceful shutdown: SIGINT/SIGTERM sets flag, scheduler finishes cycle, positions closed
    - scan_and_trade pipeline: scanner -> registry -> executor -> state_store -> tracker
    - Crash recovery called on every bot startup via reconcile_positions()

key-files:
  created:
    - scripts/portfolio_tracker.py
    - scripts/bot.py
    - tests/test_portfolio_tracker.py
    - tests/test_bot.py
  modified:
    - scripts/risk_manager.py

key-decisions:
  - "PortfolioTracker writes every trade to both loguru NDJSON rotating file and SQLite — redundancy for audit trail"
  - "RiskManager state_store=None default preserves backward compatibility with all existing Phase 2 tests"
  - "BackgroundScheduler.shutdown(wait=True) ensures current scan cycle completes before graceful shutdown proceeds"
  - "scan_and_trade catches per-symbol exceptions individually — one bad symbol does not halt others"
  - "perform_graceful_shutdown catches per-position exceptions — one failed close does not prevent remaining closes"

patterns-established:
  - "Dual-sink logging pattern: loguru file (human-readable/archival) + SQLite (queryable/structured)"
  - "Global shutdown flag pattern: signal handler sets flag, main loop polls with sleep(1)"
  - "Per-item exception isolation in loops: catch, log, continue — never let one item kill the batch"

requirements-completed: [OBS-01, OBS-02, POS-03]

# Metrics
duration: 5min
completed: 2026-03-22
---

# Phase 3 Plan 05: Pipeline Wiring Summary

**APScheduler trading loop with PortfolioTracker dual-sink trade logging (loguru NDJSON + SQLite), graceful SIGINT/SIGTERM shutdown that closes all Alpaca positions, and RiskManager PDT delegation to SQLite**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-22T01:31:39Z
- **Completed:** 2026-03-22T01:36:17Z
- **Tasks:** 3
- **Files modified:** 5 (2 created scripts, 1 modified script, 2 test files)

## Accomplishments

- Full trading pipeline wired into bot.py: MarketScanner feeds strategies, strategies produce signals, signals route through risk checks and OrderExecutor, every trade logged to both loguru JSON file and SQLite
- PortfolioTracker logs every trade with dual-sink redundancy (rotating NDJSON at 90-day retention + SQLite trade_log table) and computes daily P&L from Alpaca account equity
- APScheduler BackgroundScheduler runs scan_and_trade every 60 seconds; SIGINT/SIGTERM triggers graceful shutdown that finishes the current cycle then closes all open Alpaca positions
- RiskManager extended with optional state_store parameter — PDT tracking delegates to SQLite when provided, falls back to JSON for backward compatibility with all 9 existing Phase 2 tests
- 202 total tests passing across all phases

## Task Commits

Each task was committed atomically:

1. **Task 1: PortfolioTracker + RiskManager state_store extension** - `3576a66` (feat)
2. **Task 2: bot.py main loop with APScheduler and graceful shutdown** - `6e9e72a` (feat)
3. **Task 3: Tests for PortfolioTracker and bot** - `36d30db` (test)

## Files Created/Modified

- `scripts/portfolio_tracker.py` — PortfolioTracker with log_trade() dual-sink, get_daily_pnl(), get_total_return()
- `scripts/bot.py` — main entry point: load_config(), create_clients(), scan_and_trade() pipeline, perform_graceful_shutdown(), main()
- `scripts/risk_manager.py` — extended __init__ with state_store=None, check_pdt_limit() and record_day_trade() delegate to state_store when provided
- `tests/test_portfolio_tracker.py` — TestTradeLog (state_store delegation), TestPnL (positive/negative/breakeven, total_return vs last_equity)
- `tests/test_bot.py` — TestGracefulShutdown (flag set, positions closed, per-position error isolation), TestScanAndTrade (market closed guard, shutdown guard, BUY/HOLD signal handling)

## Decisions Made

- Dual-sink trade logging (loguru file + SQLite) for redundancy — file provides human-readable rotating archive, SQLite provides queryable structured data
- RiskManager state_store=None preserves backward compatibility — all existing Phase 2 PDT tests pass unchanged
- BackgroundScheduler.shutdown(wait=True) ensures the in-progress scan cycle completes before graceful position closing begins
- Per-symbol and per-position exception isolation in loops — one failure does not halt the batch

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — all pipeline connections are wired. PortfolioTracker writes to real loguru sinks and real StateStore. bot.py calls real MarketScanner, OrderExecutor, and StateStore methods.

## User Setup Required

None — no external service configuration required beyond Alpaca API keys (handled in Phase 1 .env.template).

## Next Phase Readiness

- Full Phase 3 pipeline complete: scanner -> strategies -> risk -> executor -> state_store -> trade_log
- bot.py is the autonomous trading entry point, ready for Phase 4 Claude integration
- All 202 tests green across Phases 1-3
- The bot can be started with `python scripts/bot.py` once ALPACA_API_KEY and ALPACA_SECRET_KEY are set

---
*Phase: 03-core-trading-loop*
*Completed: 2026-03-22*
