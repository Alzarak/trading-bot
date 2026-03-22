# Trading Bot

A Claude Code plugin that automates stock day trading on US markets via the Alpaca API. After an interactive setup, it trades autonomously — scanning markets, analyzing signals with Claude, and executing trades on a loop.

## Features

- **Interactive setup wizard** — `/initialize` adapts to your experience level and risk tolerance
- **4 pluggable strategies** — Momentum (RSI+MACD+EMA), Mean Reversion (Bollinger+RSI), Breakout (resistance+volume), VWAP intraday
- **Built-in risk management** — Circuit breaker, PDT compliance, position limits, mandatory stop-losses
- **Paper & live trading** — Defaults to paper ($100K simulated); one config change for live
- **Two deployment modes** — Run inside Claude Code with AI analysis, or `/build` a standalone bot for any server
- **Full audit trail** — Every signal, risk decision, and order is logged
- **Optional Alpaca MCP integration** — 44 Alpaca API tools available to Claude for real-time market data (opt-in during setup)

## Requirements

- [Claude Code](https://claude.ai/code) with plugin support
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (for dependency management; also required if enabling MCP server)
- [Alpaca](https://alpaca.markets/) account (free tier works for paper trading)

## Installation

### From a marketplace

First, add the marketplace that hosts this plugin:

```
/plugin marketplace add Alzarak/claude-marketplace
```

Then install the plugin:

```
/plugin install trading-bot@Alzarak-claude-marketplace
```

### From a local directory (development)

```bash
claude --plugin-dir ./trading-bot
```

Dependencies install automatically on first load via the `SessionStart` hook. Run `/reload-plugins` after installation to activate.

## Quick Start

```
/initialize    # Set up API keys, strategy, risk tolerance
/build         # Generate standalone bot scripts (optional)
/run           # Start the trading loop
```

### 1. Initialize

The setup wizard asks about your experience level, risk tolerance, budget, strategy preference, and watchlist. Config is saved to `config.json` in the plugin data directory.

### 2. Build (optional)

Generates a self-contained `trading-bot-standalone/` directory with `bot.py`, `requirements.txt`, `.env.template`, and your selected strategies. Deployable to any server — no Claude Code needed at runtime.

### 3. Run

Starts the trading loop in one of two modes:

- **Agent mode** — Claude analyzes indicator DataFrames and returns structured recommendations, which pass through the Python risk manager before execution
- **Standalone mode** — Runs the pre-built `bot.py` directly with APScheduler

## Architecture

```
Market Data (Alpaca) → MarketScanner → Technical Indicators (pandas-ta)
                                            ↓
                        Strategy Evaluation / Claude Analysis
                                            ↓
                              RiskManager (deterministic Python)
                              - Circuit breaker
                              - PDT guard (< 3 day trades / 5 days)
                              - Position limits & sizing
                                            ↓
                              OrderExecutor → Alpaca API
                                            ↓
                              AuditLogger + PortfolioTracker
```

Claude acts as a **strategy-level analyst only** — all recommendations pass through deterministic Python risk checks before any order is placed.

## Plugin Structure

```
trading-bot/
├── .claude-plugin/plugin.json   # Plugin manifest
├── commands/                    # /initialize, /build, /run (slash command stubs)
├── agents/                      # market-analyst, risk-manager, trade-executor
│   ├── market-analyst.md        # Sonnet — technical indicator analysis
│   ├── risk-manager.md          # Haiku — deterministic risk validation
│   └── trade-executor.md        # Haiku — order routing and audit logging
├── skills/                      # Auto-loaded context and workflows
│   ├── initialize/SKILL.md      # Setup wizard workflow
│   ├── build/SKILL.md           # Standalone bot generation workflow
│   ├── run/SKILL.md             # Trading loop workflow
│   └── trading-rules/SKILL.md   # Core trading rules (auto-loaded)
├── hooks/                       # Event-driven automation
│   ├── hooks.json               # SessionStart + PreToolUse + Stop hooks
│   └── validate-order.sh        # Order validation (circuit breaker + PDT)
├── scripts/                     # Python trading modules
│   ├── bot.py                   # Main entry point (APScheduler loop)
│   ├── market_scanner.py        # OHLCV + indicator computation
│   ├── order_executor.py        # Alpaca order routing
│   ├── risk_manager.py          # Circuit breaker, PDT, position sizing
│   ├── claude_analyzer.py       # Claude recommendation parsing
│   ├── state_store.py           # SQLite persistence
│   └── strategies/              # momentum, mean_reversion, breakout, vwap
├── references/                  # Detailed documentation
│   ├── tech-stack.md            # Technology stack, versions, alternatives
│   ├── trading-strategies.md    # Strategy logic, parameters, entry/exit
│   ├── risk-rules.md            # Risk rules, circuit breaker, PDT
│   └── alpaca-api-patterns.md   # Copy-paste Alpaca API code
└── requirements.txt
```

## Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **market-analyst** | Sonnet | Analyzes technical indicators, generates BUY/SELL/HOLD signals with confidence scores |
| **risk-manager** | Haiku | Validates trades against circuit breaker, PDT limits, position sizing constraints |
| **trade-executor** | Haiku | Executes approved signals through OrderExecutor, logs results for audit trail |

## Hooks

| Event | Type | Purpose |
|-------|------|---------|
| **SessionStart** | Command | Installs Python dependencies into plugin venv |
| **PreToolUse** (Bash) | Command | Gates order submissions — checks circuit breaker and PDT count |
| **Stop** | Command | Checks for open positions and circuit breaker status before ending a session |

## Configuration

After `/initialize`, your config is stored as JSON with these key settings:

| Setting | Description | Default |
|---------|-------------|---------|
| `experience_level` | beginner / intermediate / expert | — |
| `risk_tolerance` | conservative / moderate / aggressive | — |
| `paper_trading` | Paper trading mode | `true` |
| `strategies` | Active strategies with weights and params | `[momentum]` |
| `max_position_pct` | Max equity per position (5%/10%/15% by risk) | varies |
| `max_positions` | Max concurrent positions | `10` |
| `max_daily_loss_pct` | Circuit breaker threshold | varies |
| `watchlist` | Symbols to scan | `AAPL, MSFT, GOOGL, AMZN, SPY` |
| `use_mcp` | Enable Alpaca MCP server (44 real-time tools) | `false` |

API keys are read from environment variables or `.env`:

```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
```

### Alpaca MCP Server (Optional)

During `/initialize`, you can opt into the Alpaca MCP server. If enabled, it's added to your project via `claude mcp add alpaca` and gives Claude direct access to 44 Alpaca API tools (quotes, positions, account info). Paper trading is the default. If you skip MCP, all API calls go through the Python alpaca-py SDK.

## Safety

- **Circuit breaker** halts all trading when daily loss exceeds the configured threshold
- **PDT guard** blocks trades if 3+ day trades occur in a rolling 5-business-day window (accounts under $25K)
- **PreToolUse hook** validates every order submission before it reaches Alpaca
- **Stop hook** verifies all positions have stop-losses before ending a session
- **Mandatory stop-losses** on all positions (ATR-based, minimum 0.5%)
- **No averaging down** — the bot will not add to losing positions
- **Graceful shutdown** closes positions on SIGINT/SIGTERM

## Tech Stack

| Package | Purpose |
|---------|---------|
| [alpaca-py](https://github.com/alpacahq/alpaca-py) 0.43.2 | Trading execution & market data |
| [pandas-ta](https://github.com/twopirllc/pandas-ta) 0.4.71b0 | 150+ technical indicators |
| [APScheduler](https://github.com/agronholm/apscheduler) 3.x | Market-hours-aware scheduling |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) 2.x | Typed config with .env support |
| [loguru](https://github.com/Delgan/loguru) | Structured logging with rotation |
| [rich](https://github.com/Textualize/rich) | Terminal UI for setup wizard |

See `references/tech-stack.md` for the full stack reference including version compatibility, alternatives considered, and what not to use.

## License

MIT
