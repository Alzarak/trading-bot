## Project

**Trading Bot**

An autonomous stock day trading bot for Claude Code. Installed via `npx @alzarak/trading-bot`, it copies commands, skills, agents, and scripts into `~/.claude/`. Interactive setup adapts to any user — from beginners to experts — then generates and runs autonomous trading infrastructure using the Alpaca API.

**Core Value:** After initial setup, the bot trades autonomously — scanning markets, making decisions (using Claude for analysis), and executing trades on a loop.

### Installation

```bash
npx @alzarak/trading-bot
```

The installer:
1. Asks for Alpaca API key + secret
2. Optionally configures the Alpaca MCP server (keys injected into `.mcp.json`)
3. Copies commands, skills, agents, scripts, hooks to `~/.claude/`
4. Writes project-level `.env`, `config.json`, and hooks in `.claude/settings.local.json`
5. Installs Python dependencies

### Constraints

- **API**: Alpaca Markets API — free tier, paper trading support required
- **Language**: Python 3.12+ for trading scripts
- **SDK**: alpaca-py 0.43.2 (not deprecated alpaca-trade-api)
- **Indicators**: pandas-ta 0.4.71b0 (pure Python, no C compiler needed)
- **Platform**: Linux
- **Autonomy**: Safe to run unattended — error handling, position limits, circuit breakers
- **Keys**: Never hardcode API keys — use pydantic-settings + .env

### Architecture

```
Market Data → MarketScanner → Technical Indicators → Claude Analysis
  → RiskManager (circuit breaker, PDT, position sizing) → OrderExecutor → Alpaca
```

**Key invariant:** Claude never submits orders directly. All recommendations route through deterministic Python risk checks.

**Two Alpaca modes** (chosen during `npx @alzarak/trading-bot` install):
- **MCP mode**: Alpaca MCP server configured in `.mcp.json` with API keys injected
- **SDK-only mode**: All API calls through Python alpaca-py SDK, no MCP server

### File Layout

```
~/.claude/
├── commands/trading-bot/       # /trading-bot:initialize, :build, :run
├── skills/trading-bot/         # initialize/, build/, run/, trading-rules/
├── agents/trading-bot-*.md     # market-analyst, risk-manager, trade-executor
└── trading-bot/                # scripts/, hooks/, references/, requirements.txt

<project>/
├── .claude/settings.local.json # hooks (project-level)
├── .mcp.json                   # Alpaca MCP config (if enabled)
└── trading-bot/
    ├── .env                    # API keys
    ├── config.json             # trading preferences
    ├── setup-context.md        # build handoff document
    └── venv/                   # Python virtualenv
```

### References

Detailed documentation in `~/.claude/trading-bot/references/`:
- `tech-stack.md` — Full technology stack, versions, alternatives, compatibility
- `trading-strategies.md` — Strategy logic, parameters, entry/exit conditions
- `risk-rules.md` — Risk management rules, circuit breaker, PDT, position sizing
- `alpaca-api-patterns.md` — Copy-paste Alpaca API code patterns

### Hooks

Hooks are installed into `.claude/settings.local.json` (project-level) by the npx installer. Scripts live at `~/.claude/trading-bot/hooks/`.

- **SessionStart** → `install-deps.sh` — installs Python deps if requirements.txt changed (SHA256 hash comparison)
- **PreToolUse (Bash)** → `validate-order.sh` — blocks orders if circuit breaker active or PDT limit reached
- **Stop** → `check-session.sh` — warns about open positions when stopping

### Alpaca MCP Server

The MCP server is **opt-in** during `npx @alzarak/trading-bot` install. API keys are injected directly into `.mcp.json`.

- **Requires**: `uvx` (part of `uv`). The installer offers to install `uv` if missing.
- **Two different paper-trade env vars exist**: The bot uses `ALPACA_PAPER` (pydantic-settings). The MCP server uses `ALPACA_PAPER_TRADE`. They are independent systems.
- **44 tools available**: Trading, market data, positions, watchlists, account info, options, crypto.
- **`.mcp.json` is gitignored**: Created per-project by the installer — not committed.

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Trading Bot Pipeline Rewrite**

