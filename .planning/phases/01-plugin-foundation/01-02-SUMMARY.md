---
phase: 01-plugin-foundation
plan: 02
subsystem: knowledge
tags: [trading, alpaca, risk-management, skills, references, pytest, config-schema]

# Dependency graph
requires: []
provides:
  - "skills/trading-rules/SKILL.md — auto-loaded domain context for all trading conversations"
  - "references/trading-strategies.md — 4 strategies with signal logic and default parameters"
  - "references/risk-rules.md — circuit breaker, position sizing, PDT, autonomy modes"
  - "references/alpaca-api-patterns.md — alpaca-py SDK code patterns with idempotency"
  - "tests/test_config.py — config schema contract (20 tests)"
  - "tests/test_env_template.py — .env template contract (6 tests)"
affects: [01-03, 02-agents, 03-trading-loop, 04-scripts]

# Tech tracking
tech-stack:
  added: [pytest]
  patterns:
    - "Skill files use user-invocable=false for auto-loaded domain context"
    - "Reference files serve as both human docs and @-context for agents"
    - "Config schema tests define the wizard contract before wizard is built"
    - "conftest.py sample_config fixture is the canonical valid config shape"

key-files:
  created:
    - skills/trading-rules/SKILL.md
    - references/trading-strategies.md
    - references/risk-rules.md
    - references/alpaca-api-patterns.md
    - tests/test_config.py
    - tests/test_env_template.py
    - .gitignore
  modified: []

key-decisions:
  - "Trading-rules skill set to user-invocable=false — auto-loads on trading topics without polluting /skill menu"
  - "Config schema tests written before wizard (Plan 03) — tests define the contract the wizard must satisfy"
  - "REQUIRED_FIELDS dict in test_config.py is the canonical list of all wizard-produced config fields"
  - "Installed pytest via uv into .venv — python3.12 present but no pip/pytest; uv resolves this cleanly"

patterns-established:
  - "Skill YAML frontmatter: name, description (multi-sentence trigger guidance), user-invocable"
  - "Reference files use H2/H3 sections with tables and code blocks — scannable by agents"
  - "Test constants (REQUIRED_FIELDS, VALID_STRATEGY_NAMES) are module-level — serve as living schema docs"
  - "pytest fixtures in conftest.py provide canonical valid data shapes for all schema tests"

requirements-completed: [PLUG-05, PLUG-08, STATE-03, ALP-01, ALP-02, ALP-03]

# Metrics
duration: 5min
completed: 2026-03-21
---

# Phase 01 Plan 02: Domain Knowledge Layer Summary

**Auto-loaded trading-rules skill, 4-strategy reference suite with ATR/PDT/circuit-breaker risk rules, alpaca-py SDK patterns, and 26 config/env schema tests defining the wizard contract**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-21T23:58:59Z
- **Completed:** 2026-03-21T23:59:51Z
- **Tasks:** 2
- **Files created:** 7

## Accomplishments

- Created `skills/trading-rules/SKILL.md` with `user-invocable: false` — covers market hours, position sizing, PDT rule, risk controls, Alpaca API conventions, strategy framework, and Claude's role as analyst-only
- Created 3 reference files: trading-strategies.md (4 strategies with signal logic and default params), risk-rules.md (circuit breaker, position sizing, stop-loss, PDT, autonomy modes), alpaca-api-patterns.md (alpaca-py SDK patterns including bracket orders, retry, and ghost position prevention)
- Created 26 new tests (test_config.py + test_env_template.py) that define the config schema contract the wizard (Plan 03) must satisfy — all 45 tests in the suite pass green

## Task Commits

Each task was committed atomically:

1. **Task 1: Create trading-rules skill and reference files** - `2457290` (feat)
2. **Task 2: Create config schema validation tests** - `9037eec` (feat)

## Files Created/Modified

- `skills/trading-rules/SKILL.md` — Auto-loaded skill with 7 domain rule sections
- `references/trading-strategies.md` — Momentum, mean reversion, breakout, VWAP strategies with entry/exit conditions and default parameters
- `references/risk-rules.md` — Circuit breaker, position sizing, stop-loss, PDT protection, order safety, autonomy modes
- `references/alpaca-api-patterns.md` — Auth, historical data, market clock, order submission (bracket/trailing), account info, position management, error handling
- `tests/test_config.py` — TestConfigSchema (17 tests) + TestPaperVsLiveMode (3 tests)
- `tests/test_env_template.py` — TestEnvTemplate (6 tests)
- `.gitignore` — Excludes .venv, __pycache__, .env, and generated runtime files

## Decisions Made

- **user-invocable=false on skill:** Hides from /skill menu while keeping description in Claude's context for auto-loading — correct pattern for domain context skills
- **Tests before wizard:** Config schema tests (Plan 02) written before the wizard (Plan 03) — the tests define what the wizard must produce, enabling test-driven wizard development
- **pytest via uv:** No system pip available; installed pytest with `uv pip install pytest --python .venv/bin/python` — consistent with project's uv-first approach
- **REQUIRED_FIELDS as module constant:** Makes the test file self-documenting as the schema source of truth

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added .gitignore**
- **Found during:** Task 2 (setting up test infrastructure)
- **Issue:** uv created a `.venv` directory in the project root with no .gitignore to exclude it. Untracked .venv would be committed if not excluded.
- **Fix:** Created `.gitignore` covering .venv, __pycache__, .env, pytest cache, and generated plugin runtime files
- **Files modified:** .gitignore
- **Verification:** `git status` shows .venv as ignored, not untracked
- **Committed in:** 9037eec (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — .gitignore)
**Impact on plan:** Necessary to prevent accidental venv commit. No scope creep.

## Issues Encountered

- `python` and `pip3` commands not available system-wide; `python3.12` present but without pip module. Resolved by installing pytest via `uv pip install` into a local `.venv` — consistent with project's uv-first strategy and SessionStart hook pattern.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — all files are complete knowledge documents, not stubs. Reference files document actual strategies, risk rules, and API patterns. Tests validate a real config shape.

## Next Phase Readiness

- Trading-rules skill is ready to auto-load in all agent and command contexts
- All reference files available for @-reference in Plan 03 wizard command
- Config schema tests define the exact contract Plan 03 must satisfy
- 45 tests pass green — no regressions from Plan 01 test suite

---
*Phase: 01-plugin-foundation*
*Completed: 2026-03-21*
