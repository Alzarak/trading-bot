---
phase: 02-risk-management
plan: 01
subsystem: trading
tags: [risk-management, circuit-breaker, pdt, position-sizing, alpaca-py, loguru, tdd]

# Dependency graph
requires:
  - phase: 01-plugin-foundation
    provides: config schema (config.json shape), test fixtures (conftest.py, sample_config)
provides:
  - RiskManager class with circuit breaker, position sizing, PDT tracking, max position limits, claude_decides clamping, and API retry with ghost position prevention
  - Updated config schema contract: max_positions field added to REQUIRED_FIELDS and sample_config fixture
  - 24 unit tests covering RISK-01 through RISK-05, POS-01, POS-02
affects:
  - 03-order-execution (all order submission must pass through RiskManager guardrails)
  - 05-agent-integration (claude_decides mode uses RiskManager.calculate_position_size with size_override_pct)

# Tech tracking
tech-stack:
  added: [loguru (structured logging for autonomous trading loop), scripts/risk_manager.py]
  patterns:
    - Conditional import for alpaca-py (try/except ImportError -> APIError = Exception) enables testing without SDK installed
    - os.environ.get("CLAUDE_PLUGIN_DATA", "/tmp") for all file paths so tests can override via monkeypatch
    - TDD red-green cycle: test file committed first (ImportError = RED), then implementation (GREEN)

key-files:
  created:
    - scripts/risk_manager.py (RiskManager class, 160+ lines, 9 methods)
    - tests/test_risk_manager.py (24 unit tests across 7 test classes)
  modified:
    - tests/conftest.py (added max_positions to sample_config, new mock_trading_client and plugin_data_dir fixtures)
    - tests/test_config.py (added max_positions to REQUIRED_FIELDS, test_max_positions_in_range test)

key-decisions:
  - "loguru used for all logging in RiskManager — one import, structured output, critical for unattended operation review"
  - "Conditional alpaca-py import (try/except) enables testing RiskManager without alpaca-py installed — important for CI environments"
  - "PDT window uses rolling 7 calendar days (not 5 business days from risk-rules.md) — plan spec takes precedence for implementation"
  - "test_clamps_low_override fixed: override 1% (not 10%) needed to trigger lower clamp bound — 10% clamps high, not low"

patterns-established:
  - "RiskManager fixture pattern: make_rm(sample_config, mock_trading_client) helper reduces boilerplate across test classes"
  - "plugin_data_dir fixture sets CLAUDE_PLUGIN_DATA via monkeypatch — all file-writing methods use this env var"
  - "Ghost position check via _has_open_position() before every retry iteration"

requirements-completed: [RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, POS-01, POS-02]

# Metrics
duration: 4min
completed: 2026-03-22
---

# Phase 2 Plan 1: Risk Management Core Summary

**RiskManager class with circuit breaker, PDT tracking, position sizing with claude_decides clamping, and ghost-position-safe retry — 24 unit tests all green**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-22T00:33:46Z
- **Completed:** 2026-03-22T00:37:59Z
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files modified:** 4

## Accomplishments
- RiskManager class (scripts/risk_manager.py) implements all 9 safety methods: initialize_session, check_circuit_breaker, _persist_circuit_breaker, calculate_position_size, check_position_count, check_pdt_limit, record_day_trade, _load_pdt_trades/_save_pdt_trades, submit_with_retry
- Circuit breaker: triggers at max_daily_loss_pct, writes circuit_breaker.flag to CLAUDE_PLUGIN_DATA, stays triggered even if equity recovers — manual restart required
- claude_decides mode clamping: size_override_pct clamped to [50%, 150%] of max_position_pct before position value is calculated
- submit_with_retry: 5 attempts with [1, 2, 4, 8]s exponential backoff, skips 422/403 immediately, checks for ghost positions before every retry
- Config schema extended: max_positions added to REQUIRED_FIELDS and sample_config fixture; test_max_positions_in_range asserts range [1, 10]
- Full test suite: 70 tests pass (46 from Phase 1 + 24 new risk manager tests), 0 regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add max_positions to config schema and create risk manager test suite (RED)** - `e6060e5` (test)
2. **Task 2: Implement RiskManager class (GREEN phase)** - `a167591` (feat)

**Plan metadata:** (docs commit — see final commit)

_Note: TDD tasks have two commits (test RED → feat GREEN)_

## Files Created/Modified
- `scripts/risk_manager.py` - RiskManager class with all 9 risk enforcement methods (160+ lines)
- `tests/test_risk_manager.py` - 24 unit tests across 7 classes (TestCircuitBreaker, TestPositionSizing, TestPositionCount, TestPDTTracking, TestClaudeDecides, TestRetryLogic, TestGhostPosition)
- `tests/conftest.py` - Added max_positions to sample_config; new mock_trading_client and plugin_data_dir fixtures
- `tests/test_config.py` - Added max_positions to REQUIRED_FIELDS; added test_max_positions_in_range

## Decisions Made
- loguru used for all logging — structured output essential for reviewing what an unattended trading bot did
- Conditional alpaca-py import (try/except APIError) enables testing RiskManager in environments without alpaca-py installed
- PDT rolling window uses 7 calendar days as specified in plan (plan spec takes precedence over risk-rules.md which says 5 business days)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_clamps_low_override: used wrong override value**
- **Found during:** Task 2 (GREEN phase — first test run)
- **Issue:** Test used size_override_pct=10.0 expecting lower clamp, but 10% > upper bound 7.5% so it clamps high (to 7.5%), not low. Test failed: expected 5 shares (2.5% of equity), got 15 shares (7.5% of equity).
- **Fix:** Changed override to 1.0 (below lower bound of 2.5%) so lower clamp activates — returns 5 shares correctly
- **Files modified:** tests/test_risk_manager.py
- **Verification:** All 24 tests pass GREEN after fix
- **Committed in:** a167591 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - test logic bug)
**Impact on plan:** Test accurately documents the lower clamp boundary behavior. No scope creep.

## Issues Encountered
- pytest not available system-wide — created a uv venv at /tmp/trading-bot-venv with pytest and loguru for test execution. This is expected (plugin deps install into CLAUDE_PLUGIN_DATA per SessionStart hook, not system-wide).

## Known Stubs
None — all RiskManager methods fully implemented with real logic. No placeholder data flows to consumers.

## Next Phase Readiness
- RiskManager is ready for Phase 3 (order execution) — all guard methods available via `from scripts.risk_manager import RiskManager`
- Phase 3 order submission must call: check_circuit_breaker(), check_position_count(), check_pdt_limit(), calculate_position_size(), submit_with_retry()
- circuit_breaker.flag and pdt_trades.json persistence works correctly via CLAUDE_PLUGIN_DATA

---
*Phase: 02-risk-management*
*Completed: 2026-03-22*
