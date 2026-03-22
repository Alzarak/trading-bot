# Phase 2: Risk Management - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers all risk controls as foundational infrastructure before any order execution code exists: circuit breakers (daily drawdown halt), position sizing (percentage of equity), PDT tracking (rolling 5-day count), max position limits, API call resilience (exponential backoff, ghost position prevention), and a PreToolUse safety hook that intercepts order submissions violating safety constraints.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `references/risk-rules.md` — comprehensive risk rules reference (circuit breaker, position sizing, PDT, ATR stops, order safety)
- `references/alpaca-api-patterns.md` — alpaca-py SDK patterns for all order types, error handling, retry logic
- `skills/trading-rules/SKILL.md` — auto-loaded domain context covering risk controls
- `tests/conftest.py` — shared test fixtures
- `tests/test_config.py` — config schema contract (risk_tolerance, max_daily_loss_pct, max_position_pct, max_positions fields)

### Established Patterns
- Python with alpaca-py SDK for Alpaca integration
- pydantic-settings for configuration management
- pytest for testing
- Plugin structure: hooks/, agents/, skills/

### Integration Points
- `config.json` provides risk parameters (from Phase 1 wizard)
- `hooks/hooks.json` for PreToolUse hook registration
- `agents/` directory for risk-manager agent definition
- Future Phase 3 order execution will call risk manager before submitting orders

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
