# Codebase Structure

**Analysis Date:** 2026-03-22

## Directory Layout

```
trading-bot/                        # Plugin root (CLAUDE_PLUGIN_ROOT)
├── .claude-plugin/
│   └── plugin.json                 # Plugin manifest (name, version, description)
├── commands/                       # Claude Code command stubs
│   ├── initialize.md               # /trading-bot:initialize — setup wizard
│   ├── build.md                    # /trading-bot:build — generate standalone bot
│   └── run.md                      # /trading-bot:run — start trading loop
├── agents/                         # Claude sub-agent persona definitions
│   ├── market-analyst.md           # Scans indicators, returns ClaudeRecommendation JSON (model: sonnet)
│   ├── risk-manager.md             # Validates signals against risk limits (model: haiku)
│   └── trade-executor.md           # Executes approved signals via OrderExecutor (model: haiku)
├── skills/                         # Step-by-step workflow instructions for commands
│   ├── initialize/SKILL.md         # Full setup wizard logic
│   ├── build/SKILL.md              # Build generator invocation and reporting
│   ├── run/SKILL.md                # Mode selection, agent loop, standalone launch
│   └── trading-rules/SKILL.md     # Core trading rules loaded during trading operations
├── hooks/                          # Claude Code lifecycle hooks
│   ├── hooks.json                  # Hook registration (SessionStart, PreToolUse, Stop)
│   ├── validate-order.sh           # PreToolUse: circuit breaker + PDT check on Bash order commands
│   └── check-session.sh            # Stop hook: session cleanup
├── scripts/                        # Python trading backend
│   ├── bot.py                      # Main entry point — APScheduler loop, graceful shutdown
│   ├── types.py                    # Signal and ClaudeRecommendation dataclasses
│   ├── market_scanner.py           # Alpaca bar fetching + pandas-ta indicator computation
│   ├── claude_analyzer.py          # Prompt builder and JSON response parser (no LLM calls)
│   ├── risk_manager.py             # Circuit breaker, PDT, position sizing, order retry
│   ├── order_executor.py           # Signal → Alpaca order (market/limit/bracket/trailing stop)
│   ├── state_store.py              # SQLite persistence (positions, orders, trade_log, day_trades)
│   ├── portfolio_tracker.py        # P&L calculation from trade history
│   ├── audit_logger.py             # NDJSON audit trail for Claude decisions
│   ├── eod_report.py               # End-of-day report generation
│   ├── notifier.py                 # Alert dispatch (large trades, circuit breaker, EOD)
│   ├── build_generator.py          # Generates standalone bot directory from config
│   ├── install-deps.sh             # SessionStart hook: venv + pip install
│   └── strategies/                 # Pluggable strategy implementations
│       ├── __init__.py             # STRATEGY_REGISTRY dict
│       ├── base.py                 # BaseStrategy ABC
│       ├── momentum.py             # RSI + MACD + EMA crossover strategy
│       ├── mean_reversion.py       # Bollinger Bands + RSI mean reversion
│       ├── breakout.py             # Resistance breakout + volume confirmation
│       └── vwap.py                 # VWAP intraday reversion strategy
├── references/                     # Developer reference documentation
│   ├── tech-stack.md               # Technology versions and compatibility notes
│   ├── trading-strategies.md       # Strategy logic, parameters, entry/exit conditions
│   ├── risk-rules.md               # Risk management rules and circuit breaker spec
│   └── alpaca-api-patterns.md      # Copy-paste alpaca-py code patterns
├── tests/                          # pytest test suite (co-located with project root)
│   ├── conftest.py                 # Shared fixtures (mock clients, sample DataFrames)
│   ├── test_bot.py                 # Integration tests for bot.py pipeline functions
│   ├── test_market_scanner.py      # Unit tests for MarketScanner
│   ├── test_risk_manager.py        # Unit tests for all 4 RiskManager checks
│   ├── test_order_executor.py      # Unit tests for all 4 order types + execute_signal
│   ├── test_state_store.py         # Unit tests for SQLite CRUD and reconciliation
│   ├── test_strategies.py          # Unit tests for all 4 strategy signal generators
│   ├── test_claude_analyzer.py     # Unit tests for prompt building and response parsing
│   ├── test_audit_logger.py        # Unit tests for NDJSON audit logging
│   ├── test_build_generator.py     # Unit tests for standalone build generation
│   ├── test_portfolio_tracker.py   # Unit tests for P&L calculations
│   ├── test_eod_report.py          # Unit tests for EOD report generation
│   ├── test_notifier.py            # Unit tests for alert dispatch
│   ├── test_agents.py              # Tests for agent persona content/structure
│   ├── test_config.py              # Tests for config validation logic
│   ├── test_hook.py                # Tests for validate-order.sh hook behavior
│   ├── test_plugin_manifest.py     # Tests for plugin.json structure
│   └── test_env_template.py        # Tests for .env template generation
├── .planning/                      # GSD planning documents (not committed to production)
│   ├── codebase/                   # Codebase map documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
│   ├── milestones/                 # Milestone definitions
│   └── phases/                     # Phase implementation plans
├── .claude/
│   └── settings.local.json         # Local Claude Code settings (not committed)
├── .plugin-data/                   # Runtime plugin data directory (gitignored)
│   └── venv/                       # Python venv created by install-deps.sh at session start
├── .venv/                          # Development venv (for local testing)
├── CLAUDE.md                       # Project instructions for Claude
├── requirements.txt                # Python dependencies
├── pytest.ini                      # pytest configuration
└── README.md                       # User-facing documentation
```

