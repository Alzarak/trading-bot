---
phase: 01-foundation
plan: 04
subsystem: pipeline
tags: [exposure-coaching, regime-gating, config, position-sizing]

# Dependency graph
requires:
  - phase: 01-01
    provides: RegimeState and ExposureDecision dataclasses in scripts/models.py
  - phase: 01-03
    provides: RegimeDetector and RegimeState production data via scripts/pipeline/regime.py

provides:
  - ExposureCoach class with evaluate() method in scripts/pipeline/exposure.py
  - REGIME_SCORES dict mapping regime labels to numeric scores
  - Pipeline configuration section in config.json with regime_gating thresholds
  - Configurable gating thresholds via config.pipeline.regime_gating

affects:
  - Phase 02 screeners (consumes ExposureDecision.bias to gate BUY signals)
  - Phase 02 sizer (reads position_size_multiplier from ExposureDecision)
  - Any code that instantiates ExposureCoach (reads config.pipeline.regime_gating)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ExposureCoach reads gating thresholds from config dict at __init__ (not hardcoded)"
    - "Bias literals are bot-spec: risk_on/neutral/risk_off/SELL_ONLY — NOT reference values"
    - "evaluate() returns ExposureDecision without raising; all error paths return valid objects"

key-files:
  created:
    - scripts/pipeline/exposure.py
    - config.json
  modified: []

key-decisions:
  - "config.json is gitignored by design (generated per-user by /initialize, may contain API key refs) — pipeline section created on disk but not tracked in git"
  - "Linear size scaling in top_risk 41-69 uses block_buys_top_risk_above as upper bound (not hardcoded 69) so threshold is fully configurable"
  - "Contraction regime size_mult computed as (100 - contraction_pct) / 100 — keeps formula configurable"

patterns-established:
  - "REGIME_SCORES module-level dict maps regime label strings to integer scores for exposure ceiling and bias calculation"
  - "Gating priority: top_risk block -> exposure ceiling block -> regime-based sizing"

requirements-completed: [EXP-01, EXP-02, EXP-03, EXP-04]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 01 Plan 04: Exposure Coach Summary

**ExposureCoach class gating entries by top_risk threshold (>=70 -> SELL_ONLY), contraction regime (0.5x size), linear reduction in 41-69 range, and exposure ceiling — all thresholds configurable via config.pipeline.regime_gating**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-24T01:38:40Z
- **Completed:** 2026-03-24T01:41:27Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implemented ExposureCoach with all four gating rules: EXP-02 (top_risk block), EXP-03 (contraction halving), D-08 (linear 41-69 range), EXP-04 (exposure ceiling)
- Created config.json with pipeline section including regime_gating, screeners, position sizing params
- Passed full Phase 1 integration check: no-FMP defaults produce regime=transitional, top_risk=30, bias=neutral, mult=1.0

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ExposureCoach with regime gating logic** - `d2b9f4d` (feat)
2. **Task 2: Add pipeline section to config.json** - not committed (config.json gitignored by design)

## Files Created/Modified

- `scripts/pipeline/exposure.py` - ExposureCoach class with REGIME_SCORES, four gating rules, configurable thresholds
- `config.json` - Pipeline configuration section with regime_gating (block_buys_top_risk_above=70, reduce_size_contraction_pct=50), screeners, min_conviction, position sizing params (exists on disk, gitignored)

## Decisions Made

- config.json is gitignored by design (generated per-user, may contain API key refs) — the pipeline section was added to the on-disk file and verified, but the file is not tracked in git. This is the expected behavior per project design.
- Linear scaling upper bound uses `self._block_buys_above` not hardcoded 69, ensuring the configurable threshold is honored end-to-end.
- Bias output strictly uses bot-spec literals (`risk_on`/`neutral`/`risk_off`/`SELL_ONLY`) — the reference skill's `GROWTH`/`VALUE`/`DEFENSIVE`/`NEUTRAL` values were not used.

## Deviations from Plan

None - plan executed exactly as written. config.json not committed because it's intentionally gitignored by project design (`.gitignore` has `/config.json`).

## Issues Encountered

- `python` command not found on host — used venv (`source .venv/bin/activate`) for all verification commands. Not a code issue.
- config.json was gitignored — acknowledged this as designed behavior (per `.gitignore` comment: "MCP server config created by /initialize"). File exists on disk and passes all verification.

## Known Stubs

None - ExposureCoach.evaluate() returns fully populated ExposureDecision with real gating logic for all four scenarios.

## User Setup Required

None - no external service configuration required. FMP API key is optional; without it the pipeline uses neutral defaults.

## Next Phase Readiness

- ExposureCoach is importable from `scripts.pipeline.exposure`
- Full Phase 1 pipeline (FMPClient -> RegimeDetector -> ExposureCoach) runs end-to-end with neutral defaults when FMP key absent
- Phase 2 screeners can consume ExposureDecision.bias and position_size_multiplier
- config.json pipeline.screeners.technical.enabled=true signals the Phase 2 technical screener is the active entry point

## Self-Check: PASSED

- FOUND: scripts/pipeline/exposure.py
- FOUND: config.json (on disk; gitignored by design)
- FOUND: .planning/phases/01-foundation/01-04-SUMMARY.md
- FOUND: commit d2b9f4d (Task 1 feat commit)

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
