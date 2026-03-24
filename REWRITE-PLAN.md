# Trading Bot Rewrite: Skill-Based Pipeline Architecture

## Context

The current bot's strategies (momentum, mean_reversion, breakout, vwap) scored 23/100 on backtest with **negative expectancy** (-0.012% per trade, 96.8% max drawdown). Root causes: 2-of-N entry gate too loose, ATR stops too tight for 5-min bars, no trend/regime filtering.

The user acquired 50 trading skills from `tradermonty/claude-trading-skills` (cloned to `/tmp/claude-trading-skills/`). This plan rewrites the bot to use skill-based regime detection, multi-screener signal generation, weighted conviction scoring, and proper position sizing — replacing the failed strategy classes entirely.

## Architecture: What Stays vs What Goes

### KEEP (working infrastructure)
| File | Why |
|------|-----|
| `order_executor.py` | Alpaca bracket/limit/market/crypto orders work correctly |
| `risk_manager.py` | Circuit breaker, PDT, retry logic all solid |
| `state_store.py` | SQLite persistence, crash recovery |
| `portfolio_tracker.py` | P&L tracking, trade logging |
| `models.py` | Signal/ClaudeRecommendation contracts (extend, don't replace) |
| `market_scanner.py` | Alpaca data fetch + pandas-ta indicators (decouple from strategies) |
| `bot.py` | APScheduler, client creation, shutdown (rewrite `scan_and_trade()` internals) |

### DELETE
| File | Why |
|------|-----|
| `scripts/strategies/` (all 4) | Failed backtest. Replace with screener pipeline |
| `claude_analyzer.py` | Replace with regime-aware pipeline analyzer |

### NEW (create)
| File | Adapts From (tradermonty skill) |
|------|--------------------------------|
| `scripts/pipeline/__init__.py` | Package init |
| `scripts/pipeline/regime.py` | macro-regime-detector (6 calc modules + scorer), market-top-detector (6 calc modules + scorer) |
| `scripts/pipeline/exposure.py` | exposure-coach |
| `scripts/pipeline/screeners.py` | earnings-trade-analyzer (5 calc modules), vcp-screener, technical indicators from market_scanner |
| `scripts/pipeline/aggregator.py` | edge-signal-aggregator (aggregate_signals.py) |
| `scripts/pipeline/sizer.py` | position-sizer (position_sizer.py — 3 methods: fixed fractional, ATR, Kelly) |
| `scripts/pipeline/thesis_manager.py` | trader-memory-core (thesis lifecycle IDEA→ENTRY_READY→ACTIVE→CLOSED) |
| `scripts/pipeline/analyzer.py` | Replaces claude_analyzer.py with regime-aware prompts |
| `scripts/pipeline/postmortem.py` | signal-postmortem (outcome tracking, weight feedback) |

## New Pipeline Data Flow

```
APScheduler (5min loop)
    │
    ▼
Phase 1: REGIME GATE (regime.py) ─── cached hourly
    │  macro_regime: concentration/broadening/contraction/inflationary/transitional
    │  top_risk_score: 0-100
    ▼
Phase 2: EXPOSURE CEILING (exposure.py)
    │  max_exposure_pct, bias (risk_on/neutral/risk_off)
    │  If ceiling=0 or circuit_breaker → skip to sell-only scan
    ▼
Phase 3: SIGNAL GENERATION (screeners.py)
    │  Technical scan (RSI/MACD/EMA/BB — all watchlist, every cycle)
    │  Earnings drift (FMP, hourly, opt-in)
    │  VCP patterns (FMP, hourly, opt-in)
    │  → list[RawSignal]
    ▼
Phase 4: AGGREGATION (aggregator.py)
    │  Weighted conviction scoring, dedup, contradiction detection
    │  Filter by min_conviction (default 0.50)
    │  → list[AggregatedSignal] ranked by conviction
    ▼
Phase 5: CLAUDE ANALYSIS (analyzer.py) ─── agent mode only
    │  Regime + exposure + signals context in prompt
    │  → list[ClaudeRecommendation]
    ▼
Phase 6: POSITION SIZING (sizer.py)
    │  ATR-based (default), Kelly (when history available)
    │  Constrained by exposure ceiling
    │  → qty per signal
    ▼
Phase 7: RISK + EXECUTION (existing risk_manager.py + order_executor.py)
    │  Circuit breaker → PDT → position count → budget cap → submit
    ▼
Phase 8: THESIS TRACKING (thesis_manager.py)
    │  Register IDEA on signal, promote to ACTIVE on fill, CLOSE on exit
    │  Postmortem on close → feed back to screener weights
```

## Key Design Decisions

### 1. Adapt logic, don't import skill scripts
The tradermonty scripts are CLI tools with `sys.path.insert()`, argparse, file I/O to `reports/`. Each has internal `calculators/` subpackages (e.g., macro-regime-detector has 6 calculator modules + scorer + fmp_client + report_generator). We extract the **scoring logic** into our pipeline modules that work with in-memory data and return Python objects.

Reference implementations to adapt from:
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/calculators/` (6 calculators)
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/scorer.py` (classify_regime, composite_score)
- `/tmp/claude-trading-skills/skills/market-top-detector/scripts/calculators/` (6 calculators)
- `/tmp/claude-trading-skills/skills/earnings-trade-analyzer/scripts/calculators/` (5 calculators)
- `/tmp/claude-trading-skills/skills/edge-signal-aggregator/scripts/aggregate_signals.py` (DEFAULT_CONFIG with weights, dedup, contradictions)
- `/tmp/claude-trading-skills/skills/position-sizer/scripts/position_sizer.py` (3 sizing methods)

### 2. FMP API optional with graceful degradation
Many Tier 2/3 skills need FMP API. When no key is present:
- Regime defaults to `transitional` with `top_risk=30` (neutral)
- FMP screeners (earnings, VCP) are disabled
- Technical screener (Alpaca data only) still works
- Bot functions with reduced intelligence but never breaks

### 3. Regime gating rules
| Condition | Action |
|-----------|--------|
| `top_risk >= 70` | Block all new BUY signals, sell-only mode |
| `top_risk 41-69` | Reduce position sizes proportionally |
| `regime == "contraction"` | Halve max_position_pct |
| `regime == "concentration"` | Prefer large-cap, reduce small-cap weight |
| `exposure_ceiling <= current_exposure` | Block new entries |

### 4. Thesis lifecycle in SQLite (not YAML files)
The trader-memory-core skill uses YAML files in `state/theses/`. We adapt the lifecycle into a `theses` table in the existing SQLite database for crash recovery and atomic writes. Schema:
```sql
CREATE TABLE theses (
    thesis_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL,  -- IDEA/ENTRY_READY/ACTIVE/CLOSED
    source TEXT,           -- screener that generated it
    entry_price REAL, stop_price REAL, target_price REAL,
    actual_entry REAL, actual_exit REAL,
    qty REAL, pnl REAL,
    reasoning TEXT,
    metadata TEXT,         -- JSON blob for screener-specific data
    created_at TEXT, updated_at TEXT, closed_at TEXT
);
```

### 5. Backward compatibility
If config has `strategies` key but no `pipeline` key, fall back to current behavior. Adding `pipeline` section opts into the new system.

## Extended Models (models.py additions)

```python
@dataclass
class RegimeState:
    regime: str           # broadening/concentration/contraction/inflationary/transitional
    regime_confidence: float
    top_risk_score: float  # 0-100
    risk_zone: str         # green/yellow/orange/red/critical
    cached_at: datetime
    components: dict

@dataclass
class ExposureDecision:
    max_exposure_pct: float  # 0-100
    bias: str                # risk_on/neutral/risk_off
    position_size_multiplier: float  # 0.0-1.0
    reason: str

@dataclass
class RawSignal:
    symbol: str
    action: str            # BUY/SELL
    source: str            # technical/earnings_drift/vcp
    score: float           # 0-100
    confidence: float      # 0-1
    reasoning: str
    entry_price: float
    stop_price: float
    atr: float
    asset_type: AssetType
    metadata: dict

@dataclass
class AggregatedSignal:
    symbol: str
    action: str
    conviction: float      # 0-1 weighted across sources
    sources: list[str]
    agreement_count: int
    contradictions: list[str]
    top_signal: RawSignal
    all_signals: list[RawSignal]
```

## Config Changes

```json
{
  "pipeline": {
    "scan_interval_seconds": 300,
    "regime_cache_ttl_seconds": 3600,
    "screeners": {
      "technical": {"enabled": true, "weight": 0.40},
      "earnings_drift": {"enabled": false, "weight": 0.20},
      "vcp": {"enabled": false, "weight": 0.20}
    },
    "min_conviction": 0.50,
    "regime_gating": {
      "block_buys_top_risk_above": 70,
      "reduce_size_contraction_pct": 50
    },
    "position_sizing_method": "atr",
    "risk_pct_per_trade": 1.0,
    "atr_multiplier": 2.0
  },
  "fmp_api_key_env": "FMP_API_KEY"
}
```

## Implementation Order (All in One Session)

Build all modules, then wire them together. FMP integration built but defaults to disabled (graceful degradation) until user adds `FMP_API_KEY` to `.env`.

### Step 1: Foundation
- Create `scripts/pipeline/` package with `__init__.py`
- Add `RegimeState`, `ExposureDecision`, `RawSignal`, `AggregatedSignal` to `models.py`
- Add `theses` table to `state_store.py`
- Add `pipeline` + `fmp_api_key_env` sections to config.json

### Step 2: FMP Client
- Write `scripts/pipeline/fmp_client.py` — HTTP client for FMP API with caching, rate limiting, graceful `None` returns when no key

### Step 3: Regime + Exposure
- `pipeline/regime.py` — adapt macro-regime-detector's 6 calculators + market-top-detector's 6 calculators into a single `RegimeDetector` class. FMP-powered with hourly caching. Returns neutral defaults when no FMP key.
- `pipeline/exposure.py` — `ExposureCoach` synthesizes `RegimeState` into `ExposureDecision` (max exposure %, size multiplier, bias)

### Step 4: Screeners
- `pipeline/screeners.py` — `ScreenerPipeline` class with:
  - `technical_scan()` — uses existing MarketScanner indicators (RSI/MACD/EMA/BB/ATR) with improved scoring (not 2-of-N gate). Always enabled.
  - `earnings_drift_scan()` — adapts earnings-trade-analyzer 5-factor scoring via FMP. Disabled by default.
  - `vcp_scan()` — adapts VCP pattern detection via FMP. Disabled by default.

### Step 5: Aggregator
- `pipeline/aggregator.py` — adapt edge-signal-aggregator's weighted conviction scoring, dedup config, agreement bonuses, contradiction detection. Works with 1 source (technical only) or N sources.

### Step 6: Position Sizer
- `pipeline/sizer.py` — adapt position-sizer's 3 methods (fixed fractional, ATR-based, Kelly criterion). Constrained by `ExposureDecision` ceiling. Wraps existing `risk_manager.calculate_position_size()` for budget enforcement.

### Step 7: Analyzer (replaces claude_analyzer.py)
- `pipeline/analyzer.py` — `PipelineAnalyzer` builds regime-aware prompts with aggregated signal context, exposure state, and thesis history. Same `parse_response()` interface.

### Step 8: Thesis Manager + Postmortem
- `pipeline/thesis_manager.py` — IDEA→ENTRY_READY→ACTIVE→CLOSED lifecycle in SQLite
- `pipeline/postmortem.py` — outcome tracking on close, weight feedback to aggregator

### Step 9: Wire Everything Together
- Rewrite `bot.py:scan_and_trade()` to run the 8-phase pipeline
- Update `bot.py:scan_and_trade_crypto()` similarly
- Update agent mode (`get_analysis_context`, `execute_claude_recommendation`) to use new analyzer
- Delete `scripts/strategies/` directory
- Delete `scripts/claude_analyzer.py`

### Step 10: Verify
- Import check: `python -c "from scripts.pipeline import regime, exposure, screeners, aggregator, sizer, analyzer, thesis_manager"`
- Dry run: `python scripts/bot.py` in paper mode — verify logs show regime state, signals, sizing
- Verify Alpaca orders still route through risk_manager
- Verify thesis state transitions in SQLite

## Verification

After each phase:
1. `python -c "from scripts.pipeline import ..."` — imports work
2. Run bot in paper mode: `python scripts/bot.py` — no crashes, signals generated
3. Check logs for regime state, exposure decisions, signal counts
4. Verify orders still route through risk_manager (circuit breaker, PDT, budget cap)
5. After Phase 4: verify thesis state transitions in SQLite

## Skill-to-Script Mapping Summary

| Tradermonty Skill | Our Script | What We Adapt |
|-------------------|-----------|---------------|
| macro-regime-detector | pipeline/regime.py | 6 calculators + scorer + FMP client |
| market-top-detector | pipeline/regime.py | 6 calculators + scorer + FMP client |
| exposure-coach | pipeline/exposure.py | Risk zone → exposure % mapping |
| edge-signal-aggregator | pipeline/aggregator.py | Weighted scoring, dedup, contradiction config |
| position-sizer | pipeline/sizer.py | 3 sizing methods (FF, ATR, Kelly) |
| earnings-trade-analyzer | pipeline/screeners.py | 5-factor scoring (gap, trend, volume, MA200, MA50) |
| vcp-screener | pipeline/screeners.py | VCP pattern detection logic |
| trader-memory-core | pipeline/thesis_manager.py | Thesis lifecycle, state machine |
| signal-postmortem | pipeline/postmortem.py | Outcome classification, weight feedback |
| portfolio-manager | (already installed as skill) | Use via Alpaca MCP in agent mode |
| edge-pipeline-orchestrator | (skip for now) | Too complex for initial rewrite — adds research pipeline later |
| canslim-screener | (future) | Phase 3+ if needed |
| pead-screener | (future) | Phase 3+ if needed |
