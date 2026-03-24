# Requirements: Trading Bot Pipeline Rewrite

**Defined:** 2026-03-23
**Core Value:** Replace failed 2-of-N entry gate with regime-gated, conviction-scored signal pipeline that has positive expectancy

## v1 Requirements

### Data Models

- [ ] **DATA-01**: RegimeState dataclass with regime type, confidence, top_risk_score, risk_zone, cache timestamp, and components dict
- [ ] **DATA-02**: ExposureDecision dataclass with max_exposure_pct, bias, position_size_multiplier, and reason
- [ ] **DATA-03**: RawSignal dataclass with symbol, action, source, score, confidence, reasoning, entry/stop/atr prices, asset_type, metadata
- [ ] **DATA-04**: AggregatedSignal dataclass with symbol, action, conviction, sources, agreement_count, contradictions, top_signal, all_signals

### FMP Client

- [ ] **FMP-01**: Shared FMP API client with per-endpoint caching (5-min TTL) and 250/day call counter
- [ ] **FMP-02**: Graceful degradation — returns None/defaults when no API key present, never raises exceptions
- [ ] **FMP-03**: Rate limit handling with exponential backoff via tenacity

### Regime Detection

- [ ] **REG-01**: Macro regime classification into 5 types (concentration/broadening/contraction/inflationary/transitional) using 6 cross-asset ratios
- [ ] **REG-02**: Market top risk scoring (0-100) with 6 sub-components producing risk zones (green/yellow/orange/red/critical)
- [ ] **REG-03**: Regime cache with split TTL — hourly for macro regime label, more frequent for top_risk intraday ratios
- [ ] **REG-04**: Defaults to transitional regime with top_risk=30 when FMP unavailable

### Exposure

- [ ] **EXP-01**: ExposureCoach synthesizes RegimeState into ExposureDecision (max exposure %, size multiplier, bias)
- [ ] **EXP-02**: Block all new BUY signals when top_risk >= 70 (sell-only mode)
- [ ] **EXP-03**: Halve max_position_pct when regime == contraction
- [ ] **EXP-04**: Block new entries when exposure_ceiling <= current_exposure

### Screeners

- [ ] **SCR-01**: Technical screener with weighted scoring (RSI momentum zone, MACD direction + histogram slope, EMA alignment, ATR-normalized range) replacing 2-of-N boolean gate
- [ ] **SCR-02**: ATR dollar conversion (not ratio) for stop distance calculation — fixing confirmed bug
- [ ] **SCR-03**: VCP pattern screener (Stage 2 uptrend + volatility contraction) via FMP, disabled without FMP key
- [ ] **SCR-04**: Earnings drift screener (PEAD — post-earnings surprise > +5%, price reaction > +2%, within 5 days) via FMP, disabled without FMP key

### Aggregation

- [ ] **AGG-01**: Weighted conviction scoring across all active screeners with configurable weights per source
- [ ] **AGG-02**: Deduplication — same symbol from multiple screeners merges into one AggregatedSignal
- [ ] **AGG-03**: Contradiction detection — screeners disagreeing on direction for same symbol reduces score by 30%
- [ ] **AGG-04**: Dynamic min_conviction threshold that scales by number of active sources (higher threshold when only 1 screener active)

### Position Sizing

- [ ] **SIZE-01**: ATR-based position sizing as default: qty = (account_risk_pct * equity) / (ATR * atr_multiplier)
- [ ] **SIZE-02**: Kelly criterion sizing when >= 30 closed theses exist per screener, using fractional Kelly (half-Kelly)
- [ ] **SIZE-03**: All sizing constrained by ExposureDecision ceiling and existing RiskManager max_position_pct

### Pipeline Analyzer

- [ ] **ANA-01**: Regime-aware Claude analysis prompts with RegimeState, ExposureDecision, and aggregated signal context injected
- [ ] **ANA-02**: Compatible ClaudeRecommendation output format (same parse_response interface)

