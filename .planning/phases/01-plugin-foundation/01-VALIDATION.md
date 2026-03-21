---
phase: 1
slug: plugin-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
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
| 1-01-01 | 01 | 1 | PLUG-01 | structural | `test -d commands && test -d skills && test -d hooks` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | PLUG-06 | unit | `python -m pytest tests/test_hook.py -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | CMD-01, CMD-02 | manual | N/A — wizard requires Claude session | ❌ | ⬜ pending |
| 1-02-02 | 02 | 2 | CMD-03, CMD-04 | manual | N/A — wizard requires Claude session | ❌ | ⬜ pending |
| 1-03-01 | 03 | 2 | CMD-05, STATE-03 | unit | `python -m pytest tests/test_config.py -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 2 | PLUG-05, PLUG-08 | structural | `test -f skills/trading-context/SKILL.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — stubs for config schema validation (STATE-03, CMD-05)
- [ ] `tests/test_hook.py` — stubs for SessionStart hook logic (PLUG-06)
- [ ] `tests/conftest.py` — shared fixtures (mock plugin data dir)
- [ ] `pytest` install — add to dev requirements

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wizard adapts questions by experience level | CMD-02 | Requires Claude Code session with AskUserQuestion | Run `/initialize`, select beginner, verify fewer questions shown |
| Wizard captures all trading preferences | CMD-03 | Interactive Claude session required | Run `/initialize`, complete all steps, verify config.json has all fields |
| Autonomous risk mode option | CMD-04 | Interactive Claude session required | Run `/initialize`, verify autonomous risk option appears |
| Strategy selection during setup | CMD-12 | Interactive Claude session required | Run `/initialize`, verify strategy options presented |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