## Directory Purposes

**`commands/`:**
- Purpose: Claude Code slash-command entry points — thin stubs only
- Contains: One `.md` file per command with frontmatter (`name`, `description`, `allowed-tools`) and a single delegation line to the skill
- Key files: `initialize.md`, `build.md`, `run.md`
- Pattern: Commands never contain workflow logic. They load `${CLAUDE_PLUGIN_ROOT}/skills/{name}/SKILL.md`

**`agents/`:**
- Purpose: Sub-agent persona definitions invoked during agent-mode trading
- Contains: Markdown files with frontmatter (`model`, `color`, `tools`) defining each agent's role, constraints, and output format
- Key files: `market-analyst.md` (sonnet, indicator analysis), `risk-manager.md` (haiku, risk validation), `trade-executor.md` (haiku, order execution)

**`skills/`:**
- Purpose: Reusable workflow modules — the actual implementation behind commands
- Contains: `SKILL.md` files with step-by-step instructions, Bash snippets, mode-selection logic
- Key files: `run/SKILL.md` (most complex — handles agent/standalone split and MCP detection), `trading-rules/SKILL.md` (always loaded during trading to enforce invariants)

**`hooks/`:**
- Purpose: Claude Code lifecycle integration
- Contains: `hooks.json` (registration), shell scripts for each hook event
- Key files: `validate-order.sh` (PreToolUse circuit breaker + PDT enforcement as secondary guardrail), `check-session.sh` (Stop cleanup)

**`scripts/`:**
- Purpose: The complete Python trading backend — works standalone or when invoked by agent mode
- Contains: All core trading modules. Imports use `from scripts.X` convention (rewritten to `from X` by build generator for standalone deployment)
- Key files: `bot.py` (standalone orchestrator), `types.py` (shared dataclasses), `risk_manager.py` (all risk enforcement)

**`scripts/strategies/`:**
- Purpose: Pluggable strategy implementations — each is a standalone module inheriting `BaseStrategy`
- Contains: `STRATEGY_REGISTRY` dict, `BaseStrategy` ABC, 4 concrete strategies
- Adding a new strategy: create `scripts/strategies/{name}.py` implementing `generate_signal()`, register in `STRATEGY_REGISTRY` in `__init__.py`

**`references/`:**
- Purpose: Authoritative reference for strategy parameters, API patterns, and risk rules — consulted by skills and agents
- Contains: Markdown reference documents loaded by agents and skills at runtime
- Key files: `alpaca-api-patterns.md` (copy-paste SDK patterns), `risk-rules.md` (circuit breaker spec), `trading-strategies.md` (entry/exit conditions per strategy)

**`tests/`:**
- Purpose: pytest test suite — one test file per module in `scripts/`
- Contains: Unit tests and integration tests; `conftest.py` with shared mock fixtures
- Pattern: Module tests live in `tests/test_{module_name}.py`; all alpaca-py imports mocked

**`.plugin-data/`:**
- Purpose: Runtime data directory populated by the plugin (gitignored)
- Generated: Yes — created by `install-deps.sh` on first session start
- Committed: No
- Contains at runtime: `config.json`, `trading.db` (SQLite), `.env`, `circuit_breaker.flag` (when triggered), `pdt_trades.json` (legacy), `audit/claude_decisions.ndjson`, `trading-bot-standalone/` (after build)

## Key File Locations

