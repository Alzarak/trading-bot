<!-- GSD:project-start source:PROJECT.md -->
## Project

**Trading Bot Plugin**

A Claude Code plugin that automates stock day trading on US markets. It provides an interactive setup command that adapts to any user — from complete beginners to expert traders — then generates and runs autonomous trading infrastructure using the Alpaca API. The plugin leverages the full Claude Code plugin system: agents, skills, commands, reference files, and hooks.

**Core Value:** After initial setup, the bot trades autonomously without human intervention — scanning markets, making decisions (using Claude for analysis), and executing trades on a loop.

### Constraints

- **API**: Alpaca Markets API — free tier, paper trading support required
- **Language**: Python for trading scripts, standard Claude Code plugin structure for the plugin itself
- **Platform**: Must work on Linux, compatible with Claude Code plugin system
- **Marketplace**: Must follow plugin marketplace conventions for publishing
- **Autonomy**: Must be safe to run unattended — proper error handling, position limits, circuit breakers
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| alpaca-py | 0.43.2 | Official Alpaca SDK — trading execution, market data, WebSocket streaming | The only actively maintained Alpaca Python SDK; alpaca-trade-api is deprecated since 2023. Provides TradingClient, StockDataStream, and StockHistoricalDataClient with pydantic validation built in. |
| Python | 3.12+ | Runtime for all trading scripts | alpaca-py requires Python >=3.8; pandas-ta 0.4.71b0 requires Python >=3.12. Pinning to 3.12 satisfies all library requirements and is stable LTS. |
| pandas-ta | 0.4.71b0 (beta) | Technical indicators (SMA, EMA, MACD, RSI, Bollinger Bands, 150+ more) | Pure Python, pip-installable without C compiler — critical for a plugin that users install. TA-Lib requires compiling a C library which breaks on many user machines. 60 candlestick patterns when TA-Lib is also present. |
| pandas | Latest stable (2.x) | OHLCV time-series manipulation, data frames | Industry standard for financial data; alpaca-py returns data that maps naturally to pandas DataFrames. |
| numpy | Latest stable (1.26+) | Numerical operations underlying all indicator math | Implicit dependency of pandas-ta; also used directly for position sizing math. |
| pydantic-settings | 2.x | Typed configuration management, .env file loading | alpaca-py itself uses pydantic v2 for validation. Using pydantic-settings for the bot config (API keys, strategy params) keeps types consistent and lets users supply config via .env or environment variables — both beginner and expert friendly. |
| APScheduler | 3.x | Trading loop scheduling, market-hours awareness | The standard Python async job scheduler for trading bots. Supports cron expressions (schedule by time-of-day), interval triggers (poll every N seconds), and timezone-aware scheduling — essential for "only trade 9:30am–4:00pm ET" logic. |
### Plugin System Components
| Component | Location | Purpose | Notes |
|-----------|----------|---------|-------|
| Commands (slash commands) | `commands/` | `/initialize`, `/build`, `/run` entry points | Simple `.md` files. Claude Code auto-discovers them. |
| Agents | `agents/` | Specialized subagents: market-analyst, risk-manager, trade-executor | Markdown with YAML frontmatter. `model: sonnet`, `effort: medium`. Cannot use hooks/mcpServers per plugin security policy. |
| Skills | `skills/` | Auto-invoked context: trading-context, risk-rules, strategy-reference | `SKILL.md` inside named subdirectory. Auto-loaded by Claude when conversation matches description. |
| Hooks | `hooks/hooks.json` | `SessionStart` to install Python deps into `${CLAUDE_PLUGIN_DATA}` | Use `diff` against bundled `requirements.txt` to detect dep changes across plugin versions. |
| MCP Server | `.mcp.json` | Alpaca MCP server — gives Claude real-time market data as tools | Bundled as a server config; runs `uvx alpaca-mcp-server` pointing at user's API keys. |
| Plugin Manifest | `.claude-plugin/plugin.json` | Declares name, version, author for marketplace distribution | Follows semver. Version bump required for marketplace cache invalidation. |
| Marketplace file | `.claude-plugin/marketplace.json` (in parent marketplace repo) | Lists this plugin for `claude plugin install` | Uses `source: github` pointing at this repo. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| alpaca-mcp-server | Latest (uvx) | Official Alpaca MCP server — 43 Alpaca API tools exposed to Claude as MCP tools | Always include. Lets Claude directly query account status, market data, positions during analysis. Python 3.10+ required for the MCP server process itself. |
| python-dotenv | 1.x | Load `.env` files | Use in standalone Python scripts (outside Claude Code context) where pydantic-settings isn't the entry point. |
| aiohttp / websockets | Latest stable | Underlying async transport for StockDataStream | Implicit via alpaca-py; no direct import needed. Mention in docs so users know asyncio is required for streaming. |
| pytz / zoneinfo | stdlib (3.9+) | US/Eastern timezone for market hours checks | Use stdlib `zoneinfo` module (Python 3.9+). No separate install needed. |
| loguru | 0.7+ | Structured logging for autonomous trading loop | Better than stdlib logging for long-running autonomous processes. Supports file rotation, colors, structured output. Critical for unattended operation — users need to review what the bot did. |
| rich | Latest stable | Pretty terminal output for `/initialize` interactive wizard | Makes the setup conversation legible. Tables for portfolio status, colored risk indicators. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Fast Python package management, venv creation | Used by Alpaca MCP server itself (`uvx alpaca-mcp-server`). Recommend for plugin install hooks too — faster than pip on user machines. |
| pyright (via pyright-lsp plugin) | Type checking for trading scripts | Claude Code has an official `pyright-lsp` plugin in the marketplace. Install alongside this plugin for real-time type errors in generated code. |
| claude plugin validate | Validate plugin manifest and hook JSON | Run before every release: `claude plugin validate .` checks `plugin.json`, skill frontmatter, `hooks/hooks.json`. |
## Installation
# Core trading dependencies (installed by plugin SessionStart hook into ${CLAUDE_PLUGIN_DATA})
# Alpaca MCP server (separate process, managed by .mcp.json)
# No pip install needed — uvx handles it on first run
# Dev: validate plugin structure
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| alpaca-py 0.43.2 | alpaca-trade-api 2.3.0 | Never. alpaca-trade-api is deprecated. Alpaca itself recommends migrating. |
| pandas-ta | TA-Lib | Only when raw performance matters more than install reliability. TA-Lib is 2-4x faster (C library) but requires compiling native code — a deal-breaker for a plugin that general users install. Expert traders running on a dedicated server can swap in TA-Lib; pandas-ta checks for it and uses it if present. |
| pandas-ta | finta | finta is simpler but fewer indicators (80) and less maintained. pandas-ta is the community standard for Python-native TA. |
| APScheduler | schedule (library) | `schedule` is simpler but lacks async support and timezone-awareness. Trading bots need both. Use `schedule` only for the simplest cron-style standalone scripts. |
| APScheduler | Celery + Redis | Overkill for a single-user trading bot. Celery is for distributed task queues. APScheduler runs in-process, zero infrastructure. |
| pydantic-settings | python-decouple | pydantic-settings provides typed validation, aligns with alpaca-py's own pydantic v2 usage, and supports multiple sources (env vars, .env files, secrets). decouple only does string values. |
| loguru | Python stdlib logging | stdlib logging works but requires more boilerplate to configure rotation and formatting. loguru is one import and sane defaults out of the box — matters for generated code that users will read. |
| uv | pip | pip works fine; uv is 10-100x faster for dependency resolution and is already required for the Alpaca MCP server. Consistency wins. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| alpaca-trade-api | Officially deprecated by Alpaca since 2023. No new features, security fixes only. Many tutorials reference it — they are outdated. | alpaca-py |
| alpaca-trade-api WebSocket | Same package, same deprecation. Also uses a different streaming API that doesn't match current Alpaca endpoints. | alpaca-py `StockDataStream` |
| yfinance for real-time data | Yahoo Finance rate-limits aggressively and terms of service prohibit commercial/trading use. Data quality is inconsistent. | Alpaca's own Market Data API (via alpaca-py and the MCP server) |
| Zipline / Zipline-Reloaded | Built for Quantopian-style backtesting workflows. Not designed for live trading and Alpaca integration requires community forks of unknown reliability. Out of scope (backtesting is v2). | Direct alpaca-py trading loop |
| Backtrader (live trading mode) | Backtrader's Alpaca store integration uses alpaca-trade-api (deprecated). The live trading path is broken against current Alpaca APIs. Fine for backtesting (v2), not for live execution. | Direct alpaca-py trading loop |
| Freqtrade / Jesse | Crypto-focused frameworks. Stock support is secondary or absent. The plugin needs US stock trading with Alpaca — these add complexity without gain. | alpaca-py directly |
| asyncio.sleep polling loop | A raw `while True: time.sleep(60)` loop does not respect market hours, has no error recovery, and cannot be paused/resumed cleanly. | APScheduler with cron triggers and market-hours guards |
| Hardcoded API keys in scripts | The `/build` command generates Python scripts. Generated code must read keys from environment variables or `.env`, never hardcode. pydantic-settings enforces this at config load time. | pydantic-settings + .env |
## Stack Patterns by Variant
- The MCP server (`.mcp.json`) gives Claude live access to Alpaca tools
- The trading loop runs as a background Python script spawned by the `/run` command
- Claude monitors output via hook on `Stop` or `PostToolUse` events
- Skills provide Claude with strategy context and risk rules on every turn
- The `/build` command generates `bot.py` + `requirements.txt` + `.env.template`
- APScheduler handles the loop with cron trigger (market hours)
- loguru writes to a rotating log file for later review
- No Claude Code runtime needed after generation
- `TradingClient('key', 'secret', paper=True)` — one flag difference from live
- `StockDataStream` connects to paper endpoint automatically when paper=True on trading client
- Alpaca paper accounts have $100,000 simulated starting capital
- All generated configs default to `ALPACA_PAPER=true` until user explicitly overrides
- Same code, `paper=False` (or `ALPACA_PAPER=false` in .env)
- Circuit breaker logic becomes non-optional — max daily loss, max position size enforced in code
- loguru audit log is required (what trades were placed and why)
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| alpaca-py 0.43.2 | Python 3.8–3.13, pydantic v2 | Uses pydantic v2 internally. Do not mix with pydantic v1. |
| pandas-ta 0.4.71b0 | Python >=3.12, pandas 2.x | The beta requirement for Python 3.12 is a hard floor. Older stable releases (0.3.x) work on Python 3.8+ but lack recent indicators. Use the beta; it is stable enough for production. |
| APScheduler 3.x | Python 3.8+, asyncio | APScheduler 4.x exists but is a near-complete API rewrite in alpha. Stick to 3.x — tutorials, docs, and examples are all 3.x. |
| alpaca-mcp-server | Python 3.10+ (its own process) | The MCP server runs in a separate subprocess. It does not affect the trading script's Python version. Ensure 3.10+ is available system-wide for `uvx`. |
| pydantic-settings 2.x | pydantic v2, Python 3.8+ | Requires pydantic v2. alpaca-py also requires pydantic v2. They are compatible. |
## Alpaca API: Key Client Classes Reference
# Paper trading
# Real-time price stream (WebSocket)
# Stream order status updates
# Historical OHLCV for indicator calculation
## Claude Code Plugin Directory Structure
## Sources
- [alpaca-py on PyPI](https://pypi.org/project/alpaca-py/) — version 0.43.2 confirmed, Python 3.8–3.13 support (HIGH confidence)
- [alpaca-py GitHub](https://github.com/alpacahq/alpaca-py) — official SDK, pydantic v2, OOP client design (HIGH confidence)
- [Alpaca MCP Server GitHub](https://github.com/alpacahq/alpaca-mcp-server) — official, Python 3.10+, uvx install, 43 API functions (HIGH confidence)
- [Alpaca MCP Server docs](https://docs.alpaca.markets/docs/alpaca-mcp-server) — Claude Code / Claude Desktop integration confirmed (HIGH confidence)
- [pandas-ta on PyPI](https://pypi.org/project/pandas-ta/) — version 0.4.71b0 (beta), Python >=3.12 required (HIGH confidence)
- [Claude Code plugins reference](https://code.claude.com/docs/en/plugins-reference) — full schema for commands, agents, skills, hooks, MCP servers (HIGH confidence)
- [Claude Code plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) — marketplace.json schema, GitHub hosting, distribution (HIGH confidence)
- [alpaca-trade-api deprecation — Alpaca forum](https://forum.alpaca.markets/t/backtrader-api-uses-deprecated-alpaca-trade-api-will-it-be-migrated-to-alpaca-py/16329) — deprecation confirmed (HIGH confidence)
- APScheduler 3.x docs — cron trigger, timezone support, trading bot suitability (MEDIUM confidence — verified via PyPI and community usage)
- pydantic-settings v2 pattern — type-safe .env loading, consistent with alpaca-py pydantic v2 (MEDIUM confidence — official pydantic docs)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
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