A rewrite of the trading bot's signal generation and decision-making pipeline, replacing failed strategy classes (momentum, mean_reversion, breakout, vwap — 23/100 backtest, negative expectancy) with a skill-based architecture adapted from tradermonty/claude-trading-skills. The bot scans markets autonomously, detects macro regime, generates signals via multiple screeners, aggregates conviction scores, sizes positions, and executes trades through Alpaca — all on a 5-minute loop.

**Core Value:** The pipeline must gate entries by macro regime risk and aggregate multi-source signals with weighted conviction scoring — replacing the failed 2-of-N entry gate with a system that has positive expectancy.

### Constraints

- **API**: Alpaca Markets for execution + data; FMP for fundamental data (optional)
- **Language**: Python 3.12+, alpaca-py 0.43.2, pandas-ta 0.4.71b0
- **Architecture**: Claude never submits orders directly — all recommendations route through deterministic Python risk checks
- **Compatibility**: If config has `strategies` key but no `pipeline` key, fall back to current behavior
- **Data storage**: Thesis lifecycle in SQLite (not YAML files) for crash recovery and atomic writes
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12+ - All trading scripts, risk management, market scanning, order execution
- Bash - Hook scripts (`hooks/validate-order.sh`, `hooks/check-session.sh`, `scripts/install-deps.sh`)
- Markdown with YAML frontmatter - Agent definitions (`agents/*.md`), skill definitions (`skills/*/SKILL.md`), command definitions (`commands/*.md`)
## Runtime
- Python 3.12+ (hard requirement — enforced in `scripts/install-deps.sh` line 46)
- Timezone: America/New_York via stdlib `zoneinfo.ZoneInfo`
- uv (fast Python package management, used by `scripts/install-deps.sh`)
- pip compatible (fallback supported)
- Lockfile: Not present — `requirements.txt` pins exact versions for critical packages
## Frameworks
- alpaca-py 0.43.2 - Alpaca Markets SDK for trading execution, market data, account management
- pandas-ta 0.4.71b0 (beta) - Technical indicators (RSI, MACD, EMA, ATR, Bollinger Bands, VWAP)
- APScheduler 3.x (>=3.10,<4.0) - Trading loop scheduling at 60-second intervals, EOD cron at 16:05 ET
- pydantic-settings >=2.0 - Typed config management with `.env` loading via `BotConfig` class
- pytest (via `.pytest_cache/` and `pytest.ini`) — `pythonpath = .`, `testpaths = tests`
- uv - Virtualenv creation and dependency installation in `scripts/install-deps.sh`
## Key Dependencies
- `alpaca-py==0.43.2` - Trading SDK; exact pin required (incompatible with deprecated `alpaca-trade-api`)
- `pandas-ta==0.4.71b0` - Beta release but stable for production; requires Python >=3.12 and pandas 2.x
- `APScheduler>=3.10,<4.0` - APScheduler 4.x avoided (alpha, complete API rewrite)
- `pydantic-settings>=2.0` - Must be v2 (aligns with alpaca-py's pydantic v2 requirement)
- `pandas>=2.0` - OHLCV DataFrame manipulation, DatetimeIndex with timezone handling
- `numpy>=1.26` - Numerical operations for indicator computation
- `loguru>=0.7` - Structured logging with `logger.info()` / `logger.error()` throughout all modules
- `python-dotenv>=1.0` - `.env` loading for standalone scripts
- `rich>=13.0` - Terminal UI for interactive setup wizard (`/initialize` command)
## Configuration
- Variables loaded from `.env` file (never committed — in `.gitignore`)
- Critical vars: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER` (see INTEGRATIONS.md)
- Plugin runtime vars: `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` (set by Claude Code)
- `config.json` — generated by `/initialize` command, stored in `CLAUDE_PLUGIN_DATA`
- Contains: `paper_trading`, `budget_usd`, `max_position_pct`, `max_positions`, `max_daily_loss_pct`, `watchlist`, `strategies`, `strategy_params`, `notifications`, `autonomy_mode`
- `pytest.ini` — pytest configuration (pythonpath=., testpaths=tests)
- No `pyproject.toml` or `setup.py` — this is a plugin, not a distributed package
## Plugin Architecture
- Plugin manifest: `.claude-plugin/plugin.json` — name, version, description
- Commands: `commands/build.md`, `commands/initialize.md`, `commands/run.md`
- Skills: `skills/initialize/SKILL.md`, `skills/run/SKILL.md`, `skills/build/SKILL.md`, `skills/trading-rules/SKILL.md`
- Agents: `agents/market-analyst.md` (sonnet), `agents/risk-manager.md` (haiku), `agents/trade-executor.md` (haiku)
- Hooks: `hooks/hooks.json` wiring 3 lifecycle hooks
- `scripts/install-deps.sh` runs on `SessionStart` hook
- SHA256 hash of `requirements.txt` cached at `{CLAUDE_PLUGIN_DATA}/requirements.txt.sha256`
- Reinstalls only when `requirements.txt` changes
- Virtualenv stored at `{CLAUDE_PLUGIN_DATA}/venv`
## Platform Requirements
- Linux (primary target, per CLAUDE.md)
- Python 3.12+
- uv installed (via `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- jq, sqlite3, bash — required by hook scripts
- Claude Code with plugin support
- Same as development — single-user bot, not containerized
- Alpaca Markets account (paper or live)
- Persistent storage for `CLAUDE_PLUGIN_DATA` (SQLite database, audit logs, flag files)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` for all Python modules: `risk_manager.py`, `order_executor.py`, `state_store.py`
- `kebab-case.sh` for shell scripts: `validate-order.sh`, `check-session.sh`, `install-deps.sh`
- `snake_case` for test files, prefixed with `test_`: `test_risk_manager.py`, `test_order_executor.py`
- `PascalCase` for all classes: `RiskManager`, `OrderExecutor`, `MarketScanner`, `StateStore`, `AuditLogger`
- Strategy classes follow `{Name}Strategy` pattern: `MomentumStrategy`, `MeanReversionStrategy`, `BreakoutStrategy`, `VWAPStrategy`
- `snake_case` for all public methods: `calculate_position_size()`, `check_circuit_breaker()`, `submit_with_retry()`
- `_snake_case` prefix for private helpers: `_persist_circuit_breaker()`, `_load_pdt_trades()`, `_has_open_position()`, `_create_tables()`
- `snake_case` for all locals and instance vars: `start_equity`, `circuit_breaker_triggered`, `atr_multiplier`
- `UPPER_CASE` for module-level constants and registries: `STRATEGY_REGISTRY`, `_DEFAULTS`, `ET`
- Boolean flags use descriptive past-tense or state names: `circuit_breaker_triggered`, `_shutdown_requested`
- `dataclass` for shared contract types in `scripts/types.py`
- String literals for enum-like values: `Literal["BUY", "SELL", "HOLD"]`
- `str | Path` union syntax (Python 3.10+ style) throughout, not `Union[str, Path]`
- `float | None` preferred over `Optional[float]`
## Code Style
- No formatter config detected (no `pyproject.toml`, `ruff.toml`, `.prettierrc`). Style is enforced by convention.
- 4-space indentation throughout
- 88-character line length implied by line wrapping in practice
- Trailing commas in multi-line argument lists (e.g., `Signal(...)` in `types.py`)
- No ESLint/ruff config detected; `type: ignore[assignment]` comments used pragmatically for conditional imports
- `# pragma: no cover` marks unreachable branches in conditional imports
- Long methods are grouped with dashed comment separators:
## Import Organization
- No path aliases; all local imports use full `scripts.` prefix: `from scripts.types import Signal`, `from scripts.risk_manager import RiskManager`
- Test files add project root to `sys.path` explicitly when needed: `sys.path.insert(0, str(PROJECT_ROOT))`
## Error Handling
- Inner methods raise `RuntimeError` for unrecoverable states:
- Outer pipeline loops catch `Exception` broadly and continue:
- File I/O operations use targeted catches: `except (json.JSONDecodeError, OSError) as exc`
- HTTP status codes checked via `getattr(exc, "status_code", None)` — no custom exception types
- Non-retryable codes (422, 403) return `None` immediately from `submit_with_retry()`
- Return `None` (not raise) to signal blocked/failed operations from public methods
## Logging
- `logger.debug(...)` — non-actionable diagnostic detail (HOLD signals, prompt prep)
- `logger.info(...)` — normal operational events (orders submitted, session started, scans)
- `logger.warning(...)` — risk check blocks, parse failures, recoverable issues
- `logger.error(...)` — failed operations that skip a trade but continue the bot
- `logger.critical(...)` — circuit breaker triggers, flag file found on startup
- Always use loguru's `{}` placeholder style, never f-strings in logger calls:
- Messages are prefixed with the function name when context is ambiguous: `"scan_and_trade: error processing {}: {}"`
- Financial values formatted with `${:.2f}` or `{:.2f}%`
## Comments
## Function Design
- `config: dict` passed through the pipeline (not a global)
- Optional parameters default to `None`, not mutable defaults
- `side: "OrderSide | None" = None` with explicit `if side is None: side = OrderSide.BUY` inside body
- Public methods return `None` on failure, never raise for expected failures
- Boolean return for guard checks: `check_circuit_breaker() -> bool`, `check_position_count() -> bool`
- String return for multi-outcome checks: `check_pdt_limit() -> str` returning `"allow"`, `"warn"`, or `"block"`
- `-> object | None` for Alpaca order types (avoids importing at module level)
## Module Design
- No `__all__` used; all public names are simply not prefixed with `_`
- Strategy modules export a `STRATEGY_REGISTRY` dict at `scripts/strategies/__init__.py`
## Bash Script Conventions
#!/bin/bash          # or #!/usr/bin/env bash
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Claude Code plugin shell (`commands/`, `agents/`, `skills/`, `hooks/`) wraps a pure-Python trading backend (`scripts/`)
- The trading pipeline is unidirectional: data flows MarketScanner → Strategy/ClaudeAnalyzer → RiskManager → OrderExecutor → Alpaca — no layer calls back up the chain
- Claude is an analyst only, never an executor: `ClaudeAnalyzer` builds prompts and parses responses but never calls the Alpaca API directly
- Two orthogonal mode axes: **Alpaca access mode** (MCP vs SDK-only) × **run mode** (agent vs standalone)
## Layers
- Purpose: Exposes three user-facing commands and wires Claude Code hooks
- Location: `commands/`, `agents/`, `skills/`, `hooks/`
- Contains: Command stubs that delegate to skill files, agent persona definitions, hook scripts
- Depends on: Skills (loaded at runtime), Python backend (invoked via Bash)
- Used by: Claude Code plugin system
- Purpose: Procedural step-by-step instructions Claude follows to implement each command
- Location: `skills/initialize/SKILL.md`, `skills/run/SKILL.md`, `skills/build/SKILL.md`, `skills/trading-rules/SKILL.md`
- Contains: Markdown instructions with embedded Bash, mode-selection logic, safety rules
- Depends on: Python backend scripts, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` env vars
- Used by: Commands (via stub delegation)
- Purpose: Core autonomous trading logic — data fetching, signal generation, risk enforcement, order execution
- Location: `scripts/`
- Contains: All Python modules — see Key Abstractions below
- Depends on: Alpaca API (via alpaca-py SDK), SQLite, pandas-ta indicators
- Used by: Agent mode (via inline Python invocations), standalone mode (direct execution)
- Purpose: Pluggable signal generators — each reads indicator DataFrames and returns a Signal
- Location: `scripts/strategies/`
- Contains: `BaseStrategy` ABC, four concrete implementations, `STRATEGY_REGISTRY` dict
- Depends on: `scripts/types.Signal`, pandas DataFrames from MarketScanner
- Used by: `bot.py:scan_and_trade()` (standalone mode), directly in agent mode
- Purpose: Crash-safe state across restarts
- Location: `scripts/state_store.py` (SQLite), `scripts/audit_logger.py` (NDJSON)
- Contains: Positions table, orders table, trade log table, day_trades table; audit/claude_decisions.ndjson
- Depends on: SQLite3 (stdlib), `CLAUDE_PLUGIN_DATA` env var for path resolution
- Used by: RiskManager (PDT count), OrderExecutor (position upsert), PortfolioTracker, AuditLogger
## Data Flow
- `StateStore` (SQLite WAL mode) is the single source of truth for open positions, PDT count, trade history
- `RiskManager` holds in-memory `circuit_breaker_triggered` flag (reset only on process restart after flag file deletion)
- `PortfolioTracker` computes P&L from SQLite trade log; never holds in-memory trade state
## Key Abstractions
- Purpose: Typed contract between strategies/ClaudeAnalyzer and OrderExecutor
- File: `scripts/types.py`
- Pattern: `@dataclass` with fields `action` (BUY/SELL/HOLD), `confidence`, `symbol`, `strategy`, `atr`, `stop_price`, `reasoning`
- Purpose: Structured output from Claude analysis; converts to Signal via `to_signal()`
- File: `scripts/types.py`
- Pattern: Same shape as Signal but originates from parsed Claude JSON; `to_signal()` is the bridge
- Purpose: ABC enforcing the `generate_signal(df, symbol, params) → Signal` contract
- File: `scripts/strategies/base.py`
- Pattern: Inherit and implement `generate_signal()`. Register name in `STRATEGY_REGISTRY` in `scripts/strategies/__init__.py`
- Purpose: Config-name → class mapping for dynamic strategy loading
- File: `scripts/strategies/__init__.py`
- Pattern: `{"momentum": MomentumStrategy, "mean_reversion": MeanReversionStrategy, "breakout": BreakoutStrategy, "vwap": VWAPStrategy}` — `bot.py` indexes by `strategy_config["name"]`
- Purpose: Prompt builder and response parser — bridges Claude to the Python pipeline without coupling them
- File: `scripts/claude_analyzer.py`
- Pattern: `build_analysis_prompt(symbol, df, strategy_name)` → string; `parse_response(text)` → `list[ClaudeRecommendation]`; never calls Claude itself
- Purpose: SQLite-backed persistence for all runtime state
- File: `scripts/state_store.py`
- Pattern: 4 tables (positions, orders, trade_log, day_trades); WAL journal mode; `reconcile_positions()` for crash recovery
## Entry Points
- Location: `commands/initialize.md` → `skills/initialize/SKILL.md`
- Triggers: User runs `/trading-bot:initialize` or `/trading-bot:initialize --reset`
- Responsibilities: Interactive wizard collecting experience level, risk tolerance, budget, Alpaca mode (MCP vs SDK), strategies, autonomy mode, watchlist; writes `CLAUDE_PLUGIN_DATA/config.json` and `.env`
- Location: `commands/build.md` → `skills/build/SKILL.md`
- Triggers: User runs `/trading-bot:build`
- Responsibilities: Reads config, calls `scripts/build_generator.py:generate_build()`, writes standalone bot directory to `CLAUDE_PLUGIN_DATA/trading-bot-standalone/` with rewritten imports
- Location: `commands/run.md` → `skills/run/SKILL.md`
- Triggers: User runs `/trading-bot:run`
- Responsibilities: Mode selection (agent vs standalone); agent mode runs Claude analysis loop interactively; standalone mode executes `python bot.py` in the generated directory
- Location: `scripts/bot.py`
- Triggers: `python -m scripts.bot` or `python scripts/bot.py` (standalone mode) or generated `bot.py`
- Responsibilities: Full initialization sequence (config → clients → StateStore → RiskManager → MarketScanner → APScheduler); runs until SIGINT/SIGTERM; graceful shutdown closes all positions
- Location: `hooks/hooks.json` → `scripts/install-deps.sh`
- Triggers: Claude Code session start
- Responsibilities: Ensures `.venv` exists and all Python dependencies are installed before any command runs
## Error Handling
- `scan_and_trade()` wraps each symbol in `try/except Exception` — errors logged via loguru, cycle continues
- `RiskManager.submit_with_retry()` retries with exponential backoff (1s/2s/4s/8s, max 5 attempts); skips retry on HTTP 422/403; checks for ghost positions before each retry
- `bot.py:main()` validates config and clients at startup, raising `FileNotFoundError` or `ValueError` with actionable messages before the scheduler starts
- `StateStore.reconcile_positions()` runs at startup to sync SQLite with actual Alpaca positions after any crash
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
