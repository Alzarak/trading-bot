# Project Research Summary

**Project:** Trading Bot — Regime-Aware Signal Pipeline Rewrite
**Domain:** Multi-stage autonomous trading signal pipeline (Python, Alpaca, FMP)
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

This project is a rewrite of the signal generation layer of an autonomous stock trading bot. The existing bot has demonstrated negative expectancy (23/100 backtest score, 96.8% max drawdown) due to two root causes: (1) a regime-blind entry gate that allowed buys in hostile market conditions, and (2) a boolean 2-of-N indicator agreement gate that fails to weight signal quality. Research across all four domains confirms that the fix is a structured, sequential pipeline that gates entries on macro regime state, produces continuous conviction scores rather than binary pass/fail, and adapts position sizing to actual volatility. The recommended architecture is already validated by a set of reference implementations (tradermonty/claude-trading-skills) that map directly to the required components.

The recommended approach is to build a `scripts/pipeline/` package with eight distinct phases — regime detection, exposure calculation, multi-screener signal generation, weighted conviction aggregation, regime-aware Claude analysis, ATR-based position sizing, thesis lifecycle tracking, and signal postmortem — wired sequentially inside the existing `scan_and_trade()` loop. The entire infrastructure layer (Alpaca SDK, APScheduler, RiskManager, OrderExecutor, StateStore) is unchanged. Only three new PyPI packages are needed (`requests`, `requests-cache`, `tenacity`); all other new code uses Python stdlib. FMP API integration is optional — the pipeline degrades gracefully to neutral defaults and continues operating on Alpaca-only data.

The key risk is premature complexity: FMP-dependent screeners (VCP, earnings drift), signal postmortem, and Kelly sizing all require upstream components to be validated first. The research is unanimous that these must be deferred to v1.x. The blocking risk for v1 is the ATR dollar/ratio confusion already present in the codebase (`ATRr` column vs dollar ATR), the absence of regime context in Claude prompts, and the conviction inflation problem that occurs when only one screener is active. All three are tractable with targeted fixes, not architectural redesigns.

---

## Key Findings

### Recommended Stack

The existing stack (alpaca-py 0.43.2, pandas-ta 0.4.71b0, APScheduler, pydantic-settings, loguru, SQLite, Python 3.12+) is production-ready and requires no changes. The pipeline rewrite adds exactly three new dependencies: `requests>=2.31` and `requests-cache>=1.3.1` for the FMP client, and `tenacity>=9.1.4` for retry logic. All other pipeline modules (`pipeline/regime.py`, `pipeline/exposure.py`, `pipeline/aggregator.py`, `pipeline/sizer.py`, `pipeline/thesis_manager.py`) are pure Python stdlib.

