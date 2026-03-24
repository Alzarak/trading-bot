# Feature Research

**Domain:** Regime-aware multi-screener trading signal pipeline
**Researched:** 2026-03-23
**Confidence:** HIGH (tradermonty reference implementations verified directly; web search corroborates architecture patterns)

---

## Scope Clarification

This research covers only the **new pipeline layer** — the signal generation and decision chain between market data and order execution. The following already exist and are out of scope here:

- Order execution (order_executor.py)
- Risk management / circuit breaker / PDT (risk_manager.py)
- SQLite state and crash recovery (state_store.py)
- P&L tracking (portfolio_tracker.py)
- Market data fetch + pandas-ta indicators (market_scanner.py)
- Scheduler loop and client lifecycle (bot.py)

The pipeline layer sits between `MarketScanner.scan()` and `OrderExecutor`.

---

## Feature Landscape

### Table Stakes (Pipeline is unreliable or has negative expectancy without these)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Macro regime classification** | Without regime gating, entries happen in hostile conditions (root cause of 23/100 backtest). Must block buys when top_risk >= 70 and halve size during contraction. | MEDIUM | 5 regime types: Concentration, Broadening, Contraction, Inflationary, Transitional. Uses 6 cross-asset ratios (RSP/SPY, yield curve, HYG/LQD, IWM/SPY, SPY/TLT, XLY/XLP). FMP-powered; defaults to Transitional/neutral when FMP absent. |
| **Market top risk scoring (0-100)** | Regime classification alone is insufficient — need tactical risk score for sizing decisions. 2-8 week correction probability determines whether to allow new entries. | MEDIUM | 6 sub-components (distribution days, leading stock deterioration, defensive rotation, breadth, put/call ratio, VIX term). FMP-powered; requires graceful fallback to neutral (50) when FMP absent. |
| **Exposure decision output** | Pipeline must emit concrete trading posture: max exposure %, position size multiplier, bias (growth/value), action gate (NEW_ENTRY / REDUCE_ONLY / CASH_PRIORITY). Without this, regime data has no downstream effect. | LOW | Derived from regime + top_risk score. Pure computation — no additional API calls. Replaces the current `confidence_threshold` as the primary entry gate. |
| **Technical screener with weighted scoring** | The failed 2-of-N gate (any 2 of N indicators agree = enter) is the primary cause of negative expectancy. Replacement must score signal *strength*, not just signal *presence*. | MEDIUM | Scoring replaces boolean gate: RSI momentum zone, MACD direction + histogram slope, EMA alignment, ATR-normalized range. Output: float 0.0-1.0 per symbol. Operates on existing MarketScanner indicator DataFrames — no new data dependencies. |
| **Regime-aware Claude analysis prompts** | Current prompts are regime-blind. Claude must receive regime context, top_risk score, exposure ceiling, and contradicting signals in the prompt to produce regime-adjusted recommendations. | LOW | Replaces claude_analyzer.py prompt builder. Injects RegimeState + ExposureDecision into prompt preamble. JSON schema stays compatible with existing ClaudeRecommendation model. |
| **ATR-based position sizing** | Current sizing is flat-percentage. ATR-based sizing adapts stop distance to current volatility — reduces oversizing in volatile conditions, a contributor to 96.8% max drawdown. | LOW | Entry size = (account_risk_pct * equity) / (ATR * atr_multiplier). Already have ATR from MarketScanner. Default multiplier: 2.0. Constrained by existing RiskManager max_position_pct cap. |
| **FMP API client with graceful degradation** | Several screeners require FMP fundamental data. Without a shared, rate-limited client, parallel screeners will hit FMP's 250 calls/day free tier limit and crash. | LOW | Single FMP client instance with: per-endpoint 5-minute cache, 250/day call counter, automatic disable of FMP-dependent screeners on rate limit or missing key. Returns None/defaults — never raises exceptions to callers. |
| **Extended data models** | Pipeline produces new intermediate types that don't exist in models.py: RegimeState, ExposureDecision, RawSignal, AggregatedSignal. Without typed contracts, the pipeline is untestable and brittle. | LOW | Pure Python dataclasses. RawSignal carries: source_screener, symbol, direction, score (0-1), metadata dict. AggregatedSignal carries: symbol, composite_score, contributing_signals list, contradictions list. |
| **Thesis lifecycle tracking** | Without lifecycle state (IDEA→ENTRY_READY→ACTIVE→CLOSED), the pipeline re-evaluates and potentially re-enters the same position on every 5-minute cycle. | MEDIUM | SQLite-backed (consistent with existing state_store.py). Atomic writes. Crash-safe. States: IDEA (signal generated, not acted on), ENTRY_READY (cleared risk checks), ACTIVE (position open), CLOSED (position exited). |
| **Backward compatibility fallback** | Bot must continue operating when config has `strategies` key but no `pipeline` key. Without this, deploying the rewrite breaks all existing installations. | LOW | Check `config.get("pipeline")` at bot startup. If absent, route to existing strategy classes. If present, activate new pipeline. Zero behavioral change for non-pipeline configs. |

