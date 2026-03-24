# Architecture Research

**Domain:** Multi-stage regime-aware trading signal pipeline (Python, Alpaca, APScheduler)
**Researched:** 2026-03-23
**Confidence:** HIGH — based on direct inspection of existing codebase, REWRITE-PLAN.md, and reference skill implementations in /tmp/claude-trading-skills/

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SCHEDULER LAYER (APScheduler — 5min)                 │
│                         bot.py: scan_and_trade()                        │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                     PIPELINE LAYER (scripts/pipeline/)                  │
│                                                                         │
│  Phase 1          Phase 2         Phase 3             Phase 4           │
│  ┌──────────┐    ┌──────────┐    ┌─────────────────┐  ┌─────────────┐  │
│  │ regime.py│───►│exposure  │───►│ screeners.py    │─►│aggregator   │  │
│  │          │    │  .py     │    │                 │  │   .py       │  │
│  │RegimeSt. │    │Exposure  │    │ Technical +     │  │ Weighted    │  │
│  │top_risk  │    │Decision  │    │ Earnings +      │  │ conviction  │  │
│  │(hourly)  │    │ceiling%  │    │ VCP             │  │ dedup+      │  │
│  └──────────┘    └──────────┘    │ →list[RawSig]   │  │ contradict  │  │
│                                  └─────────────────┘  └──────┬──────┘  │
│                                                               │         │
│  Phase 5          Phase 6         Phase 7             Phase 8 │         │
│  ┌──────────┐    ┌──────────┐    ┌─────────────────┐  ┌──────▼──────┐  │
│  │analyzer  │◄───│          │    │ risk_manager.py │  │thesis_mgr   │  │
│  │  .py     │    │ sizer.py │    │ +               │  │  .py        │  │
│  │(agent    │───►│ ATR/Kelly│───►│ order_executor  │─►│IDEA→ACTIVE  │  │
│  │  mode)   │    │ qty/sig  │    │ .py             │  │→CLOSED      │  │
│  └──────────┘    └──────────┘    └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER (unchanged)                     │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │state_store │  │portfolio_   │  │market_scanner│  │audit_logger   │  │
│  │   .py      │  │tracker.py   │  │    .py       │  │notifier.py    │  │
│  │ (SQLite)   │  │ (P&L/logs)  │  │(Alpaca+ta)   │  │               │  │
│  └────────────┘  └─────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                      EXTERNAL DATA LAYER                                │
│  ┌─────────────────┐              ┌──────────────────────────────────┐  │
│  │   Alpaca API    │              │   FMP API (optional)             │  │
│  │ TradingClient   │              │ macro regime, earnings, VCP      │  │
│  │ HistoricalData  │              │ degrades gracefully if absent    │  │
│  └─────────────────┘              └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility | Communicates With |
|-----------|------|---------------|-------------------|
| Scheduler | `bot.py` | 5-min loop, market clock gate, shutdown | All pipeline phases |
| Regime Gate | `pipeline/regime.py` | Detect macro regime + top_risk score (0-100); cache hourly | exposure.py |
| Exposure Coach | `pipeline/exposure.py` | Derive max_exposure_pct, bias, size_multiplier from RegimeState | screeners.py |
| Screeners | `pipeline/screeners.py` | Produce RawSignals from technical indicators, earnings drift, VCP | aggregator.py |
| Aggregator | `pipeline/aggregator.py` | Weighted conviction scoring, dedup, contradiction detection | analyzer.py / sizer.py |
| Analyzer | `pipeline/analyzer.py` | Claude analysis with regime-enriched prompt (agent mode only) | sizer.py |
| Sizer | `pipeline/sizer.py` | ATR-based or Kelly qty per signal, capped by ExposureDecision | risk_manager.py |
| Risk + Executor | `risk_manager.py` + `order_executor.py` | Circuit breaker, PDT, budget cap, Alpaca order submission | thesis_manager.py |
| Thesis Manager | `pipeline/thesis_manager.py` | Lifecycle IDEA→ENTRY_READY→ACTIVE→CLOSED in SQLite | postmortem.py |
| Postmortem | `pipeline/postmortem.py` | Outcome tracking; feed weight adjustments back to aggregator | aggregator.py (future) |
| Market Scanner | `market_scanner.py` | Alpaca OHLCV fetch + pandas-ta indicator computation | screeners.py |
| State Store | `state_store.py` | SQLite: positions, trades, theses, PDT log | thesis_manager, risk_manager |

