# Session Context — 2026-03-23

## What Was Done This Session

### 1. Crypto Trading Added to Bot
Added full cryptocurrency trading support alongside existing stocks via Alpaca API.

**Files modified:**
- `scripts/models.py` — Added `AssetType` enum (STOCK/CRYPTO), `asset_type` field on `Signal` + `ClaudeRecommendation`
- `scripts/market_scanner.py` — Added `CryptoHistoricalDataClient` support, `fetch_bars(crypto=True)`, `scan(crypto=True)`, `discover_crypto_symbols()`, `is_crypto_symbol()`, `normalize_crypto_symbol()`
- `scripts/order_executor.py` — Added `_submit_crypto_entry()` (limit + separate stop-loss, both GTC), PDT skip for crypto, `StopOrderRequest` import, `time_in_force` param on market/limit orders
- `scripts/risk_manager.py` — `calculate_position_size()` now returns fractional `float` for both stocks and crypto (stocks 2 decimal, crypto 4 decimal). Added `budget_override` param for separate crypto budget.
- `scripts/bot.py` — `create_clients()` returns 3-tuple with `CryptoHistoricalDataClient`. New `scan_and_trade_crypto()` 24/7 loop. Crypto scheduler job in `main()`.
- `scripts/claude_analyzer.py` — `build_analysis_prompt()` accepts `crypto=True` flag with crypto market context
- `skills/run/SKILL.md` — Updated `create_clients()` unpacking to 3-tuple
- `skills/initialize/SKILL.md` + `TR5/.claude/skills/trading-bot/initialize/SKILL.md` — Added Step 10 for crypto setup during initialization
- `TR5/trading-bot/config.json` — Added `crypto` section: `enabled`, `separate_budget`, `budget_usd`, `watchlist`, `scan_interval_seconds`

**Key Alpaca crypto constraints:**
- Order types: Market and Limit only (no bracket, no trailing stop)
- Time-in-force: `GTC` and `IOC` only (no `DAY`)
- No shorting, no margin
- Fractional quantities supported
- Symbol format: `BTC/USD` (slash notation)
- Same `TradingClient` + `/v2/orders` endpoint as stocks
- PDT rule does NOT apply to crypto

### 2. Fractional Shares Enabled for Stocks
- `risk_manager.py` `calculate_position_size()` now returns fractional `float` for stocks too (2 decimal places) instead of `math.floor` int
- `discover_symbols()` Tier 2 no longer caps by budget price — any stock is discoverable since Alpaca supports fractional shares
- Tier 1 (whole shares) still preferred, Tier 2 (fractional) fills remaining slots
- All order methods updated to accept `int | float` qty

### 3. Trading Skills Installed
Cloned `tradermonty/claude-trading-skills` repo to `/tmp/claude-trading-skills/`.

10 skills installed at project level (`/home/parz/projects/trading-bot/.claude/skills/`):
- `backtest-expert` — Strategy validation framework (5-dimension scoring)
- `position-sizer` — ATR/Kelly/Fixed Fractional sizing with Python script
- `technical-analyst` — Chart analysis
- `portfolio-manager` — Alpaca MCP integration for live position monitoring
- `macro-regime-detector` — Cross-asset regime classification (FMP API)
- `market-environment-analysis` — Global market conditions
- `edge-strategy-designer` — Strategy YAML spec generation
- `edge-strategy-reviewer` — Quality gate (PASS/REVISE/REJECT)
- `signal-postmortem` — Track signal outcomes
- `trader-memory-core` — Thesis lifecycle tracking
- `retag` — Git tag management (moved from global)

### 4. Backtest Results — Strategy FAILED
Ran walk-forward backtest of momentum strategy on 90 days of real Alpaca data (4 stocks + 3 crypto, ~34,162 trades):

```
Score: 23/100 — Verdict: ABANDON
Win Rate:     39.6%
Avg Win:      0.23%
Avg Loss:     0.17%
Max Drawdown: 96.8%
Expectancy:   -0.012% per trade (NEGATIVE)
Exit Reasons: stop=14291, tp=13226, signal=6608, timeout=37
```

**Root causes identified:**
1. 2-of-N entry gate too loose — low-conviction entries
2. ATR stop at 1.5x too tight for 5-min bars — noise triggers stops
3. No trend filter — buys in downtrends when MACD briefly improves
4. No regime filter — trades in all conditions including ranging markets

