---
phase: 03-core-trading-loop
plan: 04
subsystem: trading-strategies
tags: [pandas-ta, signal-generation, momentum, mean-reversion, breakout, vwap, abc, registry-pattern]

requires:
  - phase: 03-core-trading-loop
    plan: 01
    provides: Signal dataclass in scripts/types.py and MarketScanner indicator column names

provides:
  - scripts/strategies/base.py — BaseStrategy(ABC) abstract base class
  - scripts/strategies/__init__.py — STRATEGY_REGISTRY mapping config names to classes
  - scripts/strategies/momentum.py — MomentumStrategy: RSI crossover + MACD + EMA + volume
  - scripts/strategies/mean_reversion.py — MeanReversionStrategy: lower BB + RSI oversold + within 2%
  - scripts/strategies/breakout.py — BreakoutStrategy: 20-bar high + 1.5x volume confirmation
  - scripts/strategies/vwap.py — VWAPStrategy: 1.5% VWAP deviation + RSI < 40 + 10-15 ET window
  - tests/test_strategies.py — 27 unit tests covering all 4 strategies and registry

affects:
  - 03-05-trading-loop (uses STRATEGY_REGISTRY to load strategies from config)
  - agents/market-analyst (strategy signal context)
  - skills/strategy-reference (signal documentation)

tech-stack:
  added: []
  patterns:
    - "BaseStrategy ABC in base.py (not __init__.py) to avoid circular imports — concrete classes import from base"
    - "STRATEGY_REGISTRY dict maps config names to classes — pluggable strategy selection at runtime"
    - "Column names derived programmatically from params dict (e.g. f'RSI_{params.get(rsi_period, 14)}') — never hardcoded"
    - "pandas-ta 0.4.71b0 BBands columns: BBL_{period}_{std}_{std} — std appears twice (quirk of beta)"
    - "ATRr_{period} not ATR_{period} — pandas-ta true range ratio naming"
    - "VWAP stop uses percentage formula (close * (1 - max_deviation_pct/100)) not ATR multiplier"
    - "Synthetic DataFrame fixtures with crafted indicator values for deterministic signal testing"

key-files:
  created:
    - scripts/strategies/base.py
    - scripts/strategies/__init__.py
    - scripts/strategies/momentum.py
    - scripts/strategies/mean_reversion.py
    - scripts/strategies/breakout.py
    - scripts/strategies/vwap.py
    - tests/test_strategies.py
  modified: []

key-decisions:
  - "BaseStrategy(ABC) placed in base.py (not __init__.py) to avoid circular import: concrete strategies import from base.py, __init__.py re-exports BaseStrategy"
  - "VWAP stop-loss uses percentage formula not ATR: VWAP trades have a known target (VWAP itself) and a clear invalidation level (max_deviation_pct further below entry)"
  - "Breakout uses prior bar's rolling max (iloc[-2]) not current bar — confirms breakout occurred vs measuring current bar's own level"
  - "MomentumStrategy requires RSI crossover (was below 30, now above) not just RSI > 30 — reduces false signals"

patterns-established:
  - "Strategy plugin pattern: class in individual module, inherit BaseStrategy, registered in STRATEGY_REGISTRY by config name"
  - "NaN guard on all indicator reads: return HOLD with 'Insufficient data' reasoning rather than raise exception"
  - "Missing columns guard: check required_cols before row access, return HOLD with column list"
  - "Minimal row count guard at top of generate_signal: return HOLD with 'need at least N rows' reasoning"

requirements-completed: [STRAT-01, STRAT-02, STRAT-03, STRAT-04, STRAT-05]

duration: 6min
completed: 2026-03-22
---

# Phase 03 Plan 04: Strategy Modules Summary

**Four pluggable trading strategies (momentum, mean reversion, breakout, VWAP) implemented as BaseStrategy ABC subclasses, registered by config name in STRATEGY_REGISTRY, returning Signal dataclasses with programmatically derived indicator column names**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-22T01:22:53Z
- **Completed:** 2026-03-22T01:28:54Z
- **Tasks:** 2 (1 create, 1 TDD test)
- **Files modified:** 7

## Accomplishments

- Created `scripts/strategies/` package with `BaseStrategy(ABC)` in `base.py` (separate from `__init__.py` to avoid circular imports)
- Implemented 4 strategy classes: `MomentumStrategy`, `MeanReversionStrategy`, `BreakoutStrategy`, `VWAPStrategy` — all inherit `BaseStrategy`, all produce `Signal` dataclasses
- `STRATEGY_REGISTRY` maps config names (`"momentum"`, `"mean_reversion"`, `"breakout"`, `"vwap"`) to classes for runtime selection from `config.json`
- 27 unit tests pass across `TestRegistry`, `TestMomentum`, `TestMeanReversion`, `TestBreakout`, and `TestVWAP` test classes

