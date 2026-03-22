## Project

**Trading Bot Plugin**

A Claude Code plugin that automates stock day trading on US markets. Interactive setup adapts to any user — from beginners to experts — then generates and runs autonomous trading infrastructure using the Alpaca API.

**Core Value:** After initial setup, the bot trades autonomously — scanning markets, making decisions (using Claude for analysis), and executing trades on a loop.

### Constraints

- **API**: Alpaca Markets API — free tier, paper trading support required
- **Language**: Python 3.12+ for trading scripts, standard Claude Code plugin structure
- **SDK**: alpaca-py 0.43.2 (not deprecated alpaca-trade-api)
- **Indicators**: pandas-ta 0.4.71b0 (pure Python, no C compiler needed)
- **Platform**: Linux, compatible with Claude Code plugin system
- **Autonomy**: Safe to run unattended — error handling, position limits, circuit breakers
- **Keys**: Never hardcode API keys — use pydantic-settings + .env

### Architecture

```
Market Data → MarketScanner → Technical Indicators → Claude Analysis
  → RiskManager (circuit breaker, PDT, position sizing) → OrderExecutor → Alpaca
```

**Key invariant:** Claude never submits orders directly. All recommendations route through deterministic Python risk checks.

**Two Alpaca modes** (chosen during `/trading-bot:initialize`):
- **MCP mode**: Alpaca MCP server added to project via `claude mcp add`, gives Claude 44 real-time API tools
- **SDK-only mode**: All API calls through Python alpaca-py SDK, no MCP server

### References

Detailed documentation in `references/`:
- `tech-stack.md` — Full technology stack, versions, alternatives, compatibility
- `trading-strategies.md` — Strategy logic, parameters, entry/exit conditions
- `risk-rules.md` — Risk management rules, circuit breaker, PDT, position sizing
- `alpaca-api-patterns.md` — Copy-paste Alpaca API code patterns

### Hooks — What Works in Plugin Format

Plugin hooks live in `hooks/hooks.json` with a `{"hooks": {...}}` wrapper. Key rules learned from testing:

- **Only `command` type hooks work reliably in plugins.** Prompt-based Stop hooks cause validation errors in plugin format — use a bash script instead.
- **No `matcher` on SessionStart.** Plugin format doesn't support matchers on SessionStart — the hook fires on all session events (startup, resume, clear, compact). The script must handle idempotency (install-deps.sh uses SHA256 hash comparison).
- **No `matcher` on Stop.** Stop hooks always fire — matcher field is ignored per the official schema.
- **No `description` field** at the top level of hooks.json — causes validation errors.
- **No `statusMessage` field** on individual hooks — unsupported in plugin format.
- **Exit code 0 + JSON stdout** is the correct pattern for PreToolUse decisions. Exit code 2 blocks the action. Don't mix both approaches in the same hook.
- **`${CLAUDE_PLUGIN_ROOT}`** for all script paths — never hardcode.
- **Plugin cache is what runs.** Local changes to hooks.json don't take effect until the plugin is reinstalled. The cache lives at `~/.claude/plugins/cache/`.

### Alpaca MCP Server — Configuration Notes

The MCP server is **opt-in** during `/trading-bot:initialize`. No `.mcp.json` ships with the plugin.

- **Install command**: `claude mcp add alpaca --scope project --transport stdio -- uvx alpaca-mcp-server serve`
- **Requires**: `uvx` (part of `uv`). The initialize wizard offers to install `uv` if missing.
- **Env vars**: Only `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are needed. Paper trading is the default — no env var required for it.
- **Two different paper-trade env vars exist**: The bot uses `ALPACA_PAPER` (pydantic-settings). The MCP server uses `ALPACA_PAPER_TRADE`. They are independent systems.
- **MCP client config overrides .env**: If keys are in the `.mcp.json` env section, those take precedence over any `.env` file the MCP server reads.
- **44 tools available**: Trading, market data, positions, watchlists, account info, options, crypto.
- **`.mcp.json` is gitignored**: Created per-project by `claude mcp add` during setup — not committed.

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