---

## Recommended Project Structure

```
scripts/
├── pipeline/               # New signal pipeline modules
│   ├── __init__.py         # Package init; exports PipelineResult
│   ├── regime.py           # Phase 1: RegimeState + top_risk_score
│   ├── exposure.py         # Phase 2: ExposureDecision
│   ├── screeners.py        # Phase 3: list[RawSignal]
│   ├── aggregator.py       # Phase 4: list[AggregatedSignal]
│   ├── analyzer.py         # Phase 5: list[ClaudeRecommendation] (agent mode)
│   ├── sizer.py            # Phase 6: qty per AggregatedSignal
│   ├── thesis_manager.py   # Phase 8: thesis lifecycle in SQLite
│   └── postmortem.py       # Phase 8b: outcome tracking + weight feedback
├── models.py               # Extended: RegimeState, ExposureDecision, RawSignal, AggregatedSignal
├── market_scanner.py       # Unchanged: OHLCV + indicators
├── risk_manager.py         # Unchanged: circuit breaker, PDT, position limits
├── order_executor.py       # Unchanged: Alpaca bracket/limit/market
├── state_store.py          # Extended: add theses table
├── bot.py                  # Rewritten scan_and_trade() internals; pipeline key detection
├── claude_analyzer.py      # DELETE (replaced by pipeline/analyzer.py)
└── strategies/             # DELETE (all 4 — replaced by screeners.py)
    ├── momentum.py
    ├── mean_reversion.py
    ├── breakout.py
    └── vwap.py
```

### Structure Rationale

- **`pipeline/` subdirectory:** Isolates new code from the working infrastructure that stays. The `scripts/strategies/` pattern (flat files per strategy class) did not survive backtest — the new pipeline/ package makes each phase a distinct boundary with testable inputs/outputs.
- **One module per phase:** Each file corresponds to exactly one pipeline stage. Debugging is easier when a bad conviction score traces to `aggregator.py` rather than a monolithic file.
- **`models.py` stays central:** All data contracts live here. No phase imports from another phase — they import from `models.py`. This prevents circular deps and makes contracts explicit.
- **`state_store.py` extended, not replaced:** Adding a `theses` table keeps all persistence in one place, which the existing crash recovery and reconcile logic already handles.

---

## Architectural Patterns

### Pattern 1: Stage-Gated Pipeline with Early Exit

**What:** Each phase runs sequentially. A phase that returns a "halt" signal causes the bot to skip to sell-only mode, never reaching execution.

**When to use:** Any time a condition makes new buys irrational (top_risk >= 70, exposure ceiling reached, circuit breaker active). Prevents the downstream phases from wasting compute on signals that will be blocked anyway.

**Trade-offs:** Simple control flow; easy to reason about. Downside: all phases are synchronous — Phase 3 (screeners) runs for the full watchlist even when only one symbol is interesting. Acceptable at 5-min polling, would not scale to 1000+ symbols.

**Example:**
```python
# bot.py: scan_and_trade() internals — new implementation
def scan_and_trade(...):
    # Phase 1: Regime (cached hourly)
    regime = get_or_refresh_regime(config)

    # Phase 2: Exposure ceiling — early exit on sell-only mode
    exposure = calculate_exposure(regime, config)
    if exposure.action == "SELL_ONLY":
        _scan_exits_only(scanner, executor, ...)
        return

    # Phase 3-4: Screeners + aggregation
    raw_signals = run_screeners(scanner, watchlist, regime, config)
    agg_signals = aggregate_signals(raw_signals, config)

    # Phase 5 (agent mode only): Claude analysis
    if config.get("agent_mode"):
        agg_signals = enrich_with_claude(agg_signals, regime, exposure)

    # Phase 6: Size each signal
    sized = [sizer.compute_qty(sig, exposure, config) for sig in agg_signals]

    # Phase 7: Risk + execution (existing — unchanged)
    for sig, qty in sized:
        order = executor.execute_signal(sig.to_signal(qty), sig.entry_price)

        # Phase 8: Thesis tracking
        if order:
            thesis_manager.promote_to_active(sig, order)
```

