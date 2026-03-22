---
phase: 2
slug: risk-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — exists from Phase 1 |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | RISK-01, RISK-02, POS-01, POS-02, RISK-05 | unit | `python -m pytest tests/test_risk_manager.py -x` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | RISK-03, RISK-04 | unit | `python -m pytest tests/test_api_resilience.py -x` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 2 | PLUG-07 | structural | `test -f hooks/hooks.json && grep -q PreToolUse hooks/hooks.json` | ❌ | ⬜ pending |
| 2-02-02 | 02 | 2 | PLUG-03 | structural | `test -f agents/risk-manager.md` | ❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_risk_manager.py` — stubs for circuit breaker, position sizing, PDT tracking
- [ ] `tests/test_api_resilience.py` — stubs for exponential backoff, ghost position prevention

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PreToolUse hook intercepts Bash order calls | PLUG-07 | Requires live Claude Code session with hook execution | Run a Bash command that matches order pattern, verify hook blocks it |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
