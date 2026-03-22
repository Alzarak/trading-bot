---
phase: 04-build-command
plan: 02
subsystem: build
tags: [build-generator, deployment, env-template, gitignore, systemd, cron, run-sh, deploy-md]

# Dependency graph
requires:
  - phase: 04-01
    provides: "generate_build() function, core bot file generation, strategy filtering"
provides:
  - ".env.template generation with placeholder-only API keys"
  - ".gitignore generation excluding secrets and build artifacts"
  - "requirements.txt generation with runtime deps only (no rich)"
  - "run.sh bash launcher script sourcing .env and starting bot"
  - "DEPLOY.md with quick-start, cron, and systemd deployment instructions"
  - "Updated /build command with full deployment artifact guidance"
affects:
  - 05-run-command
  - 06-marketplace

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deployment artifact generation: all standalone artifacts produced by generate_build() in single call"
    - "Placeholder-only env template: ALPACA_API_KEY= with no value, never write actual keys"
    - "Runtime-only requirements.txt: strip dev/UI deps (rich) from standalone requirements"

key-files:
  created:
    - "scripts/build_generator.py (sections 4-8: .env.template, .gitignore, requirements.txt, run.sh, DEPLOY.md)"
    - ".planning/phases/04-build-command/04-02-SUMMARY.md"
  modified:
    - "scripts/build_generator.py"
    - "tests/test_build_generator.py"
    - "commands/build.md"

key-decisions:
  - ".env.template always writes ALPACA_PAPER=true regardless of config — user must explicitly set false for live trading"
  - "requirements.txt for standalone excludes rich — rich is only needed for the plugin wizard UI, not the autonomous bot"
  - "DEPLOY.md cron entry uses @reboot pattern (not scheduled interval) — APScheduler handles the internal loop, cron is only for restart-on-boot"
  - "run.sh uses 'source .env' (not python-dotenv) — simpler, no dependency, works in any shell environment"

patterns-established:
  - "generate_build() is the single entry point for all artifact generation — callers get the full standalone directory in one call"
  - "files_generated list tracks all outputs for reporting to users"

requirements-completed:
  - CMD-08
  - CMD-09
  - DIST-04
  - DIST-05

# Metrics
duration: 15min
completed: 2026-03-22
---

# Phase 04 Plan 02: Build Command Deployment Artifacts Summary

**generate_build() extended to produce .env.template, .gitignore, requirements.txt, run.sh, and DEPLOY.md — complete standalone deployment package with cron/systemd instructions and explicit secret-hygiene enforcement**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-22T01:40:00Z
- **Completed:** 2026-03-22T01:55:00Z
- **Tasks:** 2 (Task 1 TDD: RED + GREEN commits, Task 2: build.md update)
- **Files modified:** 3

## Accomplishments

- Extended `generate_build()` to write 5 new files: `.env.template`, `.gitignore`, `requirements.txt`, `run.sh`, `DEPLOY.md`
- Enforced secret hygiene: `.env.template` has `ALPACA_API_KEY=` with empty value — no actual keys ever written
- Added 11 new tests covering all deployment artifacts; all 21 tests pass
- Updated `/build` command to reference all deployment artifacts with complete security and paper trading guidance

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for deployment artifacts** - `34bf614` (test)
2. **Task 1 GREEN: Extend generate_build() with deployment artifacts** - `81708a9` (feat)
3. **Task 2: Update /build command with deployment guidance** - `c947788` (feat)

## Files Created/Modified

- `scripts/build_generator.py` - Added sections 4-8: .env.template, .gitignore, requirements.txt, run.sh, DEPLOY.md generation
- `tests/test_build_generator.py` - Added 11 new tests for deployment artifacts (tests 11-21)
- `commands/build.md` - Updated Next Steps section with complete deployment guidance including all artifact references, security reminder, and paper trading note

## Decisions Made

- `.env.template` always sets `ALPACA_PAPER=true` regardless of config — requires user explicit opt-in to live trading
- `requirements.txt` for standalone excludes `rich` — only needed for plugin wizard UI, not the autonomous bot
- `DEPLOY.md` cron entry uses `@reboot` pattern — APScheduler manages the internal loop, cron is for restart-on-boot only
- `run.sh` uses shell `source .env` — no extra dependency, works in any POSIX environment

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all tests passed on first GREEN implementation.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None — all generated artifacts produce real content. `.env.template` has intentional empty values for API keys (this is correct behavior, not a stub — users fill them in manually).

## Next Phase Readiness

- `generate_build()` now produces a complete standalone deployment package
- `/run` command (Phase 05) can use the same standalone directory to start the bot locally within Claude Code
- Phase 06 marketplace packaging can reference the deployment artifacts in documentation

## Self-Check: PASSED

- `scripts/build_generator.py` exists and contains all 5 new generation sections
- `tests/test_build_generator.py` contains 21 tests, all passing
- `commands/build.md` contains references to DEPLOY.md, .env.template, run.sh, .gitignore
- Commits 34bf614, 81708a9, c947788 all exist in git log

---
*Phase: 04-build-command*
*Completed: 2026-03-22*
