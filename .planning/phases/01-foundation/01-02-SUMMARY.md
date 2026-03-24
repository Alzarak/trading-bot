---
phase: 01-foundation
plan: 02
subsystem: api
tags: [fmp, requests-cache, tenacity, sqlite, graceful-degradation, rate-limiting]

# Dependency graph
requires: []
provides:
  - FMPClient class with graceful degradation (D-01/D-02/D-03)
  - requests-cache SQLite-backed persistent HTTP caching
  - tenacity exponential backoff retry on 429/5xx
  - scripts/pipeline Python package initialized
affects:
  - 01-03-regime (RegimeDetector receives FMPClient instance)
  - Phase 2 screeners (VCP, earnings drift use FMPClient)

# Tech tracking
tech-stack:
  added:
    - requests>=2.31
    - requests-cache>=1.3.1 (SQLite CachedSession with per-URL TTL)
    - tenacity>=9.1.4 (retry decorator with exponential backoff)
  patterns:
    - "Graceful degradation guard: if not self._enabled: return None"
    - "Shared singleton FMPClient passed through pipeline (not instantiated per-module)"
    - "Per-endpoint TTL via urls_expire_after dict in CachedSession"
    - "_daily_calls increments only on non-cached responses (resp.from_cache check)"
    - "contextlib.suppress(Exception) as last-resort safety net in _get"

key-files:
  created:
    - scripts/pipeline/__init__.py
    - scripts/pipeline/fmp_client.py
  modified:
    - requirements.txt

key-decisions:
  - "No ValueError when FMP_API_KEY absent — set _enabled=False and return None (D-01/D-02)"
  - "tenacity @retry replaces manual time.sleep(60) retry from reference skill"
  - "requests-cache CachedSession replaces in-memory dict cache from reference skill"
  - "Per-URL TTL: treasury 6h, earnings-surprises 24h, historical/screener 5min, calendar 1h"

patterns-established:
  - "Pipeline package created at scripts/pipeline/ — all future pipeline modules go here"
  - "loguru logger throughout — no print(), sys.stderr, or time.sleep"
  - "Section delimiters: # ------------------------------------------------------------------"

requirements-completed: [FMP-01, FMP-02, FMP-03]

# Metrics
duration: 10min
completed: 2026-03-24
---

# Phase 01 Plan 02: FMP API Client Summary

**FMPClient class with SQLite-backed requests-cache, tenacity exponential backoff, and graceful degradation to None when FMP_API_KEY is absent**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-24T01:20:00Z
- **Completed:** 2026-03-24T01:30:58Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created `scripts/pipeline/` package with `FMPClient` class
- FMPClient instantiates without exception when `FMP_API_KEY` is absent (`_enabled=False`)
- All public methods return None immediately when disabled — no exceptions propagate to callers
- requests-cache `CachedSession` with SQLite backend provides persistent caching across bot restarts
- tenacity `@retry` on `_get` replaces manual `time.sleep(60)` with exponential backoff (4s/8s/16s, capped 60s, 3 attempts)
- `_daily_calls` only increments on non-cached responses (free tier 250/day monitoring)
- Three new dependencies added to requirements.txt

## Task Commits

Each task was committed atomically:

1. **Task 1: Add new dependencies to requirements.txt** - `f7ffab7` (chore)
2. **Task 2: Create FMPClient** - `65bc198` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `scripts/pipeline/__init__.py` - Pipeline package init with module index
- `scripts/pipeline/fmp_client.py` - FMPClient class (179 lines)
- `requirements.txt` - Added requests>=2.31, requests-cache>=1.3.1, tenacity>=9.1.4

## Decisions Made
- No ValueError raised when API key absent — sets `_enabled=False` and returns None (D-01/D-02 compliance)
- tenacity `@retry` with `reraise=False` means all 3 retry failures return None, not raise
- `contextlib.suppress(Exception)` inside `_get` is the outer safety net ensuring even unexpected errors return None
- Per-endpoint TTL values selected based on data staleness characteristics (treasury=6h, earnings=24h, prices=5min)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created missing scripts/pipeline/__init__.py**
- **Found during:** Task 2 (Create FMPClient)
- **Issue:** `scripts/pipeline/` directory did not exist; plan only specified creating `fmp_client.py` but the package `__init__.py` was needed for the import to work
- **Fix:** Created `scripts/pipeline/` directory and `__init__.py` with package docstring listing all planned modules
- **Files modified:** scripts/pipeline/__init__.py
- **Verification:** `from scripts.pipeline.fmp_client import FMPClient` exits 0
- **Committed in:** `65bc198` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for Python package import to work. No scope creep.

## Issues Encountered
- Project uses uv-managed `.venv/` but venv has no `pip` executable — used `uv pip install --python .venv/bin/python` to install dependencies into venv. Standard invocation works via `.venv/bin/python`.

## Known Stubs
None - all public methods are fully wired. Phase 2 endpoints (`get_earnings_surprises`, `get_stock_screener`) are implemented and functional; they are not stubs — they return real API data when `_enabled=True`.

## Next Phase Readiness
- `FMPClient` ready to be instantiated and passed to `RegimeDetector.__init__` in Plan 03
- When no key: all methods return None, regime defaults to `transitional/top_risk=30` (to be implemented in Plan 03)
- When key present: caching, retry, and rate monitoring all active
- No blockers for Plan 03

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