### Differentiators (Competitive advantage over simple indicator-following bots)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Weighted conviction aggregation with deduplication** | Multiple screeners seeing the same symbol creates artificial conviction inflation. Deduplication with source-weighted scoring produces honest composite scores and surfaces real agreement vs coincidence. | MEDIUM | Weights: technical screener (base), VCP screener (1.3x — high-quality setup), earnings drift screener (1.2x). Dedup: same symbol from multiple screeners merges into one AggregatedSignal. Contradiction detection: if screeners disagree on direction for same symbol, flag and reduce composite score by 30%. |
| **VCP pattern screener (Minervini)** | VCP setups (Stage 2 uptrend + volatility contraction) have structurally better risk/reward than random technical entries. Identifiable from price/volume data alone. | HIGH | Requires FMP for S&P 500 universe + daily price history. 5 criteria: Stage 2 trend (200DMA slope), volatility contracting (successive range tightenings), volume dry-up on pullbacks, pivot identification, ATR multiplier for stop. Disabled gracefully without FMP. |
| **Earnings drift screener (PEAD)** | Post-earnings announcement drift is one of the most replicated anomalies in academic finance. Stocks with earnings surprises continue drifting for 5-20 days — a predictable edge window. | HIGH | Requires FMP for earnings calendar + EPS surprise data. Filters: surprise > +5%, price reaction day-of > +2%, within 5 days of announcement. Outputs LONG signal with 10-day holding thesis. Disabled without FMP. |
| **Signal postmortem and weight feedback** | Most bots never learn which screeners actually work. Postmortem records true/false positive rates per screener on close, feeds back into conviction weights. Creates compounding improvement over time. | MEDIUM | On thesis CLOSED: fetch outcome (realized return vs predicted direction), classify (TRUE_POSITIVE / FALSE_POSITIVE / REGIME_MISMATCH), update source_screener weight in SQLite weight table. Weight adjustments apply on next cycle. |
| **Kelly criterion position sizing** | When thesis postmortem history accumulates sufficient win rate data per screener, Kelly-optimal sizing replaces ATR-fixed-fraction. Higher Sharpe on known-quality signal sources. | MEDIUM | Requires minimum 20 closed theses per screener to activate Kelly. Falls back to ATR-based sizing below threshold. Kelly fraction halved (fractional Kelly) for conservatism. Still capped by RiskManager max_position_pct. |
| **Pipeline config section in config.json** | Screener weights, FMP key, regime thresholds, and Kelly activation are runtime-tunable without code changes. Enables A/B testing of parameter sets without redeployment. | LOW | New `pipeline` key in config.json. Contains: `regime_thresholds` (block_buys_at_top_risk, halve_size_below), `screener_weights`, `fmp_api_key`, `kelly_min_history`, `conviction_threshold`. Documented in existing config.json schema. |

