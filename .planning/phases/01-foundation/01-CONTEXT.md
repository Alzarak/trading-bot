# Phase 1: Foundation - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish typed data contracts (RegimeState, ExposureDecision, RawSignal, AggregatedSignal), a shared FMP API client with graceful degradation, macro regime detection with market top risk scoring, and exposure gating that blocks/reduces entries based on regime state. This phase produces the foundation that all downstream pipeline phases depend on — no signal generation or order execution changes yet.

</domain>

<decisions>
## Implementation Decisions

### FMP Degradation Behavior
- **D-01:** Silent degradation with log warning — when FMP API key is missing or rate-limited, log a warning once per cache cycle and continue with neutral defaults (regime=transitional, top_risk=30). Never raise exceptions to callers.
- **D-02:** FMP client returns `None` for individual endpoints on failure; each consumer applies its own default. This prevents one bad endpoint from disabling all FMP-dependent features.
- **D-03:** Use `requests-cache` with SQLite backend for persistent caching across bot restarts. Use `tenacity` for exponential backoff with jitter on 429/5xx responses.

### Regime Cache Strategy
- **D-04:** Split TTL — hourly (3600s) for macro regime label (uses weekly/monthly data that changes slowly), 15-minute (900s) for top_risk score (uses intraday ratios like RSP/SPY, HYG/LQD that can shift within a session).
- **D-05:** Cache is stored in-memory with timestamp; on bot restart, cache is cold and regime is re-fetched on first scan cycle. No persistent regime cache across restarts.

### Exposure Gating Thresholds
- **D-06:** Use REWRITE-PLAN.md thresholds as defaults: block all BUY signals when top_risk >= 70, halve max_position_pct when regime == contraction, block new entries when exposure_ceiling <= current_exposure.
- **D-07:** All thresholds are configurable via `pipeline.regime_gating` section in config.json — not hardcoded.
- **D-08:** When top_risk is 41-69, reduce position sizes proportionally (linear scaling between full size and half size).

### Data Model Placement
- **D-09:** Add all four new dataclasses (RegimeState, ExposureDecision, RawSignal, AggregatedSignal) to existing `scripts/models.py`, consistent with the existing Signal and ClaudeRecommendation pattern.
- **D-10:** Use `@dataclass` with `field(default_factory=dict)` for metadata/components dicts. Use `datetime` for timestamps. Use string literals for enum-like fields (regime types, risk zones, bias) — consistent with existing `Literal["BUY", "SELL", "HOLD"]` pattern.

### Claude's Discretion
- FMP client internal architecture (connection pooling, retry timing, cache eviction)
- Exact regime calculator implementations (adapt from reference skills as needed)
- Error logging format and verbosity levels
- Unit test structure for new modules

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Reference skill implementations
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/calculators/` — 6 regime calculator modules to adapt
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/scorer.py` — classify_regime(), composite_score() functions
- `/tmp/claude-trading-skills/skills/market-top-detector/scripts/calculators/` — 6 top risk calculator modules to adapt
- `/tmp/claude-trading-skills/skills/market-top-detector/scripts/scorer.py` — top risk scoring logic
- `/tmp/claude-trading-skills/skills/exposure-coach/` — Risk zone → exposure % mapping logic

### Existing codebase
- `scripts/models.py` — Existing Signal/ClaudeRecommendation dataclasses (extend, don't replace)
- `scripts/state_store.py` — SQLite patterns (WAL mode, row_factory, _create_tables pattern)
- `scripts/market_scanner.py` — Existing indicator computation (data source for regime calculators if needed)

### Project documentation
- `REWRITE-PLAN.md` — Full pipeline architecture, data flow, model definitions, config schema
- `.planning/research/PITFALLS.md` — Domain pitfalls including regime cache TTL split, ATR ratio bug
- `.planning/research/STACK.md` — Stack recommendations (requests-cache, tenacity versions)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/models.py` — Existing dataclass patterns with `@dataclass`, `field()`, `Literal[]`, `AssetType` enum
- `scripts/state_store.py` — SQLite connection pattern (WAL mode, row_factory=sqlite3.Row, `_create_tables()`)
- `scripts/market_scanner.py` — `MarketScanner.scan()` returns indicator DataFrames that regime calculators could consume for intraday ratios
- Conditional import pattern (`try/except ImportError`) used for alpaca-py — apply same for FMP client

### Established Patterns
- All modules use `loguru.logger` for logging
- Config loaded from `config.json` via `json.load()` in `bot.py`
- `snake_case` methods, `PascalCase` classes, `_private_helpers` prefix
- Section delimiters with dashed comment blocks for long classes
- `from __future__ import annotations` in type-heavy modules

### Integration Points
- `bot.py:scan_and_trade()` — will call regime/exposure in Phase 3, but models must be importable now
- `config.json` — needs `pipeline` and `fmp_api_key_env` sections added
- `.env` — FMP_API_KEY loaded via `os.environ.get()` (consistent with existing ALPACA_API_KEY pattern)

</code_context>

<specifics>
## Specific Ideas

- Adapt scoring logic from reference skills as pure functions with numeric inputs → float outputs, discarding CLI scaffolding (argparse, file I/O, sys.path hacks)
- The FMP client should be a single shared instance passed through the pipeline, not instantiated per-module
- Regime detection produces a `RegimeState` that gets logged on every scan cycle for observability

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-23*