## Task Commits

Each task was committed atomically:

1. **Task 1: Create strategy package with BaseStrategy ABC and all 4 implementations** - `4095c0c` (feat)
2. **Task 2: BaseStrategy ABC inheritance + comprehensive strategy tests** - `8a03d3f` (feat)

_Note: Task 2 was TDD. RED (test written first), then GREEN (fix ABC inheritance), 27 tests pass._

## Files Created/Modified

- `scripts/strategies/base.py` — BaseStrategy(ABC) with abstract generate_signal() method
- `scripts/strategies/__init__.py` — STRATEGY_REGISTRY dict and re-export of BaseStrategy
- `scripts/strategies/momentum.py` — MomentumStrategy: RSI crossover above 30 + MACD histogram positive + EMA 9 > 21 + volume > 20-bar avg
- `scripts/strategies/mean_reversion.py` — MeanReversionStrategy: price at/below lower BB + RSI < 30 + within 2% of lower band
- `scripts/strategies/breakout.py` — BreakoutStrategy: price > prior 20-bar high + volume > 1.5x 20-bar avg
- `scripts/strategies/vwap.py` — VWAPStrategy: price > 1.5% below VWAP + RSI < 40 + 10:00-15:00 ET; percentage-based stop
- `tests/test_strategies.py` — 27 tests with synthetic DataFrames crafted to trigger specific BUY/SELL/HOLD signals (584 lines)

## Decisions Made

- `BaseStrategy(ABC)` in `base.py` (not `__init__.py`): concrete strategies need to inherit from `BaseStrategy`, but `__init__.py` also imports the concrete strategies — placing ABC in `__init__.py` creates a circular import. Separate `base.py` breaks the cycle cleanly.
- VWAP stop uses percentage formula: `close * (1 - max_deviation_pct / 100)` instead of `close - atr * multiplier`. Rationale: VWAP trades have a known, pre-defined invalidation level (further deviation from VWAP). ATR-based stop would be inconsistent with the strategy's mean-reversion logic.
- Breakout uses `rolling_high_max.iloc[-2]` (prior bar's max) to confirm the current bar has broken out — not `iloc[-1]` which would include the current bar's own price.
- Momentum requires RSI *crossover* (prev <= 30 AND current > 30), not just RSI > 30 — reduces false signals during sustained RSI levels above 30.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added base.py to enable BaseStrategy inheritance without circular imports**
- **Found during:** Task 2 (TDD RED phase — test_all_subclass_base failed)
- **Issue:** Plan specified `BaseStrategy(ABC)` in `__init__.py` and concrete strategies in separate files. This creates a circular import because `__init__.py` imports concrete classes, which would need to import `BaseStrategy` from `__init__.py`.
- **Fix:** Created `scripts/strategies/base.py` with `BaseStrategy(ABC)`. Concrete strategies import from `base.py`. `__init__.py` re-exports `BaseStrategy` from `base.py`.
- **Files modified:** `scripts/strategies/base.py` (new), `scripts/strategies/__init__.py` (restructured), all 4 strategy files (add inheritance)
- **Verification:** `test_all_subclass_base` and 26 other tests pass
- **Committed in:** `8a03d3f` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — architectural necessity for circular import avoidance)
**Impact on plan:** The fix preserves the plan's intended interface exactly. `BaseStrategy` is still exported from `scripts.strategies`, `STRATEGY_REGISTRY` still maps config names to classes. The only change is the file where `BaseStrategy` lives.

## Issues Encountered

- Test fixture `buy_momentum_df` initially set all volume to 200k, making the rolling average also 200k — the BUY condition `volume > vol_avg` became `200k > 200k = False`. Fixed by setting prior bars to 100k and only the last bar to 300k.
- VWAP test fixture created timestamps starting at midnight (00:00) in ET, not 11:00 as intended. `pd.Timestamp("2024-01-15", tz=ET)` defaults to midnight. Fixed by using `f"2024-01-15 {hour:02d}:00:00"` format in `make_datetime_index`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `STRATEGY_REGISTRY` is ready for the trading loop to load strategies from `config["strategies"]` by config name
- All 4 strategies accept `(df, symbol, params)` and return `Signal` — the trading loop can call them uniformly
- Signal's `stop_price` is pre-computed per strategy logic — order executor can use it directly for bracket orders
- No blockers. Phase 03-05 (trading loop orchestration) can proceed immediately.

---
*Phase: 03-core-trading-loop*
*Completed: 2026-03-22*