### Pattern 2: Hourly Regime Cache

**What:** Regime detection (FMP API calls for cross-asset ratios) runs once per hour, not every 5-minute cycle. The result (`RegimeState`) is stored in memory with a `cached_at` timestamp. Each 5-min cycle checks `(now - cached_at) > 3600s` before refreshing.

**When to use:** Any computation that requires external API calls slower than the scan interval, or produces a result that changes on hour/day timescales rather than minute timescales.

**Trade-offs:** Saves ~10 FMP API calls per hour. Risk: stale regime during fast market transitions. Mitigated by: top_risk score (fast-moving component) uses a shorter 30-min cache; macro regime (slow-moving) is fine at 1 hour.

**Example:**
```python
# pipeline/regime.py
_regime_cache: RegimeState | None = None
_regime_cached_at: float = 0.0
_REGIME_TTL = 3600.0   # 1 hour

def get_or_refresh_regime(fmp_client, config) -> RegimeState:
    if _regime_cache and (time.time() - _regime_cached_at < _REGIME_TTL):
        return _regime_cache
    return _refresh_regime(fmp_client, config)
```

### Pattern 3: Graceful FMP Degradation

**What:** Every pipeline component that depends on FMP API wraps its call in try/except and returns a safe neutral default when FMP is unavailable, not configured, or rate-limited.

**When to use:** All FMP-dependent components: regime.py, screeners.py (earnings drift, VCP). The technical screener (Alpaca data only) must always run.

**Trade-offs:** Reduced intelligence without FMP (regime defaults to `transitional`, FMP screeners disabled). Bot never breaks. FMP key absence is not an error condition.

**Example:**
```python
# pipeline/regime.py
def _refresh_regime(fmp_client, config) -> RegimeState:
    if fmp_client is None:
        return RegimeState(
            regime="transitional",
            regime_confidence=0.0,
            top_risk_score=30,
            risk_zone="green",
            cached_at=datetime.now(),
            components={},
        )
    try:
        return _compute_regime(fmp_client)
    except Exception as exc:
        logger.warning("Regime computation failed: {} — using neutral default", exc)
        return RegimeState(regime="transitional", top_risk_score=30, ...)
```

### Pattern 4: Weighted Conviction Aggregation

**What:** Multiple screeners produce RawSignals with a score (0-100) and source. The aggregator applies per-source weights, merges duplicate symbols, detects contradictions (BUY + SELL for same symbol), and applies recency decay. Sourced from edge-signal-aggregator's `DEFAULT_CONFIG`.

**When to use:** Whenever you want a single ranked conviction score across multiple heterogeneous sources, without requiring all sources to agree (unlike the old 2-of-N gate).

**Trade-offs:** More expressive than 2-of-N. Requires tuning weights — wrong weights produce low-quality signals. Initial weights from edge-signal-aggregator reference implementation, refined by postmortem feedback.

**Reference weights from edge-signal-aggregator:**
```python
DEFAULT_SOURCE_WEIGHTS = {
    "technical":       0.40,  # always runs; Alpaca data
    "earnings_drift":  0.35,  # FMP-dependent; high predictive value
    "vcp":             0.25,  # FMP-dependent; pattern quality signal
}
```

---

## Data Flow

### 5-Minute Cycle Flow (Autonomous Mode)

