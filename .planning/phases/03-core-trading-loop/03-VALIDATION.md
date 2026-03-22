---
phase: 3
slug: core-trading-loop
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — exists from Phase 1 |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | TA-01..TA-06, ALP-05 | unit | `python -m pytest tests/test_market_scanner.py -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | ORD-01..ORD-05 | unit | `python -m pytest tests/test_order_executor.py -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 2 | STATE-01, STATE-02, POS-03, POS-04 | unit | `python -m pytest tests/test_state_store.py -x` | ❌ W0 | ⬜ pending |
| 3-04-01 | 04 | 2 | STRAT-01..STRAT-05 | unit | `python -m pytest tests/test_strategies.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_market_scanner.py` — stubs for indicator computation, market hours
- [ ] `tests/test_order_executor.py` — stubs for order types, idempotency
- [ ] `tests/test_state_store.py` — stubs for SQLite persistence, crash recovery
- [ ] `tests/test_strategies.py` — stubs for all 4 strategy modules

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bot connects to Alpaca paper endpoint | ALP-05 | Requires live API keys | Set paper keys, run bot, verify market clock check |
| Graceful shutdown on SIGINT | POS-03 | Requires signal delivery to running process | Start bot, send SIGINT, verify positions closed/logged |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