### Thesis Lifecycle

- [ ] **THESIS-01**: SQLite theses table with IDEA→ENTRY_READY→ACTIVE→CLOSED state machine and atomic transitions
- [ ] **THESIS-02**: Register IDEA on signal generation, promote to ACTIVE on fill, CLOSE on exit
- [ ] **THESIS-03**: Prevent re-entry on same symbol while thesis is IDEA/ENTRY_READY/ACTIVE

### Integration

- [ ] **INT-01**: Rewrite bot.py scan_and_trade() to run the 8-phase pipeline
- [ ] **INT-02**: Update scan_and_trade_crypto() similarly
- [ ] **INT-03**: Update agent mode (get_analysis_context, execute_claude_recommendation) to use new analyzer
- [ ] **INT-04**: Pipeline config section in config.json with screener weights, regime thresholds, sizing params
- [ ] **INT-05**: Backward compatibility — if config has strategies key but no pipeline key, fall back to current behavior

### Postmortem

- [ ] **POST-01**: On thesis CLOSED, record outcome (realized return, true/false positive, regime mismatch classification)
- [ ] **POST-02**: Feed postmortem results back to screener conviction weights in aggregator

## v2 Requirements

### Advanced Screeners

- **ADV-01**: CANSLIM screener (8 criteria including earnings growth, RS rank, institutional sponsorship)
- **ADV-02**: PEAD screener with extended holding period analysis

### ML Integration

- **ML-01**: Pattern recognition from postmortem data to identify systematic Claude misses
- **ML-02**: Automated screener weight optimization from historical performance

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time streaming data | 5-min polling sufficient; negative expectancy is not a latency problem |
| Edge pipeline orchestrator (full) | Designed for interactive use; adapting for autonomous loops requires complete rewrite |
| Direct skill script imports | CLI tools with argparse/sys.path hacks — extract scoring logic only |
| Options strategy integration | Requires different Greeks-based sizing, expiry management, no models exist |
| Shorting / inverse positions | PDT interaction differs; validate long-side positive expectancy first |
| ML model training in-loop | GPU deps, stationarity requirements; Claude + heuristics sufficient for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| FMP-01 | Phase 1 | Pending |
| FMP-02 | Phase 1 | Pending |
| FMP-03 | Phase 1 | Pending |
| REG-01 | Phase 1 | Pending |
| REG-02 | Phase 1 | Pending |
| REG-03 | Phase 1 | Pending |
| REG-04 | Phase 1 | Pending |
| EXP-01 | Phase 1 | Pending |
| EXP-02 | Phase 1 | Pending |
| EXP-03 | Phase 1 | Pending |
| EXP-04 | Phase 1 | Pending |
| SCR-01 | Phase 2 | Pending |
| SCR-02 | Phase 2 | Pending |
| SCR-03 | Phase 2 | Pending |
| SCR-04 | Phase 2 | Pending |
| AGG-01 | Phase 2 | Pending |
| AGG-02 | Phase 2 | Pending |
| AGG-03 | Phase 2 | Pending |
| AGG-04 | Phase 2 | Pending |
| SIZE-01 | Phase 2 | Pending |
| SIZE-02 | Phase 2 | Pending |
| SIZE-03 | Phase 2 | Pending |
| ANA-01 | Phase 3 | Pending |
| ANA-02 | Phase 3 | Pending |
| THESIS-01 | Phase 3 | Pending |
| THESIS-02 | Phase 3 | Pending |
| THESIS-03 | Phase 3 | Pending |
| INT-01 | Phase 3 | Pending |
| INT-02 | Phase 3 | Pending |
| INT-03 | Phase 3 | Pending |
| INT-04 | Phase 3 | Pending |
| INT-05 | Phase 3 | Pending |
| POST-01 | Phase 4 | Pending |
| POST-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after roadmap creation*
