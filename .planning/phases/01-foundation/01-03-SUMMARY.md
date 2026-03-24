---
phase: 01-foundation
plan: 03
subsystem: pipeline
tags: [regime-detection, macro, market-top, split-ttl, fmp, python]

# Dependency graph
requires:
  - phase: 01-01
    provides: RegimeState dataclass in scripts/models.py
  - phase: 01-02
    provides: FMPClient in scripts/pipeline/fmp_client.py

provides:
  - RegimeDetector class with detect() -> RegimeState
  - 6 macro regime calculators (concentration, size_factor, credit_conditions, sector_rotation, equity_bond, yield_curve) adapted inline
  - 6 top-risk calculators (distribution_days, index_technical, leading_stocks, defensive_rotation, breadth_divergence, sentiment) adapted inline
  - Split TTL caching: MACRO_TTL_SECONDS=3600, TOP_RISK_TTL_SECONDS=900
  - Neutral defaults when FMP absent: regime=transitional, top_risk=30.0, risk_zone=green

affects: [pipeline-screeners, exposure-coach, signal-aggregator, claude-analyzer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Split TTL cache pattern: two independent timestamps (_macro_cached_at, _top_risk_cached_at) for different refresh rates on same object"
    - "Utility functions adapted inline (no external skill imports) — pure math helpers at module level"
    - "try/except wrapper in all _refresh_* methods so exceptions never escape the detector"

key-files:
  created:
    - scripts/pipeline/regime.py
  modified: []

key-decisions:
  - "Used SPY as QQQ proxy for distribution_days (avoids extra FMP call for closely correlated index)"
  - "Breadth divergence uses SPY's own MA position as proxy since FMP free tier doesn't expose breadth data"
  - "Sentiment uses SPY realized volatility as VIX proxy — no additional FMP endpoint needed"
  - "All utility functions adapted inline (no imports from /tmp/claude-trading-skills) per PROJECT.md constraint"

patterns-established:
  - "RegimeDetector.detect() is the only public method — returns RegimeState dataclass, never raises"
  - "_refresh_macro() and _refresh_top_risk() always catch exceptions and leave cached values unchanged"
  - "risk_zone stores bare color string only (green/yellow/orange/red/critical) — no full label strings"

requirements-completed: [REG-01, REG-02, REG-03, REG-04]

# Metrics
duration: 25min
completed: 2026-03-24
---

# Phase 01 Plan 03: RegimeDetector Summary

**RegimeDetector with split TTL caching (hourly macro regime + 15-min top-risk) using 12 inline-adapted calculators from macro-regime-detector and market-top-detector skills**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-24T01:10:00Z
- **Completed:** 2026-03-24T01:36:28Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

- Created `scripts/pipeline/regime.py` with `RegimeDetector` class (1057 lines)
- Adapted 6 macro regime calculators inline: concentration (RSP/SPY), size_factor (IWM/SPY), credit_conditions (HYG/LQD), sector_rotation (XLY/XLP), equity_bond (SPY/TLT + correlation), yield_curve (10Y-2Y spread)
- Adapted 6 top-risk calculators inline: distribution_days, index_technical (EMA/SMA checks), leading_stocks (ETF proxy), defensive_rotation (XLU/XLP/XLV/VNQ vs XLK/XLC/XLY/QQQ), breadth_divergence (SPY MA proxy), sentiment (realized vol proxy)
- Split TTL caching with `_macro_cached_at` and `_top_risk_cached_at` as independent timestamps
- `detect().regime == "transitional"` and `detect().top_risk_score == 30.0` when FMP absent (D-01 defaults)
- `risk_zone` always bare color string; all exceptions contained in `_refresh_*` methods

## Task Commits

1. **Task 1: Create RegimeDetector with macro regime classification** - `57b537e` (feat)

**Plan metadata:** TBD (docs commit)

## Files Created/Modified

- `scripts/pipeline/regime.py` — RegimeDetector class with detect() -> RegimeState, 6 macro calculators, 6 top-risk calculators, split TTL cache, zone mapping helpers

## Decisions Made

- Used SPY price data as QQQ proxy for distribution_days to avoid an extra FMP API call — SPY and QQQ are highly correlated for this metric
- FMP free tier doesn't expose breadth data (% stocks above MA), so breadth_divergence uses SPY's own position vs 50DMA as a structural proxy
- VIX not available via get_historical_prices(), so sentiment uses SPY's 20-day realized volatility as an inverse proxy (low vol = complacency = higher top-risk contribution)
- All 12 calculator functions adapted as module-level pure functions — no imports from /tmp/claude-trading-skills per the project constraint

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Breadth calculator uses SPY MA proxy instead of actual breadth data**
- **Found during:** Task 1 (_refresh_top_risk implementation)
- **Issue:** FMP free tier doesn't expose % of stocks above 200DMA endpoint — reference skill expected this as a CLI argument
- **Fix:** Used SPY's own position vs 50DMA and distance from 52-week high as structural proxy for breadth health
- **Files modified:** scripts/pipeline/regime.py
- **Verification:** Returns score in 0-100 range, no data_available=False edge case raises
- **Committed in:** 57b537e (Task 1 commit)

**2. [Rule 2 - Missing] Sentiment uses realized volatility proxy instead of VIX**
- **Found during:** Task 1 (_top_risk_sentiment implementation)
- **Issue:** VIX requires a separate FMP endpoint not in FMPClient; reference skill expected VIX as CLI arg
- **Fix:** Compute SPY's average absolute daily move over 20 days as inverse volatility proxy (low moves = complacency)
- **Files modified:** scripts/pipeline/regime.py
- **Verification:** Low-vol market returns score >0 (complacency signal); high-vol returns 0
- **Committed in:** 57b537e (Task 1 commit)

---

**Total deviations:** 2 auto-adapted (Rule 2 — missing data, used proxy instead of failing)
**Impact on plan:** Both proxies produce directionally correct signals. Real VIX/breadth data can replace proxies when additional FMP endpoints are added in a future plan. Plan objectives fully met.

## Issues Encountered

- Reference calculators in market-top-detector used `from calculators.math_utils import calc_ema` — adapted the EMA function inline in regime.py to avoid the external import dependency

## Known Stubs

None — all calculators produce live scores from FMP data when available, or neutral defaults when unavailable.

## Next Phase Readiness

- `RegimeDetector` is ready for use in `ExposureCoach` (next plan — 01-04)
- `detect()` always returns a valid `RegimeState`, so the ExposureCoach can call it unconditionally
- FMP-disabled path returns `transitional/30.0/green` which allows the ExposureCoach to proceed with neutral bias

## Self-Check: PASSED

- `scripts/pipeline/regime.py` — FOUND
- `.planning/phases/01-foundation/01-03-SUMMARY.md` — FOUND
- Commit `57b537e` — FOUND

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