**Entry Points:**
- `scripts/bot.py`: Standalone mode main — `if __name__ == "__main__": main()`
- `commands/run.md` → `skills/run/SKILL.md`: Agent mode entry
- `commands/initialize.md` → `skills/initialize/SKILL.md`: Setup wizard entry
- `commands/build.md` → `skills/build/SKILL.md`: Build generator entry

**Configuration:**
- `$CLAUDE_PLUGIN_DATA/config.json`: Runtime trading config (generated by `/initialize`)
- `$CLAUDE_PLUGIN_DATA/.env`: API keys (generated by `/initialize`, never committed)
- `.claude-plugin/plugin.json`: Plugin manifest
- `hooks/hooks.json`: Hook registration
- `pytest.ini`: Test configuration
- `requirements.txt`: Python dependencies

**Core Logic:**
- `scripts/types.py`: `Signal` and `ClaudeRecommendation` dataclasses — the pipeline contracts
- `scripts/risk_manager.py`: All 4 risk checks + retry logic — the safety substrate
- `scripts/order_executor.py`: `execute_signal()` — the only path to order submission
- `scripts/strategies/__init__.py`: `STRATEGY_REGISTRY` — how strategies are selected by name
- `scripts/build_generator.py`: `generate_build()` — standalone bot generation

**Testing:**
- `tests/conftest.py`: Shared fixtures (mock TradingClient, mock DataClient, sample indicator DataFrames)
- `tests/test_risk_manager.py`: Most safety-critical tests — covers all 4 checks and circuit breaker
- `tests/test_strategies.py`: Signal generation for all 4 strategies

## Naming Conventions

**Python Files:**
- `snake_case.py` for all modules: `market_scanner.py`, `risk_manager.py`, `state_store.py`
- Strategies follow pattern: `{strategy_name}.py` matching the registry key

**Classes:**
- `PascalCase`: `MarketScanner`, `RiskManager`, `OrderExecutor`, `StateStore`, `ClaudeAnalyzer`
- Strategies: `{StrategyName}Strategy` (e.g., `MomentumStrategy`, `BreakoutStrategy`)

**Command/Agent/Skill Files:**
- `kebab-case.md` for all Markdown plugin files: `market-analyst.md`, `validate-order.sh`
- Skill directories: `{command-name}/SKILL.md` (uppercase SKILL.md always)

**Tests:**
- `test_{module_name}.py` pattern, one file per module

**Environment Variables:**
- `CLAUDE_PLUGIN_ROOT`: Absolute path to plugin directory (set by Claude Code)
- `CLAUDE_PLUGIN_DATA`: Absolute path to runtime data directory (set by Claude Code)
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`: Alpaca credentials (loaded from `.env`)

## Where to Add New Code

**New Strategy:**
1. Create `scripts/strategies/{name}.py` inheriting `BaseStrategy`
2. Implement `generate_signal(df: pd.DataFrame, symbol: str, params: dict) -> Signal`
3. Register in `scripts/strategies/__init__.py`: add import and entry in `STRATEGY_REGISTRY`
4. Add test file: `tests/test_strategies.py` (extend existing file — all strategy tests are co-located)
5. Document parameters in `references/trading-strategies.md`

**New Python Module:**
- Implementation: `scripts/{module_name}.py`
- Test: `tests/test_{module_name}.py`
- Import convention: `from scripts.{module_name} import ClassName`

**New Command:**
- Command stub: `commands/{name}.md` with frontmatter and delegation line
- Skill: `skills/{name}/SKILL.md` with full workflow logic

**New Agent:**
- Agent definition: `agents/{role-name}.md` with `model:`, `color:`, `tools:` frontmatter
- Reference the agent in the relevant skill SKILL.md

**Utilities / Shared Helpers:**
- Shared type definitions: `scripts/types.py`
- Shared test fixtures: `tests/conftest.py`

## Special Directories

**`.plugin-data/venv/`:**
- Purpose: Python virtual environment used by hooks and command invocations in plugin mode
- Generated: Yes — by `scripts/install-deps.sh` on SessionStart
- Committed: No (gitignored)

**`.venv/`:**
- Purpose: Development virtual environment for local testing and IDE integration
- Generated: Yes — manually by developer
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD planning documents — milestones, phase plans, codebase maps
- Generated: By GSD commands
- Committed: Yes (planning artifacts tracked in git)

**`scripts/__pycache__/` and `tests/__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes
- Committed: No (gitignored)

---

*Structure analysis: 2026-03-22*