```
APScheduler tick (every 300s)
    │
    ├── Market closed? → log + return (no-op)
    │
    ├── Phase 1: regime.py.get_or_refresh_regime()
    │       └── RegimeState{regime, top_risk_score, risk_zone, cached_at}
    │
    ├── Phase 2: exposure.py.calculate_exposure(RegimeState)
    │       └── ExposureDecision{max_exposure_pct, bias, size_multiplier, action}
    │           action == "SELL_ONLY" → skip to exit scan
    │
    ├── Phase 3: screeners.py.run_screeners(watchlist, scanner, regime)
    │       ├── TechnicalScreener.scan(symbol, df)    ← always runs
    │       ├── EarningsDriftScreener.scan(symbol)    ← FMP, hourly cache
    │       └── VCPScreener.scan(symbol)              ← FMP, hourly cache
    │       └── list[RawSignal{symbol, source, score, confidence, action}]
    │
    ├── Phase 4: aggregator.py.aggregate(list[RawSignal])
    │       ├── Apply source weights
    │       ├── Dedup by symbol (merge bonuses for multi-source agreement)
    │       ├── Contradiction detection (BUY+SELL same symbol → exclude)
    │       └── list[AggregatedSignal{symbol, conviction, sources, action}]
    │           Filter: conviction >= min_conviction (0.50 default)
    │
    ├── Phase 6: sizer.py.compute_qty(AggregatedSignal, ExposureDecision)
    │       ├── ATR-based: qty = (account_equity * risk_pct) / (atr * multiplier)
    │       ├── Kelly: qty = kelly_fraction * bankroll / price (when history available)
    │       └── Cap: qty * price <= exposure_ceiling_remaining
    │
    ├── Phase 7: risk_manager.check_all() → order_executor.execute_signal()
    │       ├── circuit_breaker check
    │       ├── PDT check (< 3 day-trades in rolling 5 days for < $25k accounts)
    │       ├── max_positions check
    │       ├── budget_cap check
    │       └── Alpaca bracket/limit order submission
    │
    └── Phase 8: thesis_manager.on_fill(order, AggregatedSignal)
            └── theses table: ENTRY_READY → ACTIVE (on fill), ACTIVE → CLOSED (on exit)
```

### Agent Mode (Claude Analysis) Flow

```
Phase 4 output: list[AggregatedSignal]
    │
    ├── Phase 5: analyzer.py.build_prompt(AggregatedSignal, RegimeState, ExposureDecision)
    │       └── Regime-enriched prompt: "Market is in contraction. Top risk: 65/100.
    │            Exposure ceiling: 40%. Signal: AAPL BUY, conviction 0.72, sources:
    │            technical+earnings_drift. Analyze and confirm/reject."
    │
    ├── Claude response → ClaudeRecommendation{symbol, action, confidence, reasoning}
    │
    └── Phase 6+7: same sizer → risk_manager → executor path as autonomous mode
```

### Thesis Lifecycle (SQLite)

```
Signal generated
    └── thesis_manager.register_idea(RawSignal)
            → theses.status = "IDEA"

Conviction passes threshold
    └── thesis_manager.promote_to_entry_ready(AggregatedSignal)
            → theses.status = "ENTRY_READY"

Order filled (Alpaca callback or next-cycle position check)
    └── thesis_manager.promote_to_active(order)
            → theses.status = "ACTIVE", actual_entry, qty

Position closed (SELL order filled)
    └── thesis_manager.close(symbol, exit_price)
            → theses.status = "CLOSED", actual_exit, pnl
            → postmortem.py: compute outcome, adjust screener weights
```

---

## Build Order (Phase Dependencies)

The phases have a strict dependency order that maps directly to which modules must exist before others can be tested.

| Build Order | Component | Depends On | Rationale |
|-------------|-----------|------------|-----------|
| 1 | `models.py` extensions | Nothing | Data contracts must be defined before anything uses them. RegimeState, ExposureDecision, RawSignal, AggregatedSignal. |
| 2 | `state_store.py` theses table | models.py | thesis_manager needs the table to exist before writing. Add schema migration. |
| 3 | `pipeline/regime.py` | models.py, FMP client | Foundation of the gate logic. Everything downstream consumes RegimeState. Also: FMP client must exist or regime returns neutral default. |
| 4 | `pipeline/exposure.py` | regime.py (RegimeState) | Pure function: RegimeState → ExposureDecision. No external I/O. Test in isolation. |
| 5 | `pipeline/screeners.py` (technical only) | market_scanner.py, models.py | Technical screener works without FMP. Build and test independently of FMP screeners. |
| 6 | `pipeline/aggregator.py` | models.py (RawSignal → AggregatedSignal) | Can be tested with synthetic RawSignals from step 5. No external I/O. |
| 7 | `pipeline/sizer.py` | models.py (AggregatedSignal, ExposureDecision) | Pure function. Test ATR method first, Kelly second (requires trade history). |
| 8 | `bot.py` pipeline integration | All above + risk_manager + order_executor | Wire the pipeline into scan_and_trade(); add `pipeline` key detection for backward compat. |
| 9 | `pipeline/thesis_manager.py` | state_store.py (theses table), models.py | Can be added after Phase 7 works, since thesis tracking doesn't block execution. |
| 10 | `pipeline/screeners.py` FMP screeners | regime.py, FMP client | Add earnings_drift and VCP screeners once technical screener + aggregator are validated. |
| 11 | `pipeline/analyzer.py` | aggregator.py, regime.py | Claude analysis is agent-mode-only. Can be built after the autonomous pipeline runs cleanly. |
| 12 | `pipeline/postmortem.py` | thesis_manager.py, aggregator.py | Weight feedback requires closed theses to exist. Last to build, no blocking dependency. |

