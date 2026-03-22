# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Trading Bot Plugin MVP

**Shipped:** 2026-03-22
**Phases:** 6 | **Plans:** 16 | **Sessions:** 1

### What Was Built
- Complete Claude Code plugin with 3 commands (/initialize, /build, /run)
- 4 trading strategies (momentum, mean reversion, breakout, VWAP) with 6 technical indicators
- Full risk management: circuit breaker, PDT tracking, position sizing, ghost position prevention
- SQLite state persistence with crash recovery via Alpaca position reconciliation
- Claude as strategy-level analyst with NDJSON audit trail
- Standalone deployment (generate scripts for VPS/cron/systemd)
- End-of-day reports and Slack webhook notifications

### What Worked
- Infrastructure phases (2, 3) skipping discuss worked well — no user-facing design decisions needed
- TDD approach in Phase 2 (RiskManager) caught edge cases early
- Parallel execution of Wave 1 plans in Phase 3 saved significant time
- Reference files from Phase 1 (trading-strategies.md, risk-rules.md, alpaca-api-patterns.md) served as effective specs for all later phases
- Plan checker caught real issues (Phase 2: RESEARCH.md contradiction, PDT window message)

### What Was Inefficient
- Cross-phase integration wiring wasn't verified until milestone audit — constructor signature mismatches in /run command and missing modules in build_generator could have been caught earlier
- Phase 1 human verification items accumulated without resolution
- Notification config (Slack webhook) was never added to /initialize wizard — surfaced late in audit

### Patterns Established
- Infrastructure phases skip discuss and write minimal CONTEXT.md
- Copy-and-rewrite approach for /build (single source of truth)
- Claude-as-analyst pattern: prompt builder → JSON parser → type conversion → risk gate → execution
- NDJSON audit trail for all Claude recommendations

### Key Lessons
1. Cross-phase integration checks should run after each wave, not just at milestone audit
2. Commands that reference module constructors should be verified against actual signatures
3. Build generators that copy source files need to be updated when new modules are added to imports
4. Hook scripts that read state files need to be aware of migration paths (JSON → SQLite)

### Cost Observations
- Model mix: opus for planning, sonnet for research/execution/verification
- Entire v1.0 built in a single autonomous session
- 87 commits, 4,512 LOC Python, 312 tests

---

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 6 |
| Plans | 16 |
| Tests | 312 |
| LOC | 4,512 |
| Integration issues | 4 (2 critical, 2 medium) |
| Plan checker revisions | 1 (Phase 2 only) |
