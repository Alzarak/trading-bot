# Architecture

**Analysis Date:** 2026-03-22

## Pattern Overview

**Overall:** Plugin-first pipeline architecture with two distinct run modes

**Key Characteristics:**
- Claude Code plugin shell (`commands/`, `agents/`, `skills/`, `hooks/`) wraps a pure-Python trading backend (`scripts/`)
- The trading pipeline is unidirectional: data flows MarketScanner → Strategy/ClaudeAnalyzer → RiskManager → OrderExecutor → Alpaca — no layer calls back up the chain
- Claude is an analyst only, never an executor: `ClaudeAnalyzer` builds prompts and parses responses but never calls the Alpaca API directly
- Two orthogonal mode axes: **Alpaca access mode** (MCP vs SDK-only) × **run mode** (agent vs standalone)

## Layers

**Plugin Shell:**
- Purpose: Exposes three user-facing commands and wires Claude Code hooks
- Location: `commands/`, `agents/`, `skills/`, `hooks/`
- Contains: Command stubs that delegate to skill files, agent persona definitions, hook scripts
- Depends on: Skills (loaded at runtime), Python backend (invoked via Bash)
- Used by: Claude Code plugin system

**Skills (Workflow Logic):**
- Purpose: Procedural step-by-step instructions Claude follows to implement each command
- Location: `skills/initialize/SKILL.md`, `skills/run/SKILL.md`, `skills/build/SKILL.md`, `skills/trading-rules/SKILL.md`
- Contains: Markdown instructions with embedded Bash, mode-selection logic, safety rules
- Depends on: Python backend scripts, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` env vars
- Used by: Commands (via stub delegation)

**Trading Pipeline (Python):**
- Purpose: Core autonomous trading logic — data fetching, signal generation, risk enforcement, order execution
- Location: `scripts/`
- Contains: All Python modules — see Key Abstractions below
- Depends on: Alpaca API (via alpaca-py SDK), SQLite, pandas-ta indicators
- Used by: Agent mode (via inline Python invocations), standalone mode (direct execution)

**Strategies:**
- Purpose: Pluggable signal generators — each reads indicator DataFrames and returns a Signal
- Location: `scripts/strategies/`
- Contains: `BaseStrategy` ABC, four concrete implementations, `STRATEGY_REGISTRY` dict
- Depends on: `scripts/types.Signal`, pandas DataFrames from MarketScanner
- Used by: `bot.py:scan_and_trade()` (standalone mode), directly in agent mode

**Persistence:**
- Purpose: Crash-safe state across restarts
- Location: `scripts/state_store.py` (SQLite), `scripts/audit_logger.py` (NDJSON)
- Contains: Positions table, orders table, trade log table, day_trades table; audit/claude_decisions.ndjson
- Depends on: SQLite3 (stdlib), `CLAUDE_PLUGIN_DATA` env var for path resolution
- Used by: RiskManager (PDT count), OrderExecutor (position upsert), PortfolioTracker, AuditLogger

## Data Flow

**Standalone Mode (APScheduler loop):**

1. `bot.py:main()` loads `config.json` from `CLAUDE_PLUGIN_DATA`, creates Alpaca clients
2. `StateStore` opens SQLite at `CLAUDE_PLUGIN_DATA/trading.db`; reconciles positions from Alpaca
3. `RiskManager.initialize_session()` checks `circuit_breaker.flag`, captures start equity
4. `APScheduler` fires `scan_and_trade()` every 60 seconds
5. `MarketScanner.scan(symbol)` fetches OHLCV bars (Alpaca IEX feed) and computes 6 indicators via pandas-ta
6. Strategy from `STRATEGY_REGISTRY` calls `generate_signal(df, symbol, params)` → `Signal` dataclass
7. `OrderExecutor.execute_signal(signal, price)` runs 4 serial risk checks (circuit breaker → position count → PDT → position size)
8. On pass: submits bracket order (BUY) or market order (SELL) via `RiskManager.submit_with_retry()`
9. Position upserted in SQLite; trade logged to `trade_log` table
10. At 16:05 ET: `EODReportGenerator.generate()` → `Notifier.send()` for summary dispatch

**Agent Mode (Claude-in-the-loop):**

1. `/run` skill checks `config.json`, reads `autonomy_mode` and `use_mcp`
2. `get_analysis_context()` runs `MarketScanner.scan()` and `ClaudeAnalyzer.build_analysis_prompt()` for every watchlist symbol × strategy combination — returns dict of prompts
3. Claude (as `market-analyst` agent) reads each indicator table, reasons about the strategy conditions, and returns a `ClaudeRecommendation` JSON object (7 required fields)
4. `ClaudeAnalyzer.parse_response()` extracts JSON from Claude's response text, validates fields, applies confidence threshold (default 0.6)
5. `execute_claude_recommendation()` converts to `Signal` via `rec.to_signal()`, routes through `OrderExecutor.execute_signal()` — same 4 risk checks as standalone mode
6. `AuditLogger` writes every recommendation + execution outcome to `audit/claude_decisions.ndjson`
7. Claude asks user to continue or stop after each cycle

**State Management:**
- `StateStore` (SQLite WAL mode) is the single source of truth for open positions, PDT count, trade history
- `RiskManager` holds in-memory `circuit_breaker_triggered` flag (reset only on process restart after flag file deletion)
- `PortfolioTracker` computes P&L from SQLite trade log; never holds in-memory trade state

## Key Abstractions

**Signal:**
- Purpose: Typed contract between strategies/ClaudeAnalyzer and OrderExecutor
- File: `scripts/types.py`
- Pattern: `@dataclass` with fields `action` (BUY/SELL/HOLD), `confidence`, `symbol`, `strategy`, `atr`, `stop_price`, `reasoning`

**ClaudeRecommendation:**
- Purpose: Structured output from Claude analysis; converts to Signal via `to_signal()`
- File: `scripts/types.py`
- Pattern: Same shape as Signal but originates from parsed Claude JSON; `to_signal()` is the bridge

**BaseStrategy:**
- Purpose: ABC enforcing the `generate_signal(df, symbol, params) → Signal` contract
- File: `scripts/strategies/base.py`
- Pattern: Inherit and implement `generate_signal()`. Register name in `STRATEGY_REGISTRY` in `scripts/strategies/__init__.py`

**STRATEGY_REGISTRY:**
- Purpose: Config-name → class mapping for dynamic strategy loading
- File: `scripts/strategies/__init__.py`
- Pattern: `{"momentum": MomentumStrategy, "mean_reversion": MeanReversionStrategy, "breakout": BreakoutStrategy, "vwap": VWAPStrategy}` — `bot.py` indexes by `strategy_config["name"]`

**ClaudeAnalyzer:**
- Purpose: Prompt builder and response parser — bridges Claude to the Python pipeline without coupling them
- File: `scripts/claude_analyzer.py`
- Pattern: `build_analysis_prompt(symbol, df, strategy_name)` → string; `parse_response(text)` → `list[ClaudeRecommendation]`; never calls Claude itself

**StateStore:**
- Purpose: SQLite-backed persistence for all runtime state
- File: `scripts/state_store.py`
- Pattern: 4 tables (positions, orders, trade_log, day_trades); WAL journal mode; `reconcile_positions()` for crash recovery

## Entry Points

**`/trading-bot:initialize` command:**
- Location: `commands/initialize.md` → `skills/initialize/SKILL.md`
- Triggers: User runs `/trading-bot:initialize` or `/trading-bot:initialize --reset`
- Responsibilities: Interactive wizard collecting experience level, risk tolerance, budget, Alpaca mode (MCP vs SDK), strategies, autonomy mode, watchlist; writes `CLAUDE_PLUGIN_DATA/config.json` and `.env`

**`/trading-bot:build` command:**
- Location: `commands/build.md` → `skills/build/SKILL.md`
- Triggers: User runs `/trading-bot:build`
- Responsibilities: Reads config, calls `scripts/build_generator.py:generate_build()`, writes standalone bot directory to `CLAUDE_PLUGIN_DATA/trading-bot-standalone/` with rewritten imports

**`/trading-bot:run` command:**
- Location: `commands/run.md` → `skills/run/SKILL.md`
- Triggers: User runs `/trading-bot:run`
- Responsibilities: Mode selection (agent vs standalone); agent mode runs Claude analysis loop interactively; standalone mode executes `python bot.py` in the generated directory

**`scripts/bot.py` (standalone entry point):**
- Location: `scripts/bot.py`
- Triggers: `python -m scripts.bot` or `python scripts/bot.py` (standalone mode) or generated `bot.py`
- Responsibilities: Full initialization sequence (config → clients → StateStore → RiskManager → MarketScanner → APScheduler); runs until SIGINT/SIGTERM; graceful shutdown closes all positions

**`SessionStart` hook:**
- Location: `hooks/hooks.json` → `scripts/install-deps.sh`
- Triggers: Claude Code session start
- Responsibilities: Ensures `.venv` exists and all Python dependencies are installed before any command runs

## Error Handling

**Strategy:** Fail-safe — errors are caught, logged, and the pipeline continues for the next symbol/cycle. The bot never crashes on a single bad symbol.

**Patterns:**
- `scan_and_trade()` wraps each symbol in `try/except Exception` — errors logged via loguru, cycle continues
- `RiskManager.submit_with_retry()` retries with exponential backoff (1s/2s/4s/8s, max 5 attempts); skips retry on HTTP 422/403; checks for ghost positions before each retry
- `bot.py:main()` validates config and clients at startup, raising `FileNotFoundError` or `ValueError` with actionable messages before the scheduler starts
- `StateStore.reconcile_positions()` runs at startup to sync SQLite with actual Alpaca positions after any crash

## Cross-Cutting Concerns

**Logging:** loguru (`logger`) throughout all Python modules; `logger.info/warning/error/critical/debug` pattern; all debug output from shell hooks goes to stderr to keep stdout clean for JSON decisions

**Validation:** `ClaudeAnalyzer.parse_response()` validates all 7 required JSON fields, action whitelist (BUY/SELL/HOLD), confidence range, and applies threshold filter before any recommendation reaches the executor

**Authentication:** API keys loaded exclusively from environment variables (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) — never from config.json; `RiskManager` and clients created in `bot.py:create_clients()` after env check

**Alpaca MCP Mode:** When `use_mcp: true` in config, Claude Code MCP server (`alpaca-mcp-server`) is registered at project scope; Claude can use `mcp__alpaca__*` tools for read-only market queries during agent mode. Order execution always uses the Python SDK regardless of MCP setting.

**Audit Trail:** `AuditLogger` writes one NDJSON line per recommendation and one per execution outcome to `CLAUDE_PLUGIN_DATA/audit/claude_decisions.ndjson`; session_id ties entries to a single run

**Hook Safety Layer:** `hooks/validate-order.sh` (PreToolUse) intercepts Bash calls matching order submission patterns and enforces circuit breaker and PDT limits at the shell level as a secondary guardrail on top of the Python risk manager

---

*Architecture analysis: 2026-03-22*
