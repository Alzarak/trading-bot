---
phase: 03-core-trading-loop
plan: "01"
subsystem: market-scanner
tags: [indicators, pandas-ta, alpaca-data, signal-contract, rsi, macd, ema, atr, bbands, vwap]
dependency_graph:
  requires: []
  provides: [scripts/types.py, scripts/market_scanner.py]
  affects: [scripts/strategy_engine.py, scripts/order_executor.py, scripts/bot.py]
tech_stack:
  added: [pandas-ta==0.4.71b0]
  patterns:
    - "df.ta.* accessor pattern for all indicator computation (requires pandas_ta import)"
    - "try/except alpaca-py import for testability without SDK installed"
    - "ZoneInfo('America/New_York') for all ET timezone operations"
    - "dropna() after all indicators to remove rolling window warmup NaN rows"
key_files:
  created:
    - scripts/types.py
    - scripts/market_scanner.py
    - tests/test_market_scanner.py
    - pytest.ini
  modified: []
decisions:
  - "pandas_ta must be imported explicitly (not just alpaca-py) to register df.ta accessor on DataFrames"
  - "pandas-ta 0.4.71b0 BBands columns use BBL_{period}_{std}_{std} format (std appears twice) — not BBL_{period}_{std}"
  - "get_indicator_columns() uses ATRr_{period} (not ATR_{period}) — prevents column-name mismatch in strategy modules"
  - "pytest.ini with pythonpath=. added to resolve scripts module in tests — was missing and blocked all test imports"
metrics:
  duration_seconds: 292
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 03 Plan 01: Market Scanner and Signal Contract Summary

**One-liner:** Signal dataclass and MarketScanner with 6 pandas-ta indicators (RSI, MACD, EMA, ATR, BBands, VWAP) via Alpaca IEX feed — tested with 12 passing unit tests.

## Objective

Create the shared Signal dataclass contract and the MarketScanner module that fetches OHLCV bars from Alpaca and computes all 6 technical indicators via pandas-ta. This is the data pipeline foundation for all strategy and execution modules.

## What Was Built

### scripts/types.py

Signal dataclass with 7 fields: `action` (BUY/SELL/HOLD literal), `confidence` (0-1 float), `symbol`, `strategy`, `atr`, `stop_price`, `reasoning`. Used by all downstream modules as the trade decision contract.

### scripts/market_scanner.py

`MarketScanner` class with:
- `compute_indicators(df)` — appends RSI, MACD (3 columns), EMA x2, ATR, BBands (3 columns), VWAP via `df.ta.*` API; drops NaN rows
- `fetch_bars(symbol, days_back)` — fetches OHLCV minute bars from Alpaca IEX feed with ET-aware DatetimeIndex
- `scan(symbol)` — combines fetch + indicators, returns empty DataFrame on error
- `is_market_open()` — delegates to Alpaca market clock
- `get_indicator_columns()` — safe logical-to-column-name mapping preventing hard-coded names in strategy modules
- `_ensure_tz_aware(df)` — handles naive, UTC, or non-ET indexes for VWAP compatibility

### tests/test_market_scanner.py

12 tests across 3 classes: `TestIndicators` (8 tests), `TestMarketClock` (2 tests), `TestGetIndicatorColumns` (2 tests). All use mocked Alpaca clients with no real API calls.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create Signal dataclass and MarketScanner module | c46d54a | scripts/types.py, scripts/market_scanner.py |
| 2 | Write tests for MarketScanner and all 6 indicators | dd037a9 | tests/test_market_scanner.py, pytest.ini |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pandas_ta import missing from market_scanner.py**
- **Found during:** Task 2 (RED phase — tests collected but accessor unavailable)
- **Issue:** `df.ta.*` accessor raises `AttributeError: DataFrame object has no attribute 'ta'` unless `pandas_ta` is explicitly imported first — the accessor registers itself at import time
- **Fix:** Added `import pandas_ta  # noqa: F401` to market_scanner.py
- **Files modified:** scripts/market_scanner.py
- **Commit:** dd037a9

**2. [Rule 1 - Bug] BBands column name format incorrect for pandas-ta 0.4.71b0**
- **Found during:** Task 2 (RED phase — `BBL_20_2.0` column not found)
- **Issue:** pandas-ta 0.4.71b0 names Bollinger Band columns `BBL_{period}_{std}_{std}` (std appears twice, e.g. `BBL_20_2.0_2.0`) — plan spec shows `BBL_20_2.0`
- **Fix:** Updated `get_indicator_columns()` to use `BBL_{bb}_{bb_std}_{bb_std}` format; updated tests to match actual column names
- **Files modified:** scripts/market_scanner.py, tests/test_market_scanner.py
- **Commit:** dd037a9

**3. [Rule 3 - Blocking] pytest.ini missing — scripts module not resolvable in tests**
- **Found during:** Task 2 (RED phase — `ModuleNotFoundError: No module named 'scripts'`)
- **Issue:** No `pytest.ini` or `pyproject.toml` with `pythonpath` setting — pytest could not find the `scripts` module. Existing tests (test_risk_manager.py) had the same issue.
- **Fix:** Created `pytest.ini` with `pythonpath = .` (pytest 7+ standard)
- **Files modified:** pytest.ini (new)
- **Commit:** dd037a9

## Decisions Made

1. `pandas_ta` must be imported explicitly — the `df.ta` accessor registration is a side effect of import, not from alpaca-py
2. pandas-ta 0.4.71b0 BBands column naming quirk: `BBL_{period}_{std}_{std}` — document in `get_indicator_columns()` comment
3. `get_indicator_columns()` provides the single source of truth for all downstream column lookups — strategy modules must use this rather than hardcoding column names
4. `pytest.ini` added to project root — fixes module resolution for all current and future tests

## Known Stubs

None — all code is fully wired. `scan()` returns empty DataFrame on error (not stub behavior — this is correct defensive design).

## Self-Check: PASSED

Files created:
- FOUND: scripts/types.py
- FOUND: scripts/market_scanner.py
- FOUND: tests/test_market_scanner.py
- FOUND: pytest.ini

Commits verified:
- FOUND: c46d54a (feat(03-01): create Signal dataclass and MarketScanner module)
- FOUND: dd037a9 (feat(03-01): add tests for MarketScanner and all 6 indicators (TDD))
