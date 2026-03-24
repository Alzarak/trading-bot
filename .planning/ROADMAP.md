# Roadmap: Trading Bot Pipeline Rewrite

## Overview

Replace the failed 2-of-N strategy system with a regime-gated, conviction-scored signal pipeline. Four phases deliver the complete rewrite: first establishing typed data contracts and the regime/FMP foundation, then building the full signal pipeline (screeners, aggregation, sizing), then wiring everything into the bot with thesis lifecycle tracking, and finally adding postmortem feedback to close the learning loop.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Data contracts, FMP client, regime detection, and exposure gating
- [ ] **Phase 2: Signal Pipeline** - Technical screener, FMP screeners, aggregation, and position sizing
- [ ] **Phase 3: Integration** - Bot wiring, pipeline analyzer, thesis lifecycle, and backward compatibility
- [ ] **Phase 4: Postmortem** - Signal postmortem and screener weight feedback

## Phase Details

### Phase 1: Foundation
**Goal**: The pipeline has typed data contracts and can detect macro regime state with exposure decisions before any signal is generated
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, FMP-01, FMP-02, FMP-03, REG-01, REG-02, REG-03, REG-04, EXP-01, EXP-02, EXP-03, EXP-04
**Success Criteria** (what must be TRUE):
  1. Running the bot with a valid FMP key produces a logged RegimeState with a regime label, top_risk score (0-100), and risk zone on every scan cycle
  2. Running the bot without an FMP key produces a logged RegimeState with regime=transitional and top_risk=30 (neutral defaults) without any exception raised
  3. When top_risk >= 70, a logged ExposureDecision shows bias=SELL_ONLY and new BUY entries are blocked
  4. When regime == contraction, the ExposureDecision position_size_multiplier is 0.5 (half normal size)
  5. All four new dataclasses (RegimeState, ExposureDecision, RawSignal, AggregatedSignal) are importable from models.py without error
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Data models: extend models.py with 4 dataclasses + pipeline package init
- [ ] 01-02-PLAN.md — FMP client: shared FMPClient with graceful degradation, caching, retry
- [ ] 01-03-PLAN.md — Regime detection: RegimeDetector with macro regime + top risk, split TTL cache
- [ ] 01-04-PLAN.md — Exposure gating: ExposureCoach + config.json pipeline section

### Phase 2: Signal Pipeline
**Goal**: The pipeline can scan the watchlist, produce weighted conviction scores from multiple screeners, and calculate ATR-based position sizes ready for order execution
**Depends on**: Phase 1
**Requirements**: SCR-01, SCR-02, SCR-03, SCR-04, AGG-01, AGG-02, AGG-03, AGG-04, SIZE-01, SIZE-02, SIZE-03
**Success Criteria** (what must be TRUE):
  1. The technical screener produces RawSignals with float scores (not boolean pass/fail) and correct dollar ATR values (verifiable: atr > 0.01 * entry_price for any signal)
  2. When only the technical screener is active (no FMP key), the aggregator applies a min_conviction threshold of 0.65, not 0.50
  3. When two screeners produce signals for the same symbol with opposing directions, the AggregatedSignal conviction is reduced by 30%
  4. Position sizes output by the sizer are constrained by both the ExposureDecision ceiling and RiskManager.max_position_pct — whichever is smaller wins
  5. Kelly sizing is disabled (falls back to ATR) when fewer than 30 closed theses exist for a screener
**Plans**: TBD

### Phase 3: Integration
**Goal**: The full pipeline runs inside scan_and_trade(), existing installations with only a strategies key continue working, and thesis state is tracked atomically across crashes
**Depends on**: Phase 2
**Requirements**: ANA-01, ANA-02, THESIS-01, THESIS-02, THESIS-03, INT-01, INT-02, INT-03, INT-04, INT-05
**Success Criteria** (what must be TRUE):
  1. A config.json with a pipeline key causes bot.py to execute the new 8-phase pipeline; a config.json with only a strategies key causes bot.py to execute the old behavior unchanged
  2. After a simulated crash and restart, reconcile_on_startup() correctly promotes or closes theses based on current Alpaca positions — no orphaned ACTIVE theses remain
  3. A symbol already in IDEA, ENTRY_READY, or ACTIVE thesis state is not re-entered on the next scan cycle
  4. Claude analysis prompts (agent mode) include a Market Context block with regime label, top_risk score, risk zone, and exposure ceiling — and Claude does not recommend BUY when top_risk >= 70
  5. Both scan_and_trade() and scan_and_trade_crypto() run the new pipeline end-to-end without error
**Plans**: TBD

### Phase 4: Postmortem
**Goal**: Closed theses record outcomes and feed realized performance back to screener conviction weights, enabling Kelly sizing to activate when sufficient history exists
**Depends on**: Phase 3
**Requirements**: POST-01, POST-02
**Success Criteria** (what must be TRUE):
  1. When a thesis transitions to CLOSED, the outcome record (realized return, true/false positive classification, regime mismatch flag) is written to SQLite atomically
  2. After 30+ closed theses accumulate for a screener, that screener's weight in the aggregator updates based on postmortem results — visible in logged aggregation output
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 1/4 | In Progress|  |
| 2. Signal Pipeline | 0/TBD | Not started | - |
| 3. Integration | 0/TBD | Not started | - |
| 4. Postmortem | 0/TBD | Not started | - |
