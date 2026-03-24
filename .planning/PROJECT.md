# Trading Bot Pipeline Rewrite

## What This Is

A rewrite of the trading bot's signal generation and decision-making pipeline, replacing failed strategy classes (momentum, mean_reversion, breakout, vwap — 23/100 backtest, negative expectancy) with a skill-based architecture adapted from tradermonty/claude-trading-skills. The bot scans markets autonomously, detects macro regime, generates signals via multiple screeners, aggregates conviction scores, sizes positions, and executes trades through Alpaca — all on a 5-minute loop.

## Core Value

The pipeline must gate entries by macro regime risk and aggregate multi-source signals with weighted conviction scoring — replacing the failed 2-of-N entry gate with a system that has positive expectancy.

## Requirements

### Validated

- ✓ Alpaca order execution (bracket/limit/market/crypto) — existing order_executor.py
- ✓ Risk management (circuit breaker, PDT, retry logic) — existing risk_manager.py
- ✓ SQLite state persistence and crash recovery — existing state_store.py
- ✓ P&L tracking and trade logging — existing portfolio_tracker.py
- ✓ Signal/ClaudeRecommendation data contracts — existing models.py
- ✓ Market data fetch + pandas-ta indicators — existing market_scanner.py
- ✓ APScheduler loop, client creation, shutdown — existing bot.py
- ✓ Pipeline data contracts (RegimeState, ExposureDecision, RawSignal, AggregatedSignal) — Phase 1
- ✓ FMP API client with graceful degradation and caching — Phase 1
- ✓ Macro regime detection (5 types, 6 cross-asset ratio calculators) — Phase 1
- ✓ Market top risk scoring (0-100, 6 sub-components, split TTL cache) — Phase 1
- ✓ Exposure coaching (4 gating rules, configurable thresholds) — Phase 1

### Active
- [ ] Technical screener with improved scoring (not 2-of-N gate)
- [ ] Earnings drift screener (FMP-powered, optional)
- [ ] VCP pattern screener (FMP-powered, optional)
- [ ] Weighted conviction aggregation with dedup and contradiction detection
- [ ] Regime-aware Claude analysis prompts (replaces claude_analyzer.py)
- [ ] ATR-based position sizing with Kelly criterion option
- [ ] Thesis lifecycle tracking (IDEA→ENTRY_READY→ACTIVE→CLOSED in SQLite)
- [ ] Signal postmortem and weight feedback on thesis close
- [ ] Backward compatibility (strategies key fallback when no pipeline key)

### Out of Scope

- edge-pipeline-orchestrator — too complex for initial rewrite, adds research pipeline later
- canslim-screener — future phase if needed
- pead-screener — future phase if needed
- Real-time streaming data — 5-min polling is sufficient
- Direct skill script imports — adapt logic into pipeline modules, don't import CLI tools

## Context

The current bot's 4 strategies scored 23/100 on backtest with -0.012% per trade expectancy and 96.8% max drawdown. Root causes: 2-of-N entry gate too loose, ATR stops too tight for 5-min bars, no trend/regime filtering.

50 trading skills from tradermonty/claude-trading-skills (cloned to `/tmp/claude-trading-skills/`) provide reference implementations for regime detection (6+6 calculators), earnings analysis (5 calculators), signal aggregation, position sizing (3 methods), and thesis lifecycle management. These are CLI tools with argparse/file I/O — we extract scoring logic into in-memory pipeline modules.

The existing infrastructure (order_executor, risk_manager, state_store, portfolio_tracker, bot scheduler) is solid and stays. Only the signal generation → decision → sizing chain gets replaced.

FMP API is optional — without it, regime defaults to transitional/neutral, FMP screeners disabled, but technical screener (Alpaca data only) still works.

## Constraints

- **API**: Alpaca Markets for execution + data; FMP for fundamental data (optional)
- **Language**: Python 3.12+, alpaca-py 0.43.2, pandas-ta 0.4.71b0
- **Architecture**: Claude never submits orders directly — all recommendations route through deterministic Python risk checks
- **Compatibility**: If config has `strategies` key but no `pipeline` key, fall back to current behavior
- **Data storage**: Thesis lifecycle in SQLite (not YAML files) for crash recovery and atomic writes

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Adapt logic, don't import skill scripts | Tradermonty scripts are CLI tools with sys.path hacks, argparse, file I/O — extract scoring logic into pipeline modules | — Pending |
| FMP API optional with graceful degradation | Many skills need FMP; bot must function without it using neutral defaults | — Pending |
| Thesis lifecycle in SQLite not YAML | Crash recovery and atomic writes; consistent with existing state_store.py | — Pending |
| Regime gating rules (block buys at top_risk>=70, halve size in contraction) | Prevents entries in hostile market conditions — addresses root cause of negative expectancy | — Pending |
| ATR-based sizing default, Kelly when history available | ATR adapts to volatility; Kelly optimizes when win rate data exists | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-24 after Phase 1 completion*