### 5. Decision: Rewrite From Scratch
User decided to abandon current strategy implementation and rewrite using the trading skills from `tradermonty/claude-trading-skills` as the foundation.

## What Needs To Happen Next

### Rewrite the trading bot scripts using skills from the cloned repo

The full repo is at `/tmp/claude-trading-skills/` (also available at `https://github.com/tradermonty/claude-trading-skills`).

**User provided a detailed tier analysis** of which skills map to which bot functions:

**TIER 1 — Core Bot Engine:**
1. `edge-pipeline-orchestrator` — Master orchestrator for research → signal → strategy pipeline
2. `edge-signal-aggregator` — Weighted conviction scoring + deduplication
3. `trader-memory-core` — Persistent thesis tracking (IDEA → ENTRY_READY → ACTIVE → CLOSED)
4. `portfolio-manager` — Live Alpaca MCP position monitoring
5. `position-sizer` — ATR/Kelly/Fixed Fractional with portfolio constraints

**TIER 2 — Market Analysis & Regime:**
6. `market-top-detector` — 0-100 correction probability score (FMP API)
7. `macro-regime-detector` — Structural regime classification
8. `market-breadth-analyzer` — Breadth health from CSV data
9. `uptrend-analyzer` — Market environment diagnosis
10. `exposure-coach` — Net exposure ceiling + cash allocation

**TIER 3 — Trade Screening:**
11. `earnings-trade-analyzer` — Post-earnings 5-factor scoring
12. `pead-screener` — Post-earnings drift
13. `canslim-screener` — O'Neil methodology (FinViz, no API)
14. `vcp-screener` — Minervini volatility contraction (no API)

**The task:** Map all relevant skills to the bot's script files and rewrite `market_scanner.py`, `strategies/momentum.py`, `order_executor.py`, `risk_manager.py`, `bot.py`, and potentially add new scripts using the patterns from these skills.

**Key infrastructure already working:**
- Alpaca API integration (stocks + crypto)
- `CryptoHistoricalDataClient` + `StockHistoricalDataClient`
- `AssetType` enum flowing through pipeline
- Fractional share support
- 24/7 crypto scan loop
- Config with crypto section
- SQLite state store
- APScheduler for scan loops

**What needs rewriting:**
- Strategy signal generation (momentum.py failed backtest)
- Entry/exit logic (too loose, stops too tight)
- Need to add regime/breadth filters
- Need proper position sizing (Kelly/ATR from position-sizer skill)
- Need signal aggregation instead of single-strategy scoring

## File Locations

| Path | Description |
|------|-------------|
| `/home/parz/projects/trading-bot/` | Project root (working dir) |
| `/home/parz/projects/trading-bot/TR5/` | NPX package source |
| `/home/parz/projects/trading-bot/scripts/` | Bot Python scripts |
| `/home/parz/projects/trading-bot/.claude/skills/` | Project-level skills (11 installed) |
| `/home/parz/projects/trading-bot/skills/` | Bot's own skills (initialize, build, run, trading-rules) |
| `/tmp/claude-trading-skills/` | Cloned tradermonty repo (full skill catalog) |
| `/home/parz/projects/trading-bot/TR5/trading-bot/venv/` | Python venv with alpaca-py 0.43.2 |
| `/home/parz/projects/trading-bot/reports/` | Backtest results |
| `/home/parz/projects/trading-bot/.claude/plans/spicy-yawning-conway.md` | Original crypto integration plan |

## Config

Config at `TR5/trading-bot/config.json`:
```json
{
  "budget_usd": 10,
  "max_position_pct": 5.0,
  "max_daily_loss_pct": 2.0,
  "paper_trading": true,
  "strategies": [{"name": "momentum", ...}],
  "confidence_threshold": 0.45,
  "watchlist": [],
  "market_hours_only": true,
  "crypto": {
    "enabled": false,
    "separate_budget": false,
    "budget_usd": 10,
    "watchlist": [],
    "scan_interval_seconds": 300
  }
}
```

## Installer
Run from TR5 directory: `cd TR5 && node ../bin/install.mjs`

## Pine Script Decision
Decided against Pine Script — it's a TradingView charting language, can't execute orders or run autonomously. Our Python + pandas-ta stack does the same indicator math with full control over execution.