The research explicitly rules out several tempting alternatives: `fmp-data` PyPI package (over-engineered for 5-6 endpoints), `hmmlearn` for regime detection (ML adds latency, non-explainable), `PyPortfolioOpt` for sizing (wrong abstraction level), SQLAlchemy (2-table schema doesn't justify ORM), and PyYAML (config already handled by pydantic-settings + config.json).

**Core new technologies:**
- `requests` + `requests-cache` (SQLite backend): FMP API client with zero-config caching that survives bot restarts — essential for staying within FMP's 250 calls/day free tier
- `tenacity`: Exponential backoff retry for FMP 429/5xx — replaces the fragile `time.sleep(60)` pattern in reference skill implementations
- `stdlib dataclasses` + `enum`: Internal pipeline data contracts (`RegimeState`, `ExposureDecision`, `RawSignal`, `AggregatedSignal`) — faster than Pydantic for in-memory pipeline computation, consistent with existing `models.py`
- `stdlib sqlite3`: Thesis lifecycle table and FMP snapshot cache — no migration from existing `state_store.py` pattern required

### Expected Features

The feature research identifies 12 table-stakes features for v1 (the minimum to achieve positive expectancy) and 4 differentiators for v1.x (unlocked after v1 validates the core pipeline).

**Must have (table stakes — v1):**
- Macro regime classification (5 regime types, 6 cross-asset ratios via FMP) — blocks entries in hostile conditions; root cause fix #1
- Market top risk scoring (0-100 composite, 6 sub-components) — tactical entry gate; root cause fix #2
- Exposure decision output (max_exposure_pct, bias, action gate) — translates regime into concrete trading posture
- Technical screener with weighted scoring — replaces failed 2-of-N gate with continuous float scores
- Weighted conviction aggregation with deduplication and contradiction detection — honest multi-source composite
- Regime-aware Claude analysis prompts — injects `RegimeState` + `ExposureDecision` into every Claude prompt
- ATR-based position sizing — volatility-adjusted sizing; addresses 96.8% max drawdown
- Thesis lifecycle tracking (IDEA → ENTRY_READY → ACTIVE → CLOSED) — prevents re-entry on every 5-min cycle
- FMP API client with graceful degradation — shared, rate-limited, cached; never raises to callers
- Extended data models (typed dataclasses for all new pipeline types)
- Pipeline config section in config.json (runtime-tunable thresholds)
- Backward compatibility fallback (existing `strategies` key unchanged if `pipeline` key absent)

**Should have (differentiators — v1.x, after v1 validates):**
- VCP pattern screener (Minervini) — structurally better risk/reward setups via FMP universe
- Earnings drift screener (PEAD anomaly) — predictable 5-20 day drift window; requires local FMP snapshot store
- Signal postmortem with weight feedback — screener quality tracking; enables Kelly upgrade
- Kelly criterion sizing — activates automatically after 30+ closed theses per screener

**Defer (v2+):**
- Canslim screener — multi-week implementation; not the root cause
- ML model training pipeline — requires months of postmortem data
- Options strategy layer — separate architectural concern
- Shorting/inverse positions — deferred until long pipeline shows positive expectancy

### Architecture Approach

The architecture is a linear, stage-gated pipeline wired into the existing `bot.py` `scan_and_trade()` function. Each of the 8 phases is a separate module under `scripts/pipeline/`, with `models.py` as the central shared contract — no phase imports from another phase, preventing circular dependencies. The infrastructure layer (MarketScanner, RiskManager, OrderExecutor, StateStore) is entirely unchanged. The old `strategies/` directory and `claude_analyzer.py` are deleted; the pipeline replaces their function.

**Major components:**
1. `pipeline/regime.py` — Detects macro regime label + top_risk score from FMP cross-asset ratios; hourly cache for macro label, 15-min cache for top_risk
2. `pipeline/exposure.py` — Pure function: `RegimeState` → `ExposureDecision` (max_exposure_pct, size_multiplier, action gate); no I/O
3. `pipeline/screeners.py` — Runs technical screener (always), earnings drift screener, and VCP screener (both FMP-gated); produces `list[RawSignal]`
4. `pipeline/aggregator.py` — Weighted conviction scoring with source dedup, agreement bonuses, contradiction penalties; scales `min_conviction` threshold by active source count
5. `pipeline/analyzer.py` — Claude analysis (agent mode only); always injects `RegimeState` + `ExposureDecision` into prompt preamble
6. `pipeline/sizer.py` — ATR-based qty by default; Kelly when ≥30 closed theses; capped by `ExposureDecision` ceiling and `RiskManager.max_position_pct`
7. `pipeline/thesis_manager.py` — SQLite-backed state machine with conditional UPDATE transitions; `reconcile_on_startup()` required
8. `pipeline/postmortem.py` — Outcome tracking on thesis CLOSE; weight feedback to aggregator (v1.x)

**Build order:** models.py → state_store.py (theses table) → regime.py → exposure.py → screeners.py (technical only) → aggregator.py → sizer.py → bot.py integration → thesis_manager.py → FMP screeners → analyzer.py → postmortem.py

**Critical path (MVP):** models.py → regime.py → exposure.py → screeners.py → aggregator.py → sizer.py → bot.py

### Critical Pitfalls

1. **ATR dollar/ratio confusion** — `pandas-ta` appends `ATRr_{period}` (a ratio, not dollars) when `df.ta.atr()` is called. Passing this as dollar stop distance produces stops 3 cents away on $10 stocks, instantly stopped out by noise. Fix: multiply `ATRr` by `close` price before creating `RawSignal.atr`. Verify with assertion: `signal.atr > 0.01 * entry_price`. This is already present in the codebase and must be fixed in the screener, not patched downstream.

2. **Stale regime cache during intraday flips** — A uniform 1-hour cache TTL misses fast-moving top_risk events (Fed announcements, sudden breadth deterioration). Fix: split TTL — macro regime label cached 60 min, top_risk score cached 15 min. Invalidate top_risk cache immediately when it crosses a zone boundary.

3. **Conviction inflation with single active screener** — When only the technical screener is active (default config without FMP), the `min_conviction = 0.50` threshold is too permissive and recreates the old 2-of-N failure. Fix: dynamically scale threshold by active source count — 1 source requires 0.65, 2 sources require 0.55, 3+ sources use 0.50.

4. **Kelly applied to insufficient trade history** — With fewer than 30 closed trades, the win rate estimate has ±15-20% confidence interval. Over-Kelly betting produces negative median growth even with positive-expectancy strategy. Fix: enforce `min_kelly_sample_size: 30` guard in `sizer.py`; always use ATR below threshold; cap Kelly at 0.5x (Half-Kelly) even when active.

5. **FMP earnings data is not point-in-time** — FMP's live API returns current revised consensus, not the pre-announcement estimate needed to compute surprise drift. Calling it once per cycle produces near-zero drift on all symbols. Fix: store FMP earnings snapshots to `fmp_estimates_cache` SQLite table on every poll; compute drift from two captures ≥24 hours apart.

6. **Claude prompt missing regime context** — Without `RegimeState` in the prompt, Claude returns high-confidence BUY signals during hostile conditions, wasting API calls and generating log noise from regime-gate discards. Fix: `PipelineAnalyzer.build_prompt()` must include `## Market Context` block with regime label, top_risk score, risk zone, and exposure ceiling; instruct Claude explicitly not to recommend BUY when top_risk ≥ 70.

7. **Thesis state machine allows contradictory transitions** — Simple status assignments without conditional UPDATE guards create orphaned `ACTIVE` theses after crashes, causing phantom exposure accounting. Fix: all UPDATE statements must be `WHERE thesis_id = ? AND status = 'ENTRY_READY'`; check `rowcount == 0` to detect invalid transitions; run `reconcile_on_startup()` before first scan cycle.

---

## Implications for Roadmap

Based on combined research, the build order is dictated by strict dependency chains — each phase requires the previous phase's outputs as typed inputs. The phase structure maps directly to the architecture build order identified in ARCHITECTURE.md.

### Phase 1: Foundation — Data Contracts and Persistence
**Rationale:** Every subsequent phase consumes `RegimeState`, `ExposureDecision`, `RawSignal`, or `AggregatedSignal`. These typed contracts must exist before any pipeline module can be written or tested. The theses SQLite table must also exist before `thesis_manager.py` can write to it.
**Delivers:** Extended `models.py` with 4 new dataclasses + 3 new enums; `state_store.py` with `theses` and `fmp_estimates_cache` table migrations; `pipeline/__init__.py` package scaffold
**Addresses:** Extended data models, thesis lifecycle prerequisite
**Avoids:** Circular import anti-pattern (all phases import from models.py, not from each other)

### Phase 2: Regime Detection and Exposure Gating
**Rationale:** This is the primary root cause fix. Nothing downstream should run until the regime gate is in place. The FMP client must be built first (regime depends on it), and the exposure calculation is a pure function of regime — testable immediately after regime.
**Delivers:** `pipeline/fmp_client.py` (requests + requests-cache + tenacity); `pipeline/regime.py` with split-TTL cache (macro 60min, top_risk 15min); `pipeline/exposure.py` (pure RegimeState → ExposureDecision); graceful FMP degradation returning neutral defaults
**Addresses:** Macro regime classification, market top risk scoring, exposure decision output, FMP API client
**Avoids:** Stale cache intraday flip pitfall; FMP rate limit exhaustion; regime detection on every 5-min cycle

### Phase 3: Technical Screener with Weighted Scoring
**Rationale:** The technical screener is the only screener that operates without FMP. It must be built before the aggregator (which needs at least one signal source) and can be validated independently. This is also where the ATR dollar/ratio bug must be fixed.
**Delivers:** `pipeline/screeners.py` (technical screener only); `RawSignal` production with correct dollar ATR; weighted float scoring replacing boolean 2-of-N gate
**Addresses:** Technical screener with weighted scoring, ATR-based position sizing precondition
**Avoids:** ATR dollar/ratio confusion (critical fix #1); lookforward contamination in normalization (rolling windows required)

### Phase 4: Aggregation and Conviction Scoring
**Rationale:** With at least one screener producing RawSignals, the aggregator can be built and tested with synthetic inputs. This phase also implements the dynamic conviction threshold scaling that prevents single-source inflation.
**Delivers:** `pipeline/aggregator.py` with source weights, dedup, agreement bonuses, contradiction penalties, and dynamic min_conviction scaling by active source count
**Addresses:** Weighted conviction aggregation with deduplication, contradiction detection
**Avoids:** Conviction inflation with single active screener (threshold scales with source count)

### Phase 5: Position Sizing
**Rationale:** ATR-based sizing is a pure function that depends only on `AggregatedSignal.atr` and `ExposureDecision.size_multiplier`. It can be built and unit-tested before bot.py integration. Kelly is excluded from this phase (requires postmortem history).
**Delivers:** `pipeline/sizer.py` with ATR sizing (default) and Kelly framework (disabled until ≥30 closed theses); all sizes capped by ExposureDecision ceiling and RiskManager.max_position_pct; min_kelly_sample_size guard enforced
**Addresses:** ATR-based position sizing, Kelly criterion framework (disabled)
**Avoids:** Kelly without sample guard; over-Kelly betting during lucky streaks

### Phase 6: Bot Integration and Backward Compatibility
**Rationale:** Wiring the pipeline into `scan_and_trade()` is its own phase because it requires all upstream phases to be complete and introduces the backward compatibility gate. This is also where the old `strategies/` directory and `claude_analyzer.py` are removed.
**Delivers:** Rewritten `bot.py` `scan_and_trade()` with sequential pipeline call chain; `pipeline` key detection in config; existing `strategies` key routes to legacy path unchanged; `thesis_manager.reconcile_on_startup()` called before first scan; pipeline config section in config.json
**Addresses:** Backward compatibility fallback, pipeline config section
**Avoids:** Breaking existing installations; thesis state machine orphans at startup

### Phase 7: Thesis Lifecycle Tracking
**Rationale:** Thesis tracking does not block order execution (Phase 6 works without it) but is required for postmortem and Kelly upgrade. It can be added after the pipeline runs cleanly.
**Delivers:** `pipeline/thesis_manager.py` with conditional UPDATE state machine (IDEA → ENTRY_READY → ACTIVE → CLOSED); `reconcile_on_startup()` cross-referencing Alpaca positions; SQLite atomic writes with BEGIN EXCLUSIVE transactions
**Addresses:** Thesis lifecycle tracking
**Avoids:** Contradictory thesis state transitions; orphaned ACTIVE theses after crash

### Phase 8: Regime-Aware Claude Analysis
**Rationale:** Claude analysis is agent-mode-only and does not block the autonomous pipeline. It should be built after the autonomous path is validated so prompt tuning is done against a known-working signal feed.
**Delivers:** `pipeline/analyzer.py` replacing `claude_analyzer.py`; every prompt includes `## Market Context` block with regime label, top_risk, risk zone, and exposure ceiling; explicit BUY-block instruction when top_risk ≥ 70
**Addresses:** Regime-aware Claude analysis prompts
**Avoids:** Claude receiving no regime context; wasted API calls on regime-blocked recommendations

### Phase 9 (v1.x): FMP Screeners — VCP and Earnings Drift
**Rationale:** Add after Phase 6 validates positive expectancy on Alpaca-only pipeline. FMP client already exists from Phase 2; these screeners slot into the existing `screeners.py` module.
**Delivers:** `EarningsDriftScreener` (FMP earnings calendar + local snapshot delta); `VCPScreener` (Minervini criteria on FMP S&P 500 universe); `fmp_estimates_cache` table persistence for point-in-time drift computation
**Addresses:** VCP screener, earnings drift screener
**Avoids:** FMP earnings point-in-time data pitfall (local snapshot store required from day one of this phase)

### Phase 10 (v1.x): Signal Postmortem and Weight Feedback
**Rationale:** Requires closed theses to exist (Phase 7 prerequisite) and at least one full market cycle of v1 operation. Kelly unlocks automatically once 30 closed theses are recorded.
**Delivers:** `pipeline/postmortem.py`; outcome classification (TRUE_POSITIVE / FALSE_POSITIVE / REGIME_MISMATCH); screener weight updates to SQLite; Kelly activation path in `sizer.py`
**Addresses:** Signal postmortem, Kelly criterion sizing (activated)

### Phase Ordering Rationale

- **Phases 1-3 before 4:** Aggregation cannot be built without the typed contracts (Phase 1) and at least one signal source (Phase 3).
- **Phase 2 before Phase 3:** The ATR screener is FMP-independent, but the regime gate should already be in place before any signals flow — avoids building a path that will be blocked anyway once regime is added.
- **Phase 6 after Phases 1-5:** Bot integration is the final wiring step; all pieces must work independently first.
- **Phase 7 after Phase 6:** Thesis tracking is additive — the pipeline executes trades without it, making Phase 6 a clean integration milestone.
- **Phase 8 after Phase 7:** Claude analysis should be tuned against a validated signal pipeline, not a speculative one.
- **Phases 9-10 deferred:** They depend on Phase 6 producing validated positive expectancy results before adding complexity.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 9 (VCP Screener):** Minervini VCP criteria involve specific multi-week pattern detection; the tradermonty reference skill is available but porting to the in-memory pipeline model requires careful analysis of the bar aggregation logic.
- **Phase 9 (Earnings Drift):** FMP point-in-time snapshot store design needs integration testing — the two-capture minimum and 24-hour delta requirement have implementation nuances around fiscal period alignment.
- **Phase 10 (Postmortem weight feedback):** Feedback loop design (how weights update without creating runaway reinforcement) benefits from testing with simulated data before live deployment.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Data Contracts):** Pure Python dataclass/enum additions — well-understood, no research needed.
- **Phase 2 (FMP Client + Regime):** Reference implementation exists at `/tmp/claude-trading-skills/skills/macro-regime-detector/`; direct port with TTL split change.
- **Phase 4 (Aggregator):** Reference implementation exists at `/tmp/claude-trading-skills/skills/edge-signal-aggregator/`; adapt for in-memory use.
- **Phase 5 (Sizer):** Reference implementation exists at `/tmp/claude-trading-skills/skills/position-sizer/`; direct port with guard additions.
- **Phase 6 (Bot Integration):** Straightforward wiring; backward compat pattern is simple key check.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core stack unchanged and production-verified; 3 new packages verified on PyPI with current versions; reference skills use same patterns |
| Features | HIGH | Tradermonty reference implementations verified directly; REWRITE-PLAN.md cross-references all feature decisions; feature dependencies fully mapped |
| Architecture | HIGH | Direct inspection of existing codebase + REWRITE-PLAN.md + 8 reference skill scripts; build order derived from verified dependency graph |
| Pitfalls | HIGH | 7 of 8 pitfalls derived from direct codebase analysis (ATR bug is present in market_scanner.py line 146); FMP point-in-time limitation verified against FMP education docs |

**Overall confidence:** HIGH

### Gaps to Address

- **FMP free tier call budget validation:** The 250 calls/day free tier figure is from research but was not verified with a live FMP account. If the actual limit is lower, the regime cache TTLs will need to be extended. Validate during Phase 2 implementation with a live FMP key before finalizing TTL values.
- **ATR column naming after pandas-ta upgrade:** The `ATRr` naming quirk was observed in market_scanner.py comments for pandas-ta 0.4.71b0. If pandas-ta is upgraded in future, verify column name stability. Add a startup assertion that validates ATR column names against expected values.
- **Alpaca IEX feed bar gaps for illiquid symbols:** The pitfall research notes that `dropna()` on indicator computation can remove all rows for illiquid symbols. The watchlist composition during Phase 3 testing should include at least one low-volume symbol to validate gap handling.
- **Thesis state reconciliation correctness:** The `reconcile_on_startup()` design depends on Alpaca's `/positions` endpoint returning accurate data after a crash-restart. This should be tested with a simulated crash during paper trading before relying on it in live operation.

---

## Sources

### Primary (HIGH confidence)
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/` — FMP client pattern, regime scoring logic, component TTL rationale
- `/tmp/claude-trading-skills/skills/edge-signal-aggregator/scripts/aggregate_signals.py` — Source weights, dedup thresholds, agreement bonuses, contradiction penalties
- `/tmp/claude-trading-skills/skills/position-sizer/scripts/position_sizer.py` — ATR, fixed fractional, Kelly implementations with Half-Kelly cap
- `/tmp/claude-trading-skills/skills/exposure-coach/scripts/` — Regime-to-exposure mapping and score weights
- `/home/parz/projects/trading-bot/scripts/market_scanner.py` — ATRr naming bug (line 146), existing indicator computation pattern
- `/home/parz/projects/trading-bot/scripts/models.py` — Existing Signal/ClaudeRecommendation contracts; dataclass + enum conventions
- `/home/parz/projects/trading-bot/REWRITE-PLAN.md` — Authoritative phase ordering and data flow
- https://pypi.org/project/requests-cache/ — v1.3.1 verified March 4, 2026
- https://pypi.org/project/tenacity/ — v9.1.4 verified February 7, 2026

### Secondary (MEDIUM confidence)
- https://arxiv.org/html/2412.03167v1 — Weighted-majority ensembles for intraday trading (aggregation patterns)
- https://macrosynergy.com/research/macro-trading-signal-optimization-basic-statistical-learning-methods/ — Signal quality measurement
- https://arxiv.org/html/2502.15800v3 — LLM trading overconfidence (Claude prompt design)

### Tertiary (LOW confidence — needs validation during implementation)
- FMP 250 calls/day free tier limit — from research; validate with live key during Phase 2
- https://site.financialmodelingprep.com/education/calendar/build-an-earnings-revision-pressure-signal-estimate-drift-monitor — FMP earnings point-in-time limitation

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
