# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 01-foundation
**Areas discussed:** FMP degradation behavior, Regime cache strategy, Exposure gating thresholds, Data model placement
**Mode:** Auto (all areas auto-selected, recommended defaults chosen)

---

## FMP Degradation Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Silent degradation with log warning | Log warning once per cache cycle, continue with neutral defaults | ✓ |
| Raise on missing key | Fail fast if FMP key not configured | |
| Periodic retry with backoff | Keep retrying FMP in background | |

**User's choice:** [auto] Silent degradation with log warning (recommended default)
**Notes:** Matches PROJECT.md constraint that bot must function without FMP. Never raises exceptions to callers.

---

## Regime Cache Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Split TTL (hourly macro / 15-min top_risk) | Different refresh rates for slow vs fast-changing data | ✓ |
| Single hourly TTL | Same cache for all regime data | |
| No cache (fetch every cycle) | Always fresh but burns FMP quota | |

**User's choice:** [auto] Split TTL — hourly for macro regime, 15-min for top_risk (recommended default from PITFALLS.md research)
**Notes:** Single TTL identified as pitfall — intraday top_risk ratios can shift within an hour.

---

## Exposure Gating Thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| REWRITE-PLAN.md defaults, configurable | block>=70, halve in contraction, proportional 41-69 | ✓ |
| Conservative (block>=60) | More aggressive gating | |
| Permissive (block>=80) | Less aggressive gating | |

**User's choice:** [auto] REWRITE-PLAN.md defaults with config.json override (recommended default)
**Notes:** All thresholds configurable via pipeline.regime_gating section.

---

## Data Model Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Add to existing scripts/models.py | Consistent with Signal/ClaudeRecommendation | ✓ |
| New scripts/pipeline/models.py | Separate pipeline types | |

**User's choice:** [auto] Add to existing scripts/models.py (recommended default — follows existing pattern)
**Notes:** Keeps all shared type contracts in one file.

---

## Claude's Discretion

- FMP client internal architecture
- Exact regime calculator implementations
- Error logging format
- Unit test structure

## Deferred Ideas

None — discussion stayed within phase scope
