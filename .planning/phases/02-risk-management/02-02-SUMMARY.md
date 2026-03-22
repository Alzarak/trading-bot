---
phase: 02-risk-management
plan: "02"
subsystem: infra
tags: [bash, hooks, claude-code-plugins, PreToolUse, circuit-breaker, PDT, agents]

# Dependency graph
requires:
  - phase: 02-01
    provides: circuit_breaker.flag written by RiskManager._persist_circuit_breaker()
  - phase: 01-plugin-foundation
    provides: hooks/hooks.json with SessionStart entry to preserve

provides:
  - PreToolUse safety hook that intercepts order-submission Bash commands
  - hooks/validate-order.sh with JSON permissionDecision deny format
  - Updated hooks/hooks.json with PreToolUse entry targeting Bash matcher
  - agents/risk-manager.md with model: sonnet and structured risk validation rules
  - Structural tests for PLUG-03 and PLUG-07 requirements

affects: [03-order-execution, 05-agent-coordination]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PreToolUse hook reads stdin JSON via jq, emits permissionDecision deny JSON to stdout (not exit code 2)"
    - "Hook uses flag-file check (circuit_breaker.flag) for zero-dependency safety gate"
    - "All debug output from hook goes to stderr; only JSON deny decisions to stdout"
    - "Agent definitions use model: sonnet with structured JSON response format for audit trail"

key-files:
  created:
    - hooks/validate-order.sh
    - agents/risk-manager.md
  modified:
    - hooks/hooks.json
    - tests/test_risk_manager.py

key-decisions:
  - "Hook uses JSON permissionDecision deny format — not exit code 2 — as required by Claude Code hooks spec"
  - "Bash matcher on PreToolUse means hook gates ALL Bash calls and filters by command content (grep pattern), not just plugin-specific commands"
  - "PDT check in hook is a lightweight file-based redundant check; the Python RiskManager is the primary PDT enforcer"

patterns-established:
  - "Hook pattern: stdin JSON -> jq parse -> grep filter -> flag file check -> JSON deny or exit 0"
  - "Agent pattern: structured JSON response format with decision, reason, and per-check breakdown"

requirements-completed: [PLUG-03, PLUG-07]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 02 Plan 02: PreToolUse Safety Hook and Risk Manager Agent Summary

**PreToolUse bash hook intercepting order-submission commands via flag-file checks, plus risk-manager agent with model: sonnet and 11 structural tests covering PLUG-03 and PLUG-07**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-22T00:40:29Z
- **Completed:** 2026-03-22T00:43:06Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created hooks/validate-order.sh: reads stdin JSON, filters order commands via grep, denies with permissionDecision JSON when circuit_breaker.flag exists, denies when PDT count >= 3
- Updated hooks/hooks.json with PreToolUse entry (Bash matcher, 10s timeout) while preserving existing SessionStart hook
- Created agents/risk-manager.md with model: sonnet, structured JSON response format, and comprehensive risk rule documentation (circuit breaker, PDT, position count, position sizing, autonomy modes)
- Added 11 structural tests (TestAgentDefinition, TestPreToolUseHook, TestHooksJson) covering all PLUG-03 and PLUG-07 requirements
- Full test suite: 81 tests pass, zero failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PreToolUse hook script and update hooks.json** - `6bf8975` (feat)
2. **Task 2: Create risk-manager agent and add structural tests** - `e726780` (feat)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `hooks/validate-order.sh` - PreToolUse hook: stdin JSON -> grep order filter -> flag file checks -> JSON deny or exit 0
- `hooks/hooks.json` - Added PreToolUse entry with Bash matcher and validate-order.sh reference
- `agents/risk-manager.md` - Risk manager agent with model: sonnet, 5-step risk check sequence, JSON response format
- `tests/test_risk_manager.py` - Added TestAgentDefinition, TestPreToolUseHook, TestHooksJson classes (11 tests)

## Decisions Made

- Hook uses JSON permissionDecision deny format — not exit code 2 — per Claude Code hooks spec
- Bash matcher on PreToolUse gates ALL Bash calls; hook filters internally by command pattern (grep regex)
- PDT check in hook is a lightweight redundant safety layer; Python RiskManager remains the primary PDT enforcer

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 02 risk management layer is complete: Python RiskManager (02-01) + PreToolUse hook (02-02) provide defense-in-depth
- Phase 03 (order execution) can depend on risk_manager.py and the hook for pre-submission safety checks
- risk-manager agent is available for Phase 05 agent coordination hand-off patterns

---
*Phase: 02-risk-management*
*Completed: 2026-03-22*
