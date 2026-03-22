---
phase: 03-core-trading-loop
plan: "02"
subsystem: trading
tags: [alpaca-py, order-execution, risk-management, market-analyst, trade-executor, bracket-orders, atr-stop]

# Dependency graph
requires:
  - phase: 02-risk-management
    provides: RiskManager with submit_with_retry, circuit breaker, PDT tracking, position sizing
  - phase: 03-01
    provides: Signal dataclass in scripts/types.py, project structure foundation

provides:
  - OrderExecutor class wrapping all 4 Alpaca order types with ATR-based stops
  - agents/market-analyst.md — Claude Code agent for market scanning
  - agents/trade-executor.md — Claude Code agent for trade execution
  - tests/test_order_executor.py — 26 tests covering all order types and risk flows
  - tests/test_agents.py — 8 structural tests for agent files

affects:
  - 03-core-trading-loop (remaining plans depend on OrderExecutor)
  - 05-agent-orchestration (market-analyst and trade-executor agents used there)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conditional alpaca-py import (try/except) for test/CI environments without SDK"
    - "All order prices rounded to 2 decimal places before submission (Alpaca requirement)"
    - "All orders route through RiskManager.submit_with_retry() — never direct to trading_client"
    - "ATR-based stop formula: stop_price = round(entry_price - (ATR * multiplier), 2)"
    - "BUY signals use bracket orders (atomic stop+tp); SELL signals use market orders"
    - "Risk checks in execute_signal: circuit_breaker → position_count → pdt → sizing"

key-files:
  created:
    - scripts/order_executor.py
    - agents/market-analyst.md
    - agents/trade-executor.md
    - tests/test_order_executor.py
    - tests/test_agents.py
  modified: []

key-decisions:
  - "Conditional alpaca-py import in order_executor.py — same pattern as risk_manager.py, enables testing without SDK installed"
  - "execute_signal() implements all 4 risk checks in one method — circuit_breaker, position_count, pdt, sizing — before any order is placed"
  - "BUY signals always use bracket orders to atomically protect every entry with stop-loss and take-profit"
  - "SELL signals use market orders for speed — price certainty less critical than immediate exit"
  - "Signal.size_override_pct passed to calculate_position_size for claude_decides mode compatibility"

patterns-established:
  - "Order routing pattern: OrderExecutor.submit_*(args) → RiskManager.submit_with_retry(request, symbol)"
  - "Price rounding pattern: all prices rounded to 2 decimals before being placed in request objects"
  - "Risk check gate pattern: execute_signal() runs all checks before building any order object"
  - "TDD pattern: write tests first against behavior spec, then implement to pass"

requirements-completed:
  - ORD-01
  - ORD-02
  - ORD-03
  - ORD-04
  - ORD-05
  - PLUG-02
  - PLUG-04

# Metrics
duration: 4min
completed: "2026-03-22"
---

# Phase 03 Plan 02: OrderExecutor and Agent Definitions Summary

**OrderExecutor class wrapping 4 Alpaca order types with ATR-based bracket stops, routed through RiskManager.submit_with_retry(), plus market-analyst and trade-executor Claude Code agent definitions**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-22T01:15:28Z
- **Completed:** 2026-03-22T01:19:30Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- OrderExecutor implements all 4 Alpaca order types: market, limit, bracket, trailing stop — all routed through RiskManager.submit_with_retry()
- ATR-based stop/take-profit price calculation with 2-decimal rounding verified by exact-value tests (stop=146.25, tp=157.50 for entry=150.0, ATR=2.5, multiplier=1.5)
- execute_signal() runs 4 sequential risk checks (circuit breaker, position count, PDT, sizing) before any order submission; BUY uses bracket orders, SELL uses market orders
- 34 tests pass: 26 for OrderExecutor (order types, stop math, signal execution flows), 8 structural tests for agent files
- agents/market-analyst.md and agents/trade-executor.md created with model: sonnet frontmatter

## Task Commits

Each task was committed atomically:

1. **Task 1: Create OrderExecutor module and agent definitions** - `cf2184c` (feat)
2. **Task 2: Write tests for OrderExecutor and agent definitions** - `6e98295` (test)

**Plan metadata:** (docs commit — see final_commit below)

_Note: Task 2 used TDD pattern — implementation was complete before tests, so all tests passed immediately in GREEN phase._

## Files Created/Modified

- `scripts/order_executor.py` — OrderExecutor class with 4 order types, ATR calculations, and execute_signal() risk gate
- `agents/market-analyst.md` — Claude Code agent for market scanning; model: sonnet, effort: medium
- `agents/trade-executor.md` — Claude Code agent for trade execution via OrderExecutor; model: sonnet, effort: medium
- `tests/test_order_executor.py` — 26 tests: TestOrderTypes, TestStopCalc, TestExecuteSignal (371 lines)
- `tests/test_agents.py` — 8 structural tests: TestMarketAnalyst, TestTradeExecutor, TestRiskManagerAgent (120 lines)

## Decisions Made

- Conditional alpaca-py import (try/except) in order_executor.py — same pattern as risk_manager.py, enables testing without SDK in CI
- execute_signal() calls all risk checks before building order objects — defensive ordering prevents unnecessary API object construction
- BUY signals always use bracket orders (entry + stop-loss + take-profit atomically) per risk-rules.md requirement
- SELL signals use market orders — immediate exit speed is prioritized over price certainty
- Signal.size_override_pct passed through to calculate_position_size for future claude_decides mode compatibility

## Deviations from Plan

None — plan executed exactly as written.

Note: scripts/types.py with Signal dataclass was found to already exist from a prior plan (03-01). No changes needed.

## Issues Encountered

- `python` command not found on this system; used `python3` / `.venv` activation for all verification commands. No impact on deliverables.

## Known Stubs

None — all methods are fully implemented with real logic. No hardcoded placeholders.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- OrderExecutor is ready to be integrated into the trading loop (03-03)
- market-analyst and trade-executor agents are ready for agent orchestration (Phase 05)
- All 4 order types tested and verified against mocked RiskManager
- ATR stop formula verified with exact values — matches risk-rules.md specification

## Self-Check: PASSED

- scripts/order_executor.py: FOUND
- agents/market-analyst.md: FOUND
- agents/trade-executor.md: FOUND
- tests/test_order_executor.py: FOUND
- tests/test_agents.py: FOUND
- .planning/phases/03-core-trading-loop/03-02-SUMMARY.md: FOUND
- commit cf2184c (feat): FOUND
- commit 6e98295 (test): FOUND

---
*Phase: 03-core-trading-loop*
*Completed: 2026-03-22*
