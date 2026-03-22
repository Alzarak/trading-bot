---
phase: 04-build-command
plan: 01
subsystem: build
tags: [python, code-generation, strategies, alpaca, import-rewriting]

# Dependency graph
requires:
  - phase: 03-core-trading-loop
    provides: scripts/bot.py, scripts/strategies/, scripts/types.py and all supporting modules

provides:
  - /build slash command (commands/build.md) that generates standalone trading bot directories
  - scripts/build_generator.py with generate_build() for config-driven standalone script generation
  - Strategy filtering — only selected strategies appear in output
  - Import rewriting — output files use relative imports (not from scripts.)
  - tests/test_build_generator.py with 10 tests covering all generation scenarios

affects: [05-run-command, 06-publish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Import rewriting via str.replace('from scripts.', 'from ') for standalone generation"
    - "Dynamic __init__.py generation with filtered STRATEGY_REGISTRY"
    - "Config-driven code generation pattern: /build reads config, generator produces artifacts"

key-files:
  created:
    - scripts/build_generator.py
    - commands/build.md
    - tests/test_build_generator.py
  modified: []

key-decisions:
  - "Simple str.replace('from scripts.', 'from ') used for import rewriting — safe because all source files consistently use 'from scripts.X' for cross-module imports"
  - "Generated strategies/__init__.py is built dynamically (not copied) to contain only selected strategy entries in STRATEGY_REGISTRY"
  - "Generated bot.py load_config() stripped of CLAUDE_PLUGIN_DATA fallback — standalone version always reads from cwd"

patterns-established:
  - "Build generator pattern: locate source scripts relative to __file__, rewrite and copy"
  - "Strategy filtering: iterate config['strategies'][*]['name'] against STRATEGY_CLASS_MAP"

requirements-completed: [CMD-06, CMD-07]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 4 Plan 01: Build Command Summary

**Config-driven standalone bot generator with strategy filtering and import rewriting — /build produces a self-contained directory ready to run on any server**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-22T01:48:51Z
- **Completed:** 2026-03-22T01:52:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `generate_build()` copies all trading bot scripts with imports rewritten from `from scripts.X` to `from X`
- Strategy filtering: only strategies selected in config appear in the output directory (not all 4)
- Dynamic `strategies/__init__.py` generation with filtered `STRATEGY_REGISTRY` containing only selected strategies
- `/build` slash command with pre-check, generator invocation, results reporting, and next-steps guidance
- 10 tests covering all generation scenarios including edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests** - `e37cf1a` (test)
2. **Task 1 (GREEN): Implement build generator** - `6794bb9` (feat)
3. **Task 2: Add /build slash command** - `4d7ad72` (feat)

## Files Created/Modified

- `scripts/build_generator.py` — generate_build() function; reads scripts/ source files, rewrites imports, filters strategies, generates dynamic __init__.py, writes config.json
- `commands/build.md` — /build slash command: pre-checks config.json, runs generator, reports results, provides deployment next steps
- `tests/test_build_generator.py` — 10 tests: core files created, strategy filtering (both partial and all-4), __init__.py registry filtering, relative imports, cwd config reading, no hardcoded keys, return dict structure, config.json written, strategies_included accuracy

## Decisions Made

- Simple `str.replace("from scripts.", "from ")` used for import rewriting — safe and sufficient because all source files use this consistent pattern
- Generated `strategies/__init__.py` is constructed dynamically (not copied) using a string template, enabling precise filtering of STRATEGY_REGISTRY to only selected strategies
- `load_config()` in generated `bot.py` is rewritten to remove the `CLAUDE_PLUGIN_DATA` fallback — standalone version always reads from cwd where the user placed the directory

## Deviations from Plan

None - plan executed exactly as written. TDD executed as specified: RED commit → GREEN commit.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- `/build` command is fully functional: config.json → standalone directory with selected strategies only
- `generate_build()` is importable and testable independently of Claude Code runtime
- Ready for Phase 04 Plan 02 (deployment artifacts: .env.template, requirements.txt, .gitignore, DEPLOY.md)

---
*Phase: 04-build-command*
*Completed: 2026-03-22*
