---
phase: 01-plugin-foundation
plan: "03"
subsystem: plugin-commands
tags: [claude-plugin, wizard, initialize, config-json, alpaca]

requires:
  - phase: 01-plugin-foundation
    plan: "01"
    provides: plugin scaffold, hooks, skill, reference files
  - phase: 01-plugin-foundation
    plan: "02"
    provides: config schema tests that define the contract wizard must produce

provides:
  - commands/initialize.md — /initialize wizard command prompt (183 lines)
  - Interactive experience-level-adaptive wizard (beginner/intermediate/expert)
  - config.json + .env written to CLAUDE_PLUGIN_DATA on completion

affects:
  - Phase 02 (/build command) — reads config.json written by this wizard
  - Phase 03 (/run command) — reads config.json written by this wizard

tech-stack:
  added: []
  patterns:
    - "Claude command as markdown prompt: commands/initialize.md with YAML frontmatter + wizard body"
    - "AskUserQuestion for interactive multi-step wizard in Claude Code commands"
    - "Bash heredoc to write files to CLAUDE_PLUGIN_DATA avoiding env-var expansion ambiguity"
    - "Experience-level branching: single first question determines all subsequent question complexity"

key-files:
  created:
    - commands/initialize.md

key-decisions:
  - "Wizard kept under 200 lines by deferring strategy details to references/trading-strategies.md (per Pitfall 6 from research)"
  - "Bash heredoc used for config.json write (not Write tool) to ensure CLAUDE_PLUGIN_DATA expands correctly"
  - "API keys stored in .env only — config.json security boundary explicit in wizard prompt"
  - "Equal weight distribution across selected strategies simplifies beginner UX"

patterns-established:
  - "Command-as-prompt: wizard logic is entirely in the markdown prompt body, no separate agent needed"
  - "Pre-check pattern: check for existing config before running wizard, honor --reset flag"
  - "Derive risk params from tolerance label: conservative/moderate/aggressive → position/loss pct"

requirements-completed: [CMD-01, CMD-02, CMD-03, CMD-04, CMD-05, CMD-12]

duration: 7min
completed: 2026-03-22
---

# Phase 01 Plan 03: /initialize Wizard Command Summary

**183-line wizard command that adapts to beginner/intermediate/expert experience levels, captures all 7 preference categories, and writes config.json + .env template to CLAUDE_PLUGIN_DATA**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-22T00:06:20Z
- **Completed:** 2026-03-22T00:13:00Z
- **Tasks:** 1 of 2 (Task 2 is human-verify checkpoint — awaiting verification)
- **Files modified:** 2 (commands/initialize.md created, commands/.gitkeep deleted)

## Accomplishments

- Created `commands/initialize.md` — the `/initialize` wizard command prompt (183 lines, under 250 limit)
- Wizard adapts all questions to experience level: beginners get guided defaults, experts get full parameter control
- Wizard captures all required config fields: experience_level, paper_trading, risk_tolerance, autonomy_mode, max_position_pct, max_daily_loss_pct, budget_usd, strategies, market_hours_only, watchlist, autonomy_level, config_version
- Strategy selection with per-strategy default params from references/trading-strategies.md
- Final step writes config.json + .env via Bash heredoc to CLAUDE_PLUGIN_DATA

## Task Commits

1. **Task 1: Create /initialize wizard command** - `3e1493b` (feat)
2. **Task 2: Verify wizard loads in Claude Code** - awaiting human verification

## Files Created/Modified

- `commands/initialize.md` — Complete /initialize wizard prompt (183 lines)
- `commands/.gitkeep` — Removed (placeholder no longer needed)

## Decisions Made

- Kept wizard under 200 lines by referencing `references/trading-strategies.md` for strategy descriptions, not inlining them (avoids Pitfall 6: prompt too long for context)
- Used Bash heredoc for config.json write to avoid CLAUDE_PLUGIN_DATA expansion ambiguity (per research open question #1)
- Equal weight distribution across selected strategies (1 strategy → weight 1.0, 2 → 0.5 each) for simple beginner UX
- Beginners forced to paper trading with no choice — live trading requires intermediate/expert explicit opt-in

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. The wizard prompt is complete and self-contained. All config.json fields and .env variables are covered.

## Issues Encountered

None.

## User Setup Required

None — this plan creates the wizard that guides users through their setup. The human checkpoint (Task 2) requires the user to run the wizard in Claude Code and verify it works correctly.

## Next Phase Readiness

- `/initialize` wizard command is complete and ready for human verification
- Once approved, downstream commands (/build, /run) can rely on config.json schema
- Phase 2 (/build) reads config.json written by this wizard — schema is fully specified

---
*Phase: 01-plugin-foundation*
*Completed: 2026-03-22*