### Anti-Features (Commonly requested, but harmful here)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real-time streaming data** | Seems faster = better alpha | 5-min polling is sufficient for swing/intraday. Streaming adds WebSocket complexity, reconnect logic, message buffering, and partial-bar handling. Risk of acting on incomplete bars. Current 23/100 score is not a latency problem. | Keep existing 5-min APScheduler polling. Fix regime gating and scoring instead. |
| **Canslim screener** | Popular with O'Neil traders | Requires 8 criteria including earnings growth rate, relative price strength rank, and institutional sponsorship data — all FMP-dependent. Implementation is a multi-week project. Not the root cause of negative expectancy. | Defer to v2 after VCP and PEAD are validated. |
| **Edge pipeline orchestrator (full)** | Automated skill chaining looks powerful | The full edge-pipeline-orchestrator in the reference skills is designed for interactive use with filesystem-based inter-skill communication. Adapting it for autonomous 5-min loops requires a complete rewrite of its coordination model. It is explicitly marked Out of Scope in PROJECT.md. | Implement orchestration inline in bot.py as a simple sequential function call chain: regime → exposure → screeners → aggregation → Claude → sizing → execution. |
| **Direct skill script imports** | Reuse existing code | Tradermonty scripts are CLI tools with `argparse`, `sys.path` hacks, and file I/O to JSON/CSV. Importing them directly couples the pipeline to CLI conventions, breaks testability, and introduces subprocess overhead on every 5-min cycle. | Extract only the scoring logic (pure functions with numeric inputs/outputs) into pipeline modules. Discard CLI scaffolding. |
| **ML model training in-loop** | AI-powered = better | Training neural networks or transformer models during the trading loop introduces GPU dependencies, data stationarity requirements, and hours-long training cycles. Out of scope for this milestone. Current architecture with Claude analysis + heuristic scoring is sufficient to test positive expectancy. | Use Claude as the reasoning layer. Reserve ML training for a future research pipeline phase if postmortem data shows systematic patterns Claude misses. |
| **Options strategy integration** | Alpaca supports options | Options require different Greeks-based sizing, expiry management, assignment risk, and a separate approval workflow. The existing pipeline has no options models. Mixing options with equity signals creates conflicting sizing logic. | Equity + crypto only for this pipeline. Options as a separate future skill. |
| **Shorting / inverse positions** | More opportunities on both sides | Alpaca paper trading has limited short locate availability. PDT rules interact with short positions differently. Current RiskManager has no short position tracking. The failed strategies were long-only — adding shorts introduces a new failure mode before the long side is validated. | Long-only plus HOLD/SELL for exits. Short selling deferred until long pipeline shows positive expectancy in live paper trading. |

---

## Feature Dependencies

```
[Macro Regime Classification]
    └──requires──> [FMP API Client]           (needs FMP data; falls back to Transitional without it)
    └──enables──>  [Market Top Risk Scoring]  (regime context improves top risk interpretation)

[Market Top Risk Scoring]
    └──requires──> [FMP API Client]           (distribution days, breadth data)
    └──produces──> [Exposure Decision]

[Exposure Decision]
    └──requires──> [Macro Regime Classification]
    └──requires──> [Market Top Risk Scoring]
    └──gates──>    [Technical Screener]       (CASH_PRIORITY blocks new entries)
    └──gates──>    [VCP Screener]             (CASH_PRIORITY blocks new entries)
    └──gates──>    [Earnings Drift Screener]  (CASH_PRIORITY blocks new entries)
    └──scales──>   [ATR Position Sizing]      (position_size_multiplier from ExposureDecision)

[Technical Screener]
    └──requires──> [MarketScanner.scan()]     (existing, already available)
    └──produces──> [RawSignal list]

[VCP Screener]
    └──requires──> [FMP API Client]           (needs fundamental/price history)
    └──produces──> [RawSignal list]

[Earnings Drift Screener]
    └──requires──> [FMP API Client]           (needs earnings calendar + EPS surprise)
    └──produces──> [RawSignal list]

[Weighted Conviction Aggregation]
    └──requires──> [Technical Screener]       (at minimum one screener must be active)
    └──enhances──> [VCP Screener]             (merges VCP signals with 1.3x weight)
    └──enhances──> [Earnings Drift Screener]  (merges PEAD signals with 1.2x weight)
    └──produces──> [AggregatedSignal list]

[Regime-Aware Claude Analysis Prompts]
    └──requires──> [Exposure Decision]        (injected into prompt preamble)
    └──requires──> [AggregatedSignal]         (per-symbol context for Claude)
    └──produces──> [ClaudeRecommendation]     (existing model, no change)

[ATR Position Sizing]
    └──requires──> [ClaudeRecommendation]     (entry price via current bar)
    └──requires──> [Exposure Decision]        (position_size_multiplier)
    └──enhances──> [Kelly Criterion Sizing]   (Kelly activates when history is sufficient)

[Thesis Lifecycle Tracking]
    └──requires──> [AggregatedSignal]         (thesis created at IDEA state)
    └──enables──>  [Signal Postmortem]        (can only run postmortem on CLOSED theses)

[Signal Postmortem + Weight Feedback]
    └──requires──> [Thesis Lifecycle Tracking]
    └──enhances──> [Weighted Conviction Aggregation] (adjusts screener weights)
    └──enables──>  [Kelly Criterion Sizing]   (provides win rate history per screener)

[FMP API Client]
    └──enables──>  [Macro Regime Classification]
    └──enables──>  [Market Top Risk Scoring]
    └──enables──>  [VCP Screener]
    └──enables──>  [Earnings Drift Screener]

[Extended Data Models]
    └──required-by──> ALL new pipeline modules (typed contracts for testability)
```

