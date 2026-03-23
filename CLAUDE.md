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