**Critical path:** 1 → 3 → 4 → 5 → 6 → 7 → 8 (minimum viable pipeline — runs without thesis tracking or postmortem).

---

## Anti-Patterns

### Anti-Pattern 1: Importing Skill Scripts Directly

**What people do:** `import sys; sys.path.insert(0, '/tmp/claude-trading-skills/...'); from macro_regime_detector import main`

**Why it's wrong:** The tradermonty scripts are CLI tools with `argparse`, file I/O (`reports/` directory), `sys.path` hacks, and hardcoded output paths. Importing them pulls in all that baggage. When the `/tmp/` clone is cleaned up, the bot silently breaks.

**Do this instead:** Read the calculator logic in `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/calculators/` and adapt the scoring math into `pipeline/regime.py` as pure in-memory functions. The data contracts (inputs: ETF price series; outputs: component scores) are simple enough to replicate without the CLI scaffolding.

### Anti-Pattern 2: Running Regime Detection Every 5 Minutes

**What people do:** Call the FMP API for 9 ETF price series on every scan cycle.

**Why it's wrong:** FMP free tier is 250 calls/day. Regime detection uses ~10 calls per run. At 5-min cycles during a 6.5-hour market day (78 cycles), that's 780 calls — 3x the free tier limit in one day.

**Do this instead:** Cache `RegimeState` with a 1-hour TTL (see Pattern 2 above). The macro regime changes on a 1-2 year horizon; checking hourly is already more frequent than necessary. The top_risk score, which changes faster, can use a 30-min TTL.

### Anti-Pattern 3: Conviction Threshold as a Hard Gate

**What people do:** Set `min_conviction = 0.50` and treat it as a binary pass/fail gate. If conviction is 0.49, the signal is completely discarded.

**Why it's wrong:** This recreates the same logic flaw as the old 2-of-N gate — a small difference in input produces a cliff-edge in output. A signal with conviction 0.49 and a VCP confirmation is often better than a signal at 0.51 from only one source.

**Do this instead:** Use the conviction score as a continuous weight on position size, not a binary gate. A signal at 0.55 gets a smaller position than a signal at 0.85. The hard gate exists only at an absolute minimum (e.g., 0.30) below which the signal is noise.

### Anti-Pattern 4: Thesis Lifecycle in YAML Files

**What people do:** Follow the trader-memory-core reference implementation, which writes YAML files to `state/theses/AAPL_thesis_2026-03-01.yaml`.

**Why it's wrong:** YAML files are not crash-safe. If the bot dies between writing the file and updating position state, the thesis is orphaned. Reconstruction after crash is manual.

**Do this instead:** Use the existing SQLite `state_store.py` with a `theses` table. The existing `reconcile_positions()` already handles crash recovery for positions — the same mechanism applies to theses.

### Anti-Pattern 5: Claude Directly Submitting Orders

**What people do:** Pass Alpaca credentials to Claude and let it call the API directly.

**Why it's wrong:** Claude can hallucinate symbols, prices, or quantities. An unchecked LLM call to Alpaca can submit wrong orders with no recovery path.