### Dependency Notes

- **FMP API Client is a soft dependency**: All four FMP-dependent features degrade gracefully to neutral defaults. The pipeline functions with only Alpaca data — regime defaults to Transitional, top_risk defaults to 50 (neutral), FMP screeners disabled.
- **Exposure Decision gates three screeners**: When ExposureDecision.action == CASH_PRIORITY, screeners still run but no new IDEA theses are created. This preserves signal visibility for monitoring without executing trades.
- **Signal Postmortem enhances weights but is not blocking**: The pipeline operates with default weights on first run. Postmortem feedback is additive — weight table initialized to defaults, updated incrementally over time.
- **Kelly conflicts with ATR sizing**: Mutually exclusive per-screener. Kelly activates only when minimum history threshold met (`kelly_min_history` in config, default 20 closed theses). Below threshold, ATR-based sizing is always used.

---

## MVP Definition

### Launch With (v1 — addresses root cause of negative expectancy)

- [x] **Extended data models** — typed contracts for all new types; required by everything else
- [x] **FMP API client with graceful degradation** — shared, rate-limited, cached; required by regime/top/screeners
- [x] **Macro regime classification** — blocks entries in hostile conditions; root cause fix #1
- [x] **Market top risk scoring** — tactical entry gate; root cause fix #2
- [x] **Exposure decision output** — translates regime + risk into concrete posture; required by prompt builder
- [x] **Technical screener with weighted scoring** — replaces failed 2-of-N gate with scored signals
- [x] **Weighted conviction aggregation** — dedup + contradiction detection across screeners
- [x] **Regime-aware Claude analysis prompts** — injects regime context so Claude analysis is regime-calibrated
- [x] **ATR-based position sizing** — volatility-adjusted sizing; addresses 96.8% max drawdown root cause
- [x] **Thesis lifecycle tracking** — prevents re-entry on every cycle; IDEA→ENTRY_READY→ACTIVE→CLOSED
- [x] **Pipeline config section in config.json** — runtime-tunable thresholds
- [x] **Backward compatibility fallback** — existing installations unaffected

### Add After Validation (v1.x — differentiators that require v1 to be validated first)

- [ ] **VCP screener** — add when regime gating + technical scoring shows positive expectancy; validates FMP integration
- [ ] **Earnings drift screener** — add after VCP; requires same FMP client infrastructure
- [ ] **Signal postmortem + weight feedback** — add after accumulating 20+ closed theses from v1
- [ ] **Kelly criterion sizing** — unlocks automatically after postmortem accumulates sufficient history

### Future Consideration (v2+ — not needed to prove positive expectancy)

