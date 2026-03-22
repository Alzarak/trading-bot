---
phase: 01-plugin-foundation
plan: 01
subsystem: infra
tags: [python, alpaca-py, uv, pytest, plugin, hooks, bash]

# Dependency graph
requires: []
provides:
  - Plugin manifest (.claude-plugin/plugin.json) declaring trading-bot v0.1.0
  - SessionStart hook (hooks/hooks.json) wired to install-deps.sh
  - SHA256 hash-based dependency install script (scripts/install-deps.sh) with Python 3.12+ and uv checks
  - requirements.txt pinning alpaca-py==0.43.2, pandas-ta==0.4.71b0, APScheduler<4.0
  - Plugin component directories: commands/, agents/, skills/, references/, hooks/, scripts/
  - Test infrastructure (tests/conftest.py, tests/test_hook.py) with 19 passing tests
affects: [02-plugin-foundation, 03-plugin-foundation, all future phases requiring plugin scaffold]

# Tech tracking
tech-stack:
  added:
    - alpaca-py==0.43.2 (pinned in requirements.txt)
    - pandas-ta==0.4.71b0 (pinned in requirements.txt)
    - APScheduler>=3.10,<4.0 (capped below 4.x alpha rewrite)
    - pydantic-settings>=2.0
    - loguru>=0.7
    - uv (runtime dep installer for SessionStart hook)
    - pytest (test framework)
  patterns:
    - SHA256 hash comparison for dependency change detection (skip reinstall if unchanged)
    - CLAUDE_PLUGIN_ROOT for read-only plugin files, CLAUDE_PLUGIN_DATA for persistent user data
    - PATH expansion in hook scripts to find uv in ~/.cargo/bin and ~/.local/bin

key-files:
  created:
    - .claude-plugin/plugin.json
    - hooks/hooks.json
    - scripts/install-deps.sh
    - requirements.txt
    - tests/conftest.py
    - tests/test_hook.py
    - commands/.gitkeep
    - agents/.gitkeep
    - skills/.gitkeep
    - references/.gitkeep
  modified: []

key-decisions:
  - "ALP-04 (MCP server) dropped per user decision — all Alpaca access via alpaca-py SDK only"
  - "uv used for dependency installation — not pip — for speed consistency with broader tooling"
  - "SHA256 hash-based reinstall detection — not timestamps — content hash is definitive across plugin updates"
  - "Python 3.12+ version check added to install script — hard floor from pandas-ta 0.4.71b0 requirement"

patterns-established:
  - "Pattern 1: Hook scripts must expand PATH to include ~/.cargo/bin and ~/.local/bin for uv"
  - "Pattern 2: All user-written files go in ${CLAUDE_PLUGIN_DATA}, never ${CLAUDE_PLUGIN_ROOT}"
  - "Pattern 3: Plugin component directories (commands/, agents/, skills/) live at plugin root, not inside .claude-plugin/"

requirements-completed: [PLUG-01, PLUG-06, ALP-04]

# Metrics
duration: 3min
completed: 2026-03-21
---

# Phase 01 Plan 01: Plugin Foundation Scaffold Summary

**Claude Code plugin scaffold with SHA256-gated uv dependency installer, alpaca-py 0.43.2 pinned in requirements.txt, and 19-test pytest suite covering hook logic and manifest structure**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-21T23:58:44Z
- **Completed:** 2026-03-21T23:59:58Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Created full plugin directory structure with .claude-plugin/plugin.json manifest (trading-bot v0.1.0)
- Implemented SessionStart hook that uses SHA256 to skip unnecessary reinstalls and validates Python 3.12+ and uv availability
- Built 19-test pytest suite covering install-deps.sh logic, hooks.json structure, plugin manifest, and requirements.txt content

## Task Commits

1. **Task 1: Create plugin scaffold and SessionStart hook** - `c4c0595` (feat)
2. **Task 2: Create test infrastructure and hook tests** - `8905b1b` (test)

## Files Created/Modified

- `.claude-plugin/plugin.json` - Plugin manifest with name, version, description, keywords
- `hooks/hooks.json` - SessionStart hook pointing to install-deps.sh via CLAUDE_PLUGIN_ROOT
- `scripts/install-deps.sh` - Bash script: SHA256 hash check, Python 3.12+ validation, uv venv creation, pip install
- `requirements.txt` - Pinned alpaca-py==0.43.2, pandas-ta==0.4.71b0, APScheduler>=3.10,<4.0, plus 5 other deps
- `tests/conftest.py` - Shared pytest fixtures for plugin_root, plugin_data, sample_config, env_template
- `tests/test_hook.py` - 19 tests across 4 classes: TestInstallDepsScript, TestHooksJson, TestPluginManifest, TestRequirementsTxt
- `commands/.gitkeep`, `agents/.gitkeep`, `skills/.gitkeep`, `references/.gitkeep` - Placeholder dirs

## Decisions Made

- ALP-04 (Alpaca MCP server) is dropped per user decision from planning phase — SDK-only approach documented in manifest
- Used `uv pip install` over plain pip for consistency with broader tooling stack
- Added PATH expansion (`~/.cargo/bin:~/.local/bin`) in hook script per research pitfall 3 about restricted PATH in hook processes
- Python version check uses grep pattern matching rather than python3 --version direct comparison to handle edge cases

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `python -m pytest` failed because pytest is not installed system-wide. Resolved by using `uv venv` + `uv pip install pytest` to create a temporary test venv. The verify step runs fine with that venv. Note: The plan's verify command `python -m pytest tests/ -x -q` requires pytest to be installed in the active Python environment; users should run via the plugin's own venv after SessionStart hook fires.

## Known Stubs

None - this plan establishes scaffold structure only. No data flows, no UI, no runtime logic yet.

## User Setup Required

None - no external service configuration required for this plan. Python 3.12+ and uv must be installed before the SessionStart hook runs (checked in install-deps.sh with clear error messages).

## Next Phase Readiness

- Plugin scaffold complete — Plans 02 and 03 can build on top of this structure
- commands/, agents/, skills/, references/ directories exist and ready to be populated
- requirements.txt is the authoritative dependency list for all subsequent Python phases
- Test infrastructure established — future plans add tests to the same tests/ directory

---
*Phase: 01-plugin-foundation*
*Completed: 2026-03-21*

## Self-Check: PASSED

All created files verified present. All task commits verified in git log.