**Do this instead:** Claude operates as analyst only. Every `ClaudeRecommendation` returned by `analyzer.py` must pass through `risk_manager.py` before `order_executor.py` touches Alpaca. This invariant already exists in the current codebase and must be preserved in the rewrite.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Alpaca Markets | alpaca-py SDK via existing clients in `bot.py` | TradingClient (orders/positions), StockHistoricalDataClient (OHLCV), CryptoHistoricalDataClient |
| FMP API | New `fmp_client.py` module adapted from skill reference | Optional — `pipeline/regime.py` returns neutral defaults if absent. Rate limit: 250 calls/day free tier |
| Claude (LLM) | Tool calls from agent mode skill; no direct API call in Python code | Existing `execute_claude_recommendation()` path in `bot.py` unchanged |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `bot.py` ↔ `pipeline/` | Direct function calls; `bot.py` imports pipeline package | No queue or async — synchronous within each 5-min cycle |
| `pipeline/screeners.py` ↔ `market_scanner.py` | Direct call: `scanner.scan(symbol)` → DataFrame | Screeners consume existing DataFrames; no change to market_scanner.py |
| `pipeline/regime.py` ↔ `pipeline/exposure.py` | `RegimeState` dataclass passed by value | Pure function boundary — exposure.py has no side effects |
| `pipeline/aggregator.py` ↔ `pipeline/sizer.py` | `list[AggregatedSignal]` passed by value | Sizer does not modify aggregator output |
| `pipeline/` ↔ `risk_manager.py` | `Signal` dataclass (existing model) — sizer.py calls `.to_signal(qty)` | Risk manager sees the same Signal contract as before; no changes needed |
| `pipeline/thesis_manager.py` ↔ `state_store.py` | Direct SQLite writes via state_store methods | New `theses` table added; existing position/trade tables untouched |
| `pipeline/postmortem.py` ↔ `pipeline/aggregator.py` | Weight adjustment dict written to `pipeline_config` in SQLite or config | Initial version: log only; weight feedback in later iteration |

---

## Scaling Considerations

This bot runs on a single machine for a single account. Scaling concerns are about reliability and latency, not throughput.

| Scale | Architecture Adjustment |
|-------|------------------------|
| Current (1 account, 5-min loop) | Synchronous pipeline per cycle is correct. No parallelism needed. |
| Multiple watchlist symbols (20-50) | Technical screener is the bottleneck — one Alpaca API call per symbol. Add a batch-fetch path to `market_scanner.py` if scan time exceeds 30s. |
| FMP rate limit exceeded | Add a request counter in `fmp_client.py`. When approaching 250/day, disable FMP screeners for remaining calls; regime gets the remaining budget. |
| Multiple accounts | Not in scope. Would require per-account StateStore and RiskManager instances. |

### Scaling Priorities

1. **First bottleneck:** Alpaca API rate limits during symbol discovery/scanning. 50 symbols at 1 call each = 50 calls per 5 minutes. Alpaca free tier allows ~200 req/min — fine. Paid tier adds no concern.
2. **Second bottleneck:** FMP API daily call limit (250 free). Solved by caching. FMP calls only happen in regime.py and FMP-backed screeners, both cached at 30-60 min.

---

## Sources

- Direct inspection: `/home/parz/projects/trading-bot/scripts/bot.py` — existing APScheduler loop and scan_and_trade() structure
- Direct inspection: `/home/parz/projects/trading-bot/REWRITE-PLAN.md` — explicit phase ordering and data flow diagram
- Direct inspection: `/tmp/claude-trading-skills/skills/macro-regime-detector/` — regime detection component architecture (6 calculators, scorer, fmp_client)
- Direct inspection: `/tmp/claude-trading-skills/skills/exposure-coach/scripts/calculate_exposure.py` — exposure scoring weights and regime-to-score mapping
- Direct inspection: `/tmp/claude-trading-skills/skills/edge-signal-aggregator/scripts/aggregate_signals.py` — DEFAULT_CONFIG with source weights, dedup thresholds, contradiction penalties
- Direct inspection: `/tmp/claude-trading-skills/skills/market-top-detector/SKILL.md` — top_risk scoring methodology (0-100 composite, 6 components)
- Direct inspection: `/home/parz/projects/trading-bot/scripts/models.py` — existing Signal/ClaudeRecommendation data contracts

---
*Architecture research for: regime-aware trading signal pipeline rewrite*
*Researched: 2026-03-23*