- [ ] **Canslim screener** — defer until VCP and PEAD show positive expectancy independently
- [ ] **Automated hypothesis generation** (trade-hypothesis-ideator pattern) — sophisticated but not the current gap
- [ ] **ML model training pipeline** — requires months of postmortem data to be meaningful
- [ ] **Options strategy layer** — separate architectural concern; deferred indefinitely

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Extended data models | HIGH | LOW | P1 |
| FMP API client | HIGH | LOW | P1 |
| Macro regime classification | HIGH | MEDIUM | P1 |
| Market top risk scoring | HIGH | MEDIUM | P1 |
| Exposure decision output | HIGH | LOW | P1 |
| Technical screener (weighted) | HIGH | MEDIUM | P1 |
| Weighted conviction aggregation | HIGH | MEDIUM | P1 |
| Regime-aware Claude prompts | HIGH | LOW | P1 |
| ATR position sizing | HIGH | LOW | P1 |
| Thesis lifecycle tracking | HIGH | MEDIUM | P1 |
| Pipeline config section | MEDIUM | LOW | P1 |
| Backward compatibility | HIGH | LOW | P1 |
| VCP screener | HIGH | HIGH | P2 |
| Earnings drift screener | HIGH | HIGH | P2 |
| Signal postmortem + feedback | MEDIUM | MEDIUM | P2 |
| Kelly criterion sizing | MEDIUM | MEDIUM | P2 |
| Canslim screener | LOW | HIGH | P3 |
| ML model training | LOW | HIGH | P3 |
| Options strategy layer | LOW | HIGH | P3 |

**Priority key:**
- P1: Required in v1 to achieve positive expectancy
- P2: Add after v1 validates the core pipeline
- P3: Future phases; not needed to prove the concept

---

## Competitor / Reference Feature Analysis

The tradermonty/claude-trading-skills reference implementations directly inform this feature set:

| Feature | Tradermonty Reference Skill | Our Adaptation |
|---------|-----------------------------|----------------|
| Macro regime classification | macro-regime-detector (6 components, FMP) | Extract scoring logic; remove CLI/file I/O; add SQLite caching |
| Market top risk scoring | market-top-detector (6 components, O'Neil/Minervini/Monty) | Extract scoring engine; WebSearch components replaced with Alpaca breadth data |
| Exposure decision | exposure-coach (synthesizes upstream outputs) | Inline computation from RegimeState + top_risk; no file-based orchestration |
| Technical screener | technical-analyst (chart-based) | Remap to pandas-ta indicators from MarketScanner; pure numeric scoring |
| VCP screener | vcp-screener (Minervini, FMP) | Port Python script logic directly; already well-structured |
| Earnings drift screener | pead-screener | Port scoring logic; FMP-dependent |
| Signal aggregation | edge-signal-aggregator (weights + dedup + contradiction) | Adapt for in-memory pipeline; remove YAML file I/O |
| Position sizing | position-sizer (ATR + Kelly) | Integrate into pipeline; constrained by existing RiskManager caps |
| Thesis lifecycle | trader-memory-core + edge-pipeline-orchestrator patterns | SQLite-backed; matches existing state_store.py conventions |
| Signal postmortem | signal-postmortem (4 outcome categories, weight feedback) | Adapt for autonomous loop; trigger on thesis CLOSED event |

---

## Sources

- [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) — Reference skill implementations (verified directly at /tmp/claude-trading-skills/)
- [Numin: Weighted-Majority Ensembles for Intraday Trading](https://arxiv.org/html/2412.03167v1) — Weighted aggregation patterns (MEDIUM confidence)
- [Macro trading signal optimization — Macrosynergy](https://macrosynergy.com/research/macro-trading-signal-optimization-basic-statistical-learning-methods/) — Signal quality measurement (MEDIUM confidence)
- PROJECT.md constraints and Out of Scope declarations (HIGH confidence — authoritative for this project)
- Existing codebase: market_scanner.py, claude_analyzer.py, models.py, risk_manager.py (HIGH confidence — verified directly)

---

*Feature research for: regime-aware multi-screener trading signal pipeline*
*Researched: 2026-03-23*
