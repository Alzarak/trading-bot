# Technology Stack Reference

## Core Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| alpaca-py | 0.43.2 | Official Alpaca SDK — trading execution, market data, WebSocket streaming |
| Python | 3.12+ | Runtime for all trading scripts |
| pandas-ta | 0.4.71b0 (beta) | Technical indicators (SMA, EMA, MACD, RSI, Bollinger Bands, 150+) |
| pandas | 2.x | OHLCV time-series manipulation |
| numpy | 1.26+ | Numerical operations |
| pydantic-settings | 2.x | Typed configuration management, .env loading |
| APScheduler | 3.x | Trading loop scheduling, market-hours awareness |
| loguru | 0.7+ | Structured logging with rotation |
| rich | 13.0+ | Terminal UI for interactive setup |

## Plugin Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Skills | `skills/` | `/initialize`, `/build`, `/run` entry points + auto-loaded trading-rules |
| Agents | `agents/` | market-analyst (sonnet), risk-manager (haiku), trade-executor (haiku) |
| Hooks | `hooks/hooks.json` | SessionStart deps install, PreToolUse order gating, Stop session verification |
| MCP Server | opt-in via `/initialize` | Alpaca MCP server (44 tools) — added to project via `claude mcp add` if user opts in |

## Supporting Libraries

| Library | Purpose |
|---------|---------|
| alpaca-mcp-server (uvx) | Official Alpaca MCP server — gives Claude real-time market data tools |
| python-dotenv 1.x | Load .env in standalone scripts |
| loguru 0.7+ | Structured logging for autonomous operation |
| uv | Fast Python package management (used by MCP server) |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| alpaca-py 0.43.2 | Python 3.8-3.13, pydantic v2 | Do not mix with pydantic v1 |
| pandas-ta 0.4.71b0 | Python >=3.12, pandas 2.x | Beta but stable for production |
| APScheduler 3.x | Python 3.8+, asyncio | Avoid 4.x (alpha, API rewrite) |
| alpaca-mcp-server | Python 3.10+ (separate process) | Does not affect trading script Python version |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| alpaca-trade-api | Deprecated since 2023 | alpaca-py |
| yfinance for real-time data | Rate limits, TOS prohibits trading use | Alpaca Market Data API |
| Zipline / Backtrader live mode | Broken Alpaca integration, uses deprecated SDK | Direct alpaca-py trading loop |
| asyncio.sleep polling loop | No market hours, no error recovery | APScheduler with cron triggers |
| Hardcoded API keys | Security risk | pydantic-settings + .env |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| pandas-ta | TA-Lib | Only when raw performance > install reliability (requires C compiler) |
| APScheduler | schedule | Only for simplest cron-style scripts (no async, no timezone) |
| APScheduler | Celery + Redis | Overkill for single-user bot |
| pydantic-settings | python-decouple | pydantic-settings provides typed validation, aligns with alpaca-py |
| uv | pip | pip works; uv is 10-100x faster |

## Sources

- [alpaca-py on PyPI](https://pypi.org/project/alpaca-py/) — v0.43.2, Python 3.8-3.13
- [Alpaca MCP Server](https://github.com/alpacahq/alpaca-mcp-server) — Python 3.10+, uvx install
- [pandas-ta on PyPI](https://pypi.org/project/pandas-ta/) — v0.4.71b0, Python >=3.12
- [Claude Code plugins reference](https://code.claude.com/docs/en/plugins-reference)
