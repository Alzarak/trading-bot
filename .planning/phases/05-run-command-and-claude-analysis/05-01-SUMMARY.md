---
phase: 05-run-command-and-claude-analysis
plan: 01
subsystem: ai, trading
tags: [claude-analyzer, llm-integration, slash-command, tdd, trading-signals]

# Dependency graph
requires:
  - phase: 04-build-command
    provides: "commands/build.md pattern for slash command structure"
  - phase: 03-core-trading-loop
    provides: "MarketScanner, OrderExecutor, Signal type — all consumed by ClaudeAnalyzer"

provides:
  - "ClaudeRecommendation dataclass with to_signal() converter in scripts/types.py"
  - "ClaudeAnalyzer class: build_analysis_prompt() + parse_response() in scripts/claude_analyzer.py"
  - "commands/run.md: /run slash command with agent mode and standalone mode"
  - "agents/market-analyst.md: Claude Analysis Integration section documenting agent mode flow"
  - "Unit tests for ClaudeAnalyzer covering all 6 behaviors (17 tests, all passing)"

affects:
  - "05-run-command-and-claude-analysis plan 02"
  - "Phase 06 marketplace"
  - "Any future phase that extends the trading loop or adds strategies"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prompt-builder / response-parser separation: ClaudeAnalyzer builds prompts and parses responses without calling Claude itself — enables full unit testability"
    - "last-5-rows convention: analysis prompts include only the last 5 indicator rows to stay within token limits"
    - "JSON extraction with brace-balance tracker: handles raw JSON, code-fenced JSON, and JSON embedded in prose"
    - "Confidence threshold gate: parse_response filters below threshold so no low-confidence signals reach OrderExecutor"

key-files:
  created:
    - "scripts/claude_analyzer.py — ClaudeAnalyzer: build_analysis_prompt(), parse_response(), _extract_json_text()"
    - "commands/run.md — /run slash command with agent mode and standalone mode"
    - "tests/test_claude_analyzer.py — 17 unit tests covering all ClaudeAnalyzer behaviors"
  modified:
    - "scripts/types.py — added ClaudeRecommendation dataclass with to_signal() method"
    - "agents/market-analyst.md — added Claude Analysis Integration section"

key-decisions:
  - "ClaudeAnalyzer does NOT call Claude — it builds prompts and parses responses; /run command is responsible for the LLM call — keeps analyzer fully testable"
  - "parse_response uses brace-balance tracker to extract JSON from any response format (raw, code-blocked, surrounded by prose)"
  - "ClaudeRecommendation mirrors Signal fields 1-to-1 so to_signal() is a direct mapping with no lossy conversion"
  - "/run agent mode: Claude acts as analyst inline, Python RiskManager validates every signal — Claude never calls Alpaca APIs directly"

patterns-established:
  - "Prompt separation: ClaudeAnalyzer.build_analysis_prompt() + parse_response() as the boundary between Claude and Python trading logic"
  - "TDD RED-GREEN: test file committed before implementation — 17 tests written failing, then all passing after implementation"

requirements-completed: [CMD-10, CMD-11, AI-01, AI-02, AI-03, PLUG-02]

# Metrics
duration: 5min
completed: 2026-03-21
---

# Phase 05 Plan 01: Run Command and Claude Analysis Summary

**ClaudeAnalyzer prompt-builder/response-parser and /run command with dual agent+standalone modes, all signals gated by Python RiskManager**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-21T05:49:43Z
- **Completed:** 2026-03-21T05:54:32Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- ClaudeRecommendation dataclass added to types.py with to_signal() converter for lossless Signal construction
- ClaudeAnalyzer built with build_analysis_prompt() (last-5-rows indicator tables, JSON schema, analyst-only instruction) and parse_response() (handles raw JSON, code blocks, embedded prose, confidence threshold)
- /run command created with agent mode (inline Claude analysis loop) and standalone mode (delegates to bot.py)
- market-analyst agent updated with explicit Claude Analysis Integration documentation
- 17 unit tests pass without any LLM or Alpaca API calls

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `7bbff80` (test)
2. **Task 1 GREEN: ClaudeRecommendation + ClaudeAnalyzer** - `b0a017f` (feat)
3. **Task 2: /run command + market-analyst update** - `ba20acf` (feat)

_TDD task: test commit first (RED), then implementation (GREEN), refactor not needed._

## Files Created/Modified

- `scripts/types.py` — added ClaudeRecommendation dataclass with to_signal()
- `scripts/claude_analyzer.py` — new: ClaudeAnalyzer with prompt builder and response parser
- `commands/run.md` — new: /run slash command, agent mode + standalone mode
- `agents/market-analyst.md` — added Claude Analysis Integration section
- `tests/test_claude_analyzer.py` — new: 17 unit tests covering all behaviors

## Decisions Made

- ClaudeAnalyzer intentionally does NOT call Claude — it only builds prompts and parses responses. The /run command is responsible for the LLM call. This separation enables full unit testability without mocking LLM calls.
- parse_response uses a brace-balance tracker (not regex alone) to handle arbitrarily nested JSON, plus code-block stripping for Markdown-formatted responses.
- ClaudeRecommendation mirrors Signal fields exactly so to_signal() is a lossless 1-to-1 mapping.
- /run agent mode positions Claude as the analyst inline — indicator DataFrames flow to Claude via build_analysis_prompt(), Claude's JSON response flows back via parse_response(), then Python RiskManager validates before any order executes.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- ClaudeAnalyzer is the bridge between MarketScanner output and Alpaca order execution via Claude
- /run command provides the primary user entry point for running the bot within Claude Code
- Phase 05 Plan 02 can proceed: it will extend the loop or finalize the run command
- No blockers

---
*Phase: 05-run-command-and-claude-analysis*
*Completed: 2026-03-21*
