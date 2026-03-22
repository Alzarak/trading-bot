# Phase 3: Core Trading Loop - Research

**Researched:** 2026-03-21
**Domain:** Trading pipeline — market scanning, technical indicators, order execution, SQLite persistence, crash recovery, graceful shutdown, strategy modules
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None — all implementation choices are at Claude's discretion (pure infrastructure phase).

### Claude's Discretion
All implementation choices: module structure, class design, pipeline architecture, SQLite schema, test strategy, file layout.

### Deferred Ideas (OUT OF SCOPE)
None stated.

### Critical Notes from Prior Phases
- ALP-04 (Alpaca MCP server) has been DROPPED — all Alpaca access is SDK-only via alpaca-py
- Wash sale rule: deferred — no 31-day re-entry block in v1 (tracked as a Phase 3 blocker in STATE.md, resolved as out-of-scope for v1)
- PDT tracking uses a 7-calendar-day rolling window (plan spec overrides risk-rules.md's 5-business-days phrasing)
- Hook uses JSON permissionDecision deny format (not exit code 2)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORD-01 | Bot can submit market orders for immediate execution | `MarketOrderRequest` pattern in alpaca-api-patterns.md; confirmed via Alpaca SDK docs |
| ORD-02 | Bot can submit limit orders for controlled entry price | `LimitOrderRequest` with `limit_price` in alpaca-api-patterns.md |
| ORD-03 | Bot can submit bracket orders (entry + stop-loss + take-profit in one call) | `LimitOrderRequest` with `order_class=OrderClass.BRACKET` + `TakeProfitRequest` + `StopLossRequest` |
| ORD-04 | Bot can submit trailing stop-loss orders to lock in profits | `TrailingStopOrderRequest` with `trail_percent` in alpaca-api-patterns.md |
| ORD-05 | Bot uses ATR-based dynamic stop placement that scales with volatility | `pandas_ta.atr()` provides ATR; stop formula from risk-rules.md: `stop = entry - (ATR * multiplier)` |
| POS-03 | Bot closes or logs all open positions on graceful shutdown (SIGINT/SIGTERM) | `signal.signal()` handler sets shutdown flag; `trading_client.close_all_positions(cancel_orders=True)` |
| POS-04 | Bot reconciles local state against Alpaca's actual positions on startup (crash recovery) | `trading_client.get_all_positions()` at startup; compare against SQLite `positions` table; upsert to reconcile |
| TA-01 | Bot computes RSI indicator on configured timeframe | `df.ta.rsi(length=14)` → `RSI_14` column |
| TA-02 | Bot computes MACD indicator (signal line, histogram) | `df.ta.macd(fast=12, slow=26, signal=9)` → `MACD_12_26_9`, `MACDH_12_26_9`, `MACDS_12_26_9` |
| TA-03 | Bot computes EMA for trend detection | `df.ta.ema(length=9)`, `df.ta.ema(length=21)` → `EMA_9`, `EMA_21` |
| TA-04 | Bot computes ATR for volatility-based stops | `df.ta.atr(length=14)` → `ATRr_14` column |
| TA-05 | Bot computes Bollinger Bands for mean reversion signals | `df.ta.bbands(length=20, std=2)` → `BBL_20_2.0`, `BBM_20_2.0`, `BBU_20_2.0` |
| TA-06 | Bot computes VWAP for intraday price reference | `df.ta.vwap(anchor="D")` — requires DatetimeIndex; resets daily automatically |
| STRAT-01 | Momentum strategy — RSI + MACD + EMA crossover signal logic | Signal logic fully specified in references/trading-strategies.md |
| STRAT-02 | Mean reversion strategy — Bollinger Bands + RSI oversold/overbought | Signal logic fully specified in references/trading-strategies.md |
| STRAT-03 | Breakout strategy — 20-bar high breakout with volume confirmation | Signal logic fully specified in references/trading-strategies.md |
| STRAT-04 | VWAP reversion strategy — deviation from VWAP with time window guard | Signal logic fully specified in references/trading-strategies.md |
| STRAT-05 | Each strategy is a configurable module selectable via config | Strategy plugin pattern: base class + 4 concrete implementations; `config["strategies"]` drives selection |
| ALP-05 | Plugin queries Alpaca market clock to enforce market hours (9:30am–4:00pm ET) | `trading_client.get_clock()` → `clock.is_open`; documented in alpaca-api-patterns.md |
| STATE-01 | Bot persists trading state to SQLite database (positions, orders, trade history) | Python stdlib `sqlite3`; 4 tables: positions, orders, trade_log, day_trades |
| STATE-02 | Bot recovers from crashes by reconciling SQLite state against Alpaca positions | Startup: fetch `get_all_positions()`, upsert against SQLite `positions` table |
| OBS-01 | Bot logs every trade to file (timestamp, ticker, action, price, quantity, P&L) | loguru `logger.bind(trade=True)` with structured JSON sink; file rotation built-in |
| OBS-02 | Bot tracks portfolio P&L (daily and total return) using Alpaca account endpoint | `trading_client.get_account()` → `.equity`, `.portfolio_value`; computed vs `start_equity` |
| PLUG-02 | Separate agent for market scanning/analysis | `agents/market-analyst.md` with `model: sonnet` frontmatter |
| PLUG-04 | Separate agent for trade execution | `agents/trade-executor.md` with `model: sonnet` frontmatter |
</phase_requirements>

---

## Summary

Phase 3 builds the full autonomous trading pipeline. There are five distinct subsystems to implement: (1) the market scanner that fetches OHLCV bars from Alpaca and computes all 6 indicators via pandas-ta; (2) the signal generator that runs strategy-specific logic against indicator values and produces BUY/SELL/HOLD signals; (3) the order executor that wraps all 4 order types with idempotency keys and hands off to the existing `RiskManager.submit_with_retry()`; (4) the SQLite state store that persists positions, orders, trade log, and day-trade records with startup reconciliation and crash recovery; and (5) two Claude Code agent definition files for PLUG-02 and PLUG-04.

The strategies themselves are completely specified in `references/trading-strategies.md` — no design work is needed there. The alpaca-py SDK patterns for all order types and the Alpaca market clock are already documented in `references/alpaca-api-patterns.md`. The `RiskManager` class from Phase 2 is ready for reuse — every trade signal must pass through it before order submission.

The dominant technical risks are: (a) VWAP requiring a DatetimeIndex on the DataFrame (fetched bars need proper timezone-aware indexing); (b) IEX feed gaps (free tier may have missing 1-minute bars — the scanner must handle NaN values from pandas-ta without crashing); and (c) SQLite write contention if any future extension uses multiple threads (use `check_same_thread=False` and serialize writes via a lock from day one).

**Primary recommendation:** Structure the trading loop as a single `bot.py` script with a `BackgroundScheduler` (APScheduler 3.x) that fires a `scan_and_trade()` job every minute on weekdays between 9:30–16:00 ET. The scheduler's main thread handles signal registration. Graceful shutdown sets a flag, the scheduler job checks it before acting, and the SIGTERM handler explicitly calls `scheduler.shutdown(wait=False)` then `close_all_positions()`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alpaca-py | 0.43.2 | `TradingClient` for orders + positions + market clock; `StockHistoricalDataClient` for OHLCV bars | Only maintained Alpaca SDK; established in Phase 1 |
| pandas-ta | 0.4.71b0 | RSI, MACD, EMA, ATR, Bollinger Bands, VWAP via DataFrame extension | Pip-installable, no C compiler; Python 3.12+ (matches project) |
| pandas | >=2.0 | OHLCV DataFrame manipulation; required by pandas-ta | Industry standard; alpaca-py bar data maps directly to DataFrames |
| numpy | >=1.26 | Underlying numerical ops for indicator math | Implicit dependency of pandas-ta; use directly for position math |
| APScheduler | >=3.10,<4.0 | `BackgroundScheduler` with cron trigger for market-hours loop | 3.x API is stable; 4.x is an alpha rewrite — do not use |
| loguru | >=0.7 | Structured trade logging, rotating file sink, JSON serialization | Established in Phase 2 for RiskManager; one import, sane defaults |
| sqlite3 | stdlib | State persistence (positions, orders, trade log, day trades) | No install needed; sufficient for single-process bot; WAL mode for robustness |
| pydantic-settings | >=2.0 | Config loading from .env + config.json | Established in Phase 1 for BotConfig; consistent pydantic v2 usage |
| signal | stdlib | SIGINT/SIGTERM handlers for graceful shutdown | Zero deps; Python standard pattern for daemon processes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid | stdlib | `client_order_id` idempotency keys | Every order submission — already used by `submit_with_retry()` |
| zoneinfo | stdlib (3.9+) | `ZoneInfo("America/New_York")` for ET-aware timestamps | All market-hours checks and VWAP time window guards |
| math | stdlib | `math.floor()` for share quantity truncation | Position sizing (already used in RiskManager) |
| pathlib | stdlib | SQLite DB file path under `CLAUDE_PLUGIN_DATA` | State store initialization |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite3 stdlib | SQLAlchemy ORM | SQLAlchemy adds type-mapped models and migration tooling, but is overkill for 4 simple tables in a single-process bot. Direct sqlite3 is simpler, faster, and zero-dependency. |
| APScheduler BackgroundScheduler | `while True: time.sleep(60)` | Raw polling does not respect market hours, has no built-in error recovery, and cannot be paused/resumed. APScheduler handles cron expressions natively. |
| pandas-ta Strategy (batch) | Per-indicator function calls | `df.ta.strategy()` runs all indicators in one call (with optional multiprocessing) but outputs dynamic column names that vary by parameters. Per-function calls produce predictable column names — prefer for readability. |

**Installation (if needed in venv):**
```bash
pip install alpaca-py==0.43.2 "pandas-ta==0.4.71b0" "pandas>=2.0" "numpy>=1.26" "APScheduler>=3.10,<4.0" "pydantic-settings>=2.0" "loguru>=0.7"
```

---

## Architecture Patterns

### Recommended Project Structure
```
scripts/
├── bot.py                 # Entry point: scheduler + signal handlers + main loop
├── market_scanner.py      # Fetches OHLCV bars + computes all indicators
├── signal_generator.py    # Runs strategy logic, returns Signal dataclass
├── order_executor.py      # Wraps order types + calls RiskManager.submit_with_retry()
├── portfolio_tracker.py   # Reads Alpaca account + tracks P&L; logs to SQLite
├── state_store.py         # SQLite CRUD: positions, orders, trade_log, day_trades
├── strategies/
│   ├── __init__.py        # BaseStrategy ABC + registry dict
│   ├── momentum.py        # MomentumStrategy
│   ├── mean_reversion.py  # MeanReversionStrategy
│   ├── breakout.py        # BreakoutStrategy
│   └── vwap.py            # VWAPStrategy
└── risk_manager.py        # Existing from Phase 2 — no changes needed
agents/
├── market-analyst.md      # PLUG-02: Claude Code agent for scanning/analysis
└── trade-executor.md      # PLUG-04: Claude Code agent for execution
```

### Pattern 1: Technical Indicator Computation (pandas-ta)

**What:** Call per-indicator functions on the OHLCV DataFrame. Each call appends a new column.
**When to use:** Any time fresh bar data is fetched for a ticker.
**Column naming is deterministic** — always match by exact parameterized name.

```python
# Source: pandas-ta PyPI docs + tradingstrategy.ai docs
import pandas_ta as ta

def compute_indicators(df: pd.DataFrame, strategy_params: dict) -> pd.DataFrame:
    """Compute all 6 required indicators. DataFrame must have DatetimeIndex."""
    df.ta.rsi(length=strategy_params.get("rsi_period", 14), append=True)
    # → RSI_14

    df.ta.macd(
        fast=strategy_params.get("macd_fast", 12),
        slow=strategy_params.get("macd_slow", 26),
        signal=strategy_params.get("macd_signal", 9),
        append=True,
    )
    # → MACD_12_26_9, MACDH_12_26_9, MACDS_12_26_9

    df.ta.ema(length=strategy_params.get("ema_short", 9), append=True)
    df.ta.ema(length=strategy_params.get("ema_long", 21), append=True)
    # → EMA_9, EMA_21

    df.ta.atr(length=strategy_params.get("atr_period", 14), append=True)
    # → ATRr_14

    df.ta.bbands(
        length=strategy_params.get("bb_period", 20),
        std=strategy_params.get("bb_std_dev", 2.0),
        append=True,
    )
    # → BBL_20_2.0, BBM_20_2.0, BBU_20_2.0

    # VWAP requires DatetimeIndex with timezone info
    df.ta.vwap(anchor="D", append=True)
    # → VWAP_D

    return df
```

**Critical VWAP requirement:** The DataFrame index must be a DatetimeIndex. When fetching bars via alpaca-py, `bars.df` returns a multi-level index (symbol, timestamp). After `reset_index(level=0, drop=True)`, the timestamp becomes the index. Ensure it is timezone-aware (ET) before calling `df.ta.vwap()`. If the index is naive, pandas-ta raises `AttributeError: 'DatetimeIndex' object has no attribute 'to_period'`.

```python
# Correct: ensure timezone-aware DatetimeIndex after fetching bars
df = bars.df.reset_index(level=0, drop=True)
if df.index.tz is None:
    df.index = df.index.tz_localize("America/New_York")
```

### Pattern 2: Strategy Plugin Architecture

**What:** Base class + concrete strategy classes; registry dict keyed by config name.
**When to use:** At startup, load strategies from `config["strategies"]` list; at each scan cycle, call `strategy.generate_signal(df, params)`.

```python
# Source: standard Python ABC pattern
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

@dataclass
class Signal:
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float  # 0.0 – 1.0
    symbol: str
    strategy: str
    atr: float  # For stop calculation
    reasoning: str  # Human-readable for audit log

class BaseStrategy(ABC):
    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        """Generate trading signal from indicator DataFrame.

        Args:
            df: OHLCV DataFrame with all indicators already appended.
            params: Strategy-specific parameters from config.json.

        Returns:
            Signal dataclass with action, confidence, atr, and reasoning.
        """
        ...

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "vwap": VWAPStrategy,
}
```

### Pattern 3: SQLite State Store Schema

**What:** 4 tables covering the full trading lifecycle.
**When to use:** Initialized at startup; written on every order/position event; read at startup for crash recovery.

```python
# Source: Python stdlib sqlite3; standard trading bot pattern
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS positions (
    symbol          TEXT PRIMARY KEY,
    qty             INTEGER NOT NULL,
    entry_price     REAL NOT NULL,
    stop_price      REAL NOT NULL,
    strategy        TEXT NOT NULL,
    opened_at       TEXT NOT NULL,  -- ISO 8601
    alpaca_order_id TEXT,
    status          TEXT NOT NULL DEFAULT 'open'  -- open | closed
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT UNIQUE NOT NULL,
    alpaca_order_id TEXT,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,  -- buy | sell
    order_type      TEXT NOT NULL,  -- market | limit | bracket | trailing_stop
    qty             INTEGER NOT NULL,
    limit_price     REAL,
    stop_price      REAL,
    status          TEXT NOT NULL,  -- submitted | filled | failed | cancelled
    submitted_at    TEXT NOT NULL,
    filled_at       TEXT
);

CREATE TABLE IF NOT EXISTS trade_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    action          TEXT NOT NULL,  -- BUY | SELL
    price           REAL NOT NULL,
    qty             INTEGER NOT NULL,
    pnl             REAL,           -- NULL for entries; calculated on exits
    strategy        TEXT NOT NULL,
    order_type      TEXT NOT NULL,
    logged_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS day_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    date            TEXT NOT NULL   -- YYYY-MM-DD
);
"""
```

**Note:** The existing `RiskManager._pdt_trades` uses an in-memory list + JSON file. For Phase 3, day trades should be migrated to the `day_trades` SQLite table for unified crash recovery. The RiskManager's `_load_pdt_trades()` / `_save_pdt_trades()` can be replaced with StateStore queries — or the StateStore can expose the same interface.

### Pattern 4: Crash Recovery — Position Reconciliation

**What:** At startup, fetch live positions from Alpaca and reconcile against SQLite.
**When to use:** Every time `bot.py` starts — before the scheduler begins.

```python
# Source: alpaca-api-patterns.md + sqlite3 stdlib pattern
def reconcile_positions(trading_client, state_store) -> None:
    """Sync SQLite positions table with Alpaca's actual open positions.

    Three cases:
    1. Position in Alpaca but NOT in SQLite → insert (bot crashed before persisting)
    2. Position in SQLite as 'open' but NOT in Alpaca → mark as 'closed' (filled externally)
    3. Position in both → update qty/price from Alpaca (source of truth)
    """
    alpaca_positions = {p.symbol: p for p in trading_client.get_all_positions()}
    local_open = state_store.get_open_positions()  # Returns dict[symbol, row]

    for symbol, position in alpaca_positions.items():
        state_store.upsert_position(
            symbol=symbol,
            qty=int(position.qty),
            entry_price=float(position.avg_entry_price),
            # stop_price unknown after crash — set to 0.0 and log warning
            stop_price=float(getattr(position, "stop_price", 0.0)),
            strategy="unknown_post_crash",
        )

    for symbol in local_open:
        if symbol not in alpaca_positions:
            state_store.mark_position_closed(symbol)
            logger.warning("Position {} in SQLite but not in Alpaca — marked closed", symbol)
```

### Pattern 5: Graceful Shutdown with Signal Handlers

**What:** Register SIGINT and SIGTERM handlers that set a flag; scheduler checks flag before each job; on shutdown, close all positions.
**When to use:** `bot.py` startup, before `scheduler.start()`.

```python
# Source: Python stdlib signal docs; standard daemon pattern
import signal as signal_module

_shutdown_requested = False

def _handle_shutdown(signum, frame):
    global _shutdown_requested
    logger.info("Shutdown signal received ({}). Finishing current cycle...", signum)
    _shutdown_requested = True

signal_module.signal(signal_module.SIGINT, _handle_shutdown)
signal_module.signal(signal_module.SIGTERM, _handle_shutdown)

def scan_and_trade():
    if _shutdown_requested:
        return  # Skip — shutdown in progress

    # ... normal scan/trade logic ...

# After scheduler loop ends (scheduler.shutdown() called in handler):
def perform_graceful_shutdown(trading_client, state_store):
    logger.info("Closing all open positions...")
    positions = trading_client.get_all_positions()
    for pos in positions:
        try:
            trading_client.close_position(pos.symbol)
            state_store.mark_position_closed(pos.symbol)
            logger.info("Closed position: {}", pos.symbol)
        except Exception as exc:
            logger.error("Failed to close {}: {}", pos.symbol, exc)
    logger.info("Graceful shutdown complete.")
```

### Pattern 6: APScheduler Market-Hours Loop

**What:** BackgroundScheduler with IntervalTrigger + market-hours guard.
**When to use:** Main trading loop — fires every 60 seconds, guard prevents action outside market hours.

```python
# Source: APScheduler 3.x userguide docs
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BackgroundScheduler(timezone="America/New_York")
scheduler.add_job(
    func=scan_and_trade,
    trigger=IntervalTrigger(seconds=60),
    id="trading_loop",
    name="Market Scanner",
    misfire_grace_time=30,   # Skip job if it fires >30s late (e.g., on startup)
    coalesce=True,           # If multiple missed fires, run only once
)
scheduler.start()
```

**Market-hours guard inside `scan_and_trade()`:**
```python
# Check Alpaca's clock (authoritative for holidays, early closes)
clock = trading_client.get_clock()
if not clock.is_open:
    logger.debug("Market closed — skipping scan cycle")
    return
```

The Alpaca clock is the authoritative source — it handles all US market holidays and early close days automatically. Do not implement a local holiday calendar.

### Anti-Patterns to Avoid

- **Raw polling loop:** `while True: time.sleep(60)` does not handle market hours, holidays, or clean shutdown. Use APScheduler.
- **Naive VWAP index:** Calling `df.ta.vwap()` on a DataFrame with a timezone-naive DatetimeIndex raises `AttributeError`. Always localize before computing VWAP.
- **Column name drift:** If ATR period changes (e.g., from 14 to 21), the column name becomes `ATRr_21`. Always derive column names programmatically from params: `f"ATRr_{params['atr_period']}"`.
- **Blocking the scheduler thread:** Do not call `time.sleep()` inside `scan_and_trade()`. If a symbol takes too long, the scheduler misses the next firing. Each symbol scan should be fast (< 5 seconds).
- **Duplicate PDT storage:** The existing `pdt_trades.json` and the new `day_trades` SQLite table would be out of sync. Pick one. Recommendation: migrate to SQLite in `state_store.py` and have `RiskManager` accept a `state_store` parameter instead of managing its own JSON file.
- **Missing NaN guard:** The IEX free feed has gaps — some 1-minute bars are missing. After computing indicators, `df.dropna()` before reading the last row, or check `pd.isna()` on indicator values before generating signals.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Technical indicators (RSI, MACD, EMA, ATR, BB, VWAP) | Custom indicator math | `pandas_ta.rsi()`, `pandas_ta.macd()`, etc. | Off-by-one errors in rolling windows, look-ahead bias, incorrect VWAP anchor resets — all solved in pandas-ta |
| Market holiday calendar | Local dict of US holidays | `trading_client.get_clock().is_open` | Alpaca accounts for all NYSE holidays and early closes including irregular ones (e.g., September 11 half-days) |
| Exponential backoff retry | Custom retry loop | `RiskManager.submit_with_retry()` (Phase 2) | Already implemented with ghost-position prevention, 422/403 skip, 5 attempts |
| Position size calculation | Custom equity math | `RiskManager.calculate_position_size()` (Phase 2) | Already handles `claude_decides` clamping, budget cap, zero-share rejection |
| Idempotency keys | Custom deduplication | `uuid.uuid4()` as `client_order_id` | Alpaca uses `client_order_id` to deduplicate on their side — no custom tracking needed |

**Key insight:** All risk logic is Phase 2 infrastructure. Phase 3 calls into it, never reimplements it. Any direct `trading_client.submit_order()` call that bypasses `RiskManager.submit_with_retry()` is an architectural violation.

---

## Common Pitfalls

### Pitfall 1: VWAP Fails on Timezone-Naive Index

**What goes wrong:** `df.ta.vwap()` raises `AttributeError: 'DatetimeIndex' object has no attribute 'to_period'` when the index lacks timezone information.

**Why it happens:** pandas-ta's VWAP implementation calls `df.index.to_period(anchor)` internally. This method requires a timezone-aware index to convert correctly to daily periods.

**How to avoid:** After `bars.df.reset_index(level=0, drop=True)`, immediately localize: `df.index = df.index.tz_localize("America/New_York")` (if naive) or `df.index = df.index.tz_convert("America/New_York")` (if UTC, which Alpaca returns).

**Warning signs:** `AttributeError` on `ta.vwap()` calls; also appears if the DataFrame has too few bars (fewer than the anchor period).

### Pitfall 2: IEX Feed Gaps Cause NaN Indicators

**What goes wrong:** `df.iloc[-1]["RSI_14"]` returns `NaN` and the strategy generates a false HOLD or crashes with `TypeError: '>' not supported between instances of 'float' and 'NaN'`.

**Why it happens:** The free Alpaca tier uses IEX feed which has sparser coverage than SIP. Some 1-minute bars are missing, leaving gaps in the time series. pandas-ta propagates NaN through rolling calculations.

**How to avoid:** After computing all indicators, call `df = df.dropna()` to discard incomplete bars. Then validate: `if df.empty: return Signal(action="HOLD", ...)`. Also check for NaN explicitly on critical values before signal logic.

**Warning signs:** Strategy generates HOLD for every bar despite clear market movement; `df.shape[0]` is much less than expected for the time range.

### Pitfall 3: Duplicate PDT Storage (pdt_trades.json + SQLite)

**What goes wrong:** The bot launches, `StateStore` initializes SQLite `day_trades` table, but `RiskManager` still reads from `pdt_trades.json`. After a crash recovery, the two stores are out of sync — PDT count is wrong.

**Why it happens:** Phase 2 persisted PDT trades in a JSON file. Phase 3 introduces SQLite. If both mechanisms survive, they diverge on any crash.

**How to avoid:** In Phase 3, modify `RiskManager.__init__` to accept an optional `state_store` parameter. When provided, `check_pdt_limit()` and `record_day_trade()` delegate to `state_store`; when absent (backward compatibility for tests), fall back to JSON. Migrate the `pdt_trades.json` data into SQLite on first startup.

**Warning signs:** PDT count inconsistency after restart; `pdt_trades.json` and SQLite `day_trades` table have different row counts.

### Pitfall 4: Bracket Orders Rejected for Fractional Stop Prices

**What goes wrong:** `TakeProfitRequest(limit_price=152.3456789)` or `StopLossRequest(stop_price=148.1234567)` is rejected with HTTP 422.

**Why it happens:** Alpaca requires prices rounded to 2 decimal places for most US equities (some allow up to 4). The ATR-based stop formula produces floating point results that need rounding.

**How to avoid:** Always round order prices: `round(stop_price, 2)`. Same for `take_profit_price` and `limit_price`. Do this in `order_executor.py` before constructing any request object.

**Warning signs:** HTTP 422 responses from Alpaca on bracket orders but not market orders; errors mentioning "price precision" or "invalid price".

### Pitfall 5: Scheduler Thread vs. Signal Handler Race

**What goes wrong:** SIGTERM arrives while `scan_and_trade()` is mid-execution (e.g., waiting for an Alpaca API call). The scheduler shutdown races with the ongoing job, causing uncaught exceptions.

**Why it happens:** APScheduler's `BackgroundScheduler` runs jobs in threads. The signal handler runs in the main thread. If `scheduler.shutdown(wait=True)` is called from the signal handler (main thread), it blocks waiting for the job thread to complete — which is the correct behavior. But if `wait=False` is used and `close_all_positions()` runs immediately, it may conflict with an in-flight order.

**How to avoid:** Set `_shutdown_requested = True` in the signal handler and let the current job cycle finish naturally. After `scheduler.shutdown(wait=True)`, then call `perform_graceful_shutdown()`. Do not call `close_all_positions()` from within the signal handler directly.

**Warning signs:** `RuntimeError: Scheduler is already running` on restart; unclosed SQLite connections in logs; positions show in Alpaca but not in SQLite after crash.

### Pitfall 6: ATR Column Name Mismatch

**What goes wrong:** Code reads `df.iloc[-1]["ATR_14"]` but pandas-ta produces `ATRr_14` (note the lowercase `r`). `KeyError: 'ATR_14'` at runtime.

**Why it happens:** pandas-ta uses `ATRr_N` (with `r` suffix for "real" ATR, as opposed to percentage ATR `ATRp_N`).

**How to avoid:** Always derive column names programmatically from the function return value or use the documented name: `atr_col = f"ATRr_{params['atr_period']}"`. Same for all indicators — check exact column names via `df.ta.rsi(length=14).name` once and document them.

**Warning signs:** `KeyError` mentioning the indicator name at runtime; silent HOLD signals from the strategy (the signal generator catches the exception and returns HOLD).

---

## Code Examples

### Fetch Bars and Compute Indicators

```python
# Source: alpaca-api-patterns.md (verified) + pandas-ta docs (verified)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas_ta as ta

ET = ZoneInfo("America/New_York")

def fetch_bars_with_indicators(
    data_client: StockHistoricalDataClient,
    symbol: str,
    strategy_params: dict,
    days_back: int = 60,
) -> pd.DataFrame:
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=datetime.now(ET) - timedelta(days=days_back),
        end=datetime.now(ET),
        feed="iex",
    )
    bars = data_client.get_stock_bars(request)
    df = bars.df.reset_index(level=0, drop=True)

    # Ensure timezone-aware index (Alpaca returns UTC)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("America/New_York")

    # Compute all 6 indicators
    df = compute_indicators(df, strategy_params)

    # Drop rows with NaN from rolling window warmup
    df = df.dropna()
    return df
```

### Trade Log Entry (OBS-01)

```python
# Source: loguru docs + structured logging pattern
from loguru import logger

# Configure trade log sink at startup
logger.add(
    "trades_{time:YYYY-MM-DD}.log",
    format="{message}",
    filter=lambda record: "trade" in record["extra"],
    rotation="1 day",
    retention="90 days",
    serialize=True,  # JSON format
)

# Log a trade
trade_logger = logger.bind(trade=True)
trade_logger.info(
    "TRADE",
    ticker=symbol,
    action="BUY",
    price=round(fill_price, 4),
    qty=shares,
    pnl=None,
    strategy=strategy_name,
    order_type="bracket",
)
```

### Market Hours Guard

```python
# Source: alpaca-api-patterns.md
def is_market_open(trading_client) -> bool:
    clock = trading_client.get_clock()
    return clock.is_open
```

### Signal Dataclass (Shared Contract)

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class Signal:
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float       # 0.0 – 1.0
    symbol: str
    strategy: str
    atr: float              # Current ATR value for stop calculation
    stop_price: float       # Pre-computed: entry_price - (atr * multiplier)
    reasoning: str          # Audit log — which conditions triggered
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `alpaca-trade-api` streaming | `alpaca-py StockHistoricalDataClient` REST polling | 2023 (deprecation) | REST polling on 1-min bars is the v1 approach; WebSockets deferred per REQUIREMENTS.md |
| Hardcoded holiday calendar | `trading_client.get_clock().is_open` | Alpaca market clock API | Alpaca handles all NYSE holidays, early closes automatically |
| TA-Lib (C library) | pandas-ta (pure Python) | Project start — per CLAUDE.md | pandas-ta requires no compilation; TA-Lib is faster but breaks on user installs |

**Deprecated/outdated:**
- `alpaca-trade-api`: Deprecated by Alpaca 2023. Do not use.
- APScheduler 4.x: Alpha rewrite, breaking API changes from 3.x. All docs/examples are 3.x — use `APScheduler>=3.10,<4.0`.

---

## Open Questions

1. **Wash sale rule (v1 scope)**
   - What we know: STATE.md flags this as a blocker to resolve during Phase 3 planning.
   - Resolution: Deferred — no 31-day re-entry block in v1. The bot can re-enter the same symbol the next day. Document this limitation in `references/risk-rules.md`. No implementation needed in Phase 3.

2. **PDT Storage Migration**
   - What we know: `RiskManager._pdt_trades` currently uses `pdt_trades.json`. Phase 3 adds SQLite `day_trades` table. Dual storage will diverge on crash.
   - Recommendation: Extend `RiskManager` constructor to accept an optional `state_store` parameter. When provided, delegate PDT read/write to `state_store`. Existing tests remain valid (they pass `None` or omit the parameter, falling back to JSON).

3. **IEX vs SIP feed for free tier**
   - What we know: Alpaca free tier uses IEX feed. SIP feed requires a subscription. IEX has sparser coverage with potential 1-minute bar gaps.
   - Recommendation: Use `feed="iex"` as established in alpaca-api-patterns.md. Implement NaN guard (`df.dropna()`) after indicator calculation. This is sufficient for v1 — perfect bar coverage is not required.

4. **ATR stop price for VWAP strategy exits**
   - What we know: VWAP strategy exits when price returns to VWAP (target) OR drops 2% further below VWAP (stop). This is not ATR-based unlike the other three strategies.
   - Recommendation: For VWAP strategy, `stop_price` in the Signal is calculated as `entry_price * (1 - max_deviation_pct / 100)` rather than ATR formula. The `Signal.atr` field is still populated (for audit/logging) but the stop is percentage-based.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none — discovered via `tests/` directory |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |
| Venv path | `.venv/bin/python -m pytest tests/ -x -q` |

**Note:** The project `.venv` has pytest 9.0.2 but not the trading dependencies (loguru, alpaca-py, pandas-ta, etc.). These must be installed before tests that import from `scripts/` can run. Use `python -m pytest tests/ -x -q --ignore=tests/test_risk_manager.py` to run only structural tests in CI, or install deps first.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TA-01 | RSI computed correctly on known data | unit | `python -m pytest tests/test_market_scanner.py::TestIndicators::test_rsi -x` | ❌ Wave 0 |
| TA-02 | MACD columns appear with correct names | unit | `python -m pytest tests/test_market_scanner.py::TestIndicators::test_macd -x` | ❌ Wave 0 |
| TA-03 | EMA_9 and EMA_21 columns computed | unit | `python -m pytest tests/test_market_scanner.py::TestIndicators::test_ema -x` | ❌ Wave 0 |
| TA-04 | ATRr_14 column computed | unit | `python -m pytest tests/test_market_scanner.py::TestIndicators::test_atr -x` | ❌ Wave 0 |
| TA-05 | Bollinger Bands upper/mid/lower present | unit | `python -m pytest tests/test_market_scanner.py::TestIndicators::test_bbands -x` | ❌ Wave 0 |
| TA-06 | VWAP_D column computed; requires timezone-aware index | unit | `python -m pytest tests/test_market_scanner.py::TestIndicators::test_vwap -x` | ❌ Wave 0 |
| ORD-01 | market order submitted with correct params | unit (mock) | `python -m pytest tests/test_order_executor.py::TestOrderTypes::test_market_order -x` | ❌ Wave 0 |
| ORD-02 | limit order submitted with limit_price | unit (mock) | `python -m pytest tests/test_order_executor.py::TestOrderTypes::test_limit_order -x` | ❌ Wave 0 |
| ORD-03 | bracket order has take_profit and stop_loss legs | unit (mock) | `python -m pytest tests/test_order_executor.py::TestOrderTypes::test_bracket_order -x` | ❌ Wave 0 |
| ORD-04 | trailing stop order has trail_percent | unit (mock) | `python -m pytest tests/test_order_executor.py::TestOrderTypes::test_trailing_stop -x` | ❌ Wave 0 |
| ORD-05 | ATR-based stop price is entry - (ATR * multiplier) | unit | `python -m pytest tests/test_order_executor.py::TestStopCalc::test_atr_stop -x` | ❌ Wave 0 |
| STATE-01 | SQLite tables created on init; CRUD roundtrip works | unit | `python -m pytest tests/test_state_store.py -x` | ❌ Wave 0 |
| STATE-02 | Crash recovery: Alpaca position not in SQLite → inserted | unit (mock) | `python -m pytest tests/test_state_store.py::TestCrashRecovery -x` | ❌ Wave 0 |
| POS-03 | SIGTERM triggers position close before exit | integration (mock) | `python -m pytest tests/test_bot.py::TestGracefulShutdown -x` | ❌ Wave 0 |
| POS-04 | Alpaca positions reconciled into SQLite on startup | unit (mock) | `python -m pytest tests/test_state_store.py::TestReconcile -x` | ❌ Wave 0 |
| ALP-05 | Market clock check returns is_open | unit (mock) | `python -m pytest tests/test_market_scanner.py::TestMarketClock -x` | ❌ Wave 0 |
| STRAT-01 | Momentum BUY signal: RSI>30, MACD histogram positive, EMA crossover | unit | `python -m pytest tests/test_strategies.py::TestMomentum -x` | ❌ Wave 0 |
| STRAT-02 | Mean reversion BUY: price below lower BB, RSI<30 | unit | `python -m pytest tests/test_strategies.py::TestMeanReversion -x` | ❌ Wave 0 |
| STRAT-03 | Breakout BUY: new 20-bar high, volume >1.5x average | unit | `python -m pytest tests/test_strategies.py::TestBreakout -x` | ❌ Wave 0 |
| STRAT-04 | VWAP BUY: price >1.5% below VWAP, RSI<40, 10–15h ET | unit | `python -m pytest tests/test_strategies.py::TestVWAP -x` | ❌ Wave 0 |
| STRAT-05 | Strategy loaded from config name via registry | unit | `python -m pytest tests/test_strategies.py::TestRegistry -x` | ❌ Wave 0 |
| OBS-01 | Trade log entry written to file with all required fields | unit | `python -m pytest tests/test_portfolio_tracker.py::TestTradeLog -x` | ❌ Wave 0 |
| OBS-02 | P&L computed as (current_equity - start_equity) / start_equity | unit (mock) | `python -m pytest tests/test_portfolio_tracker.py::TestPnL -x` | ❌ Wave 0 |
| PLUG-02 | agents/market-analyst.md has model: sonnet frontmatter | structural | `python -m pytest tests/test_agents.py::TestMarketAnalyst -x` | ❌ Wave 0 |
| PLUG-04 | agents/trade-executor.md has model: sonnet frontmatter | structural | `python -m pytest tests/test_agents.py::TestTradeExecutor -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

All test files for Phase 3 are new — none exist yet:

- [ ] `tests/test_market_scanner.py` — covers TA-01 through TA-06, ALP-05
- [ ] `tests/test_signal_generator.py` — signal dataclass construction (optional, strategies cover signal output)
- [ ] `tests/test_order_executor.py` — covers ORD-01 through ORD-05
- [ ] `tests/test_state_store.py` — covers STATE-01, STATE-02, POS-04
- [ ] `tests/test_strategies.py` — covers STRAT-01 through STRAT-05
- [ ] `tests/test_portfolio_tracker.py` — covers OBS-01, OBS-02
- [ ] `tests/test_bot.py` — covers POS-03 (graceful shutdown)
- [ ] `tests/test_agents.py` — covers PLUG-02, PLUG-04 (structural, like existing test_hook.py)
- [ ] Framework / deps install: `uv pip install -r requirements.txt` into `.venv` — loguru missing from .venv causes test_risk_manager.py collection failure

---

## Sources

### Primary (HIGH confidence)
- `references/alpaca-api-patterns.md` — All order types, market clock, position management, error handling patterns (project-internal reference, verified against Alpaca docs)
- `references/risk-rules.md` — ATR stop formula, circuit breaker, PDT rules, order safety
- `references/trading-strategies.md` — All 4 strategy signal logics, entry/exit conditions, default params
- `scripts/risk_manager.py` — Phase 2 implementation; confirms class interface, column names, PDT tracking
- [pandas-ta PyPI](https://pypi.org/project/pandas-ta/) — version 0.4.71b0, Python 3.12+ requirement
- [tradingstrategy.ai VWAP docs](https://tradingstrategy.ai/docs/api/technical-analysis/overlap/help/pandas_ta.overlap.vwap.html) — `anchor="D"` default, DatetimeIndex requirement
- [Alpaca positions reference](https://alpaca.markets/sdks/python/api_reference/trading/positions.html) — `get_all_positions()`, `get_open_position()` raises `APIError` if no position
- [APScheduler 3.x userguide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — BackgroundScheduler, IntervalTrigger, cron trigger, `coalesce`, `misfire_grace_time`
- [Alpaca market clock API](https://alpaca.markets/sdks/python/api_reference/trading/clock.html) — `is_open`, `next_open`, `next_close` fields

### Secondary (MEDIUM confidence)
- [Alpaca Market Data FAQ](https://docs.alpaca.markets/docs/market-data-faq) — IEX vs SIP feeds, free tier uses IEX, ~5 years IEX history
- [Python signal stdlib](https://docs.python.org/3/library/signal.html) — `signal.signal(SIGTERM, handler)` pattern
- [loguru GitHub](https://github.com/Delgan/loguru) — `bind()`, `serialize=True`, `rotation`, `retention`

### Tertiary (LOW confidence — single source, not independently verified)
- pandas-ta MACD column naming (`MACD_12_26_9`, `MACDH_12_26_9`, `MACDS_12_26_9`) — derived from WebSearch results; verify against `df.ta.macd().columns` at implementation time
- ATR column naming (`ATRr_14` not `ATR_14`) — from community forum posts; verify in Wave 0 test setup

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries established in Phase 1/2; versions pinned in requirements.txt
- Architecture: HIGH — patterns derived from alpaca-api-patterns.md and risk-rules.md (project-verified references)
- Technical indicators: HIGH (general API) / MEDIUM (exact column names) — pandas-ta column naming verified by source inspection; ATR/MACD names need runtime confirmation
- Pitfalls: MEDIUM — VWAP timezone issue and NaN gap issue are known pandas-ta behaviors; ATR column name pitfall needs runtime confirmation
- SQLite schema: HIGH — standard Python sqlite3 pattern; schema designed to exactly match state described in risk-rules.md and requirements

**Research date:** 2026-03-21
**Valid until:** 2026-06-21 (stable stack; alpaca-py minor versions may change but API surface is stable)
