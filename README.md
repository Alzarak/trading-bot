# Trading Bot

A Claude Code plugin that automates stock day trading on US markets via the Alpaca API. After an interactive setup, it trades autonomously — scanning markets, analyzing signals with Claude, and executing trades on a loop.

## Features

- **Interactive setup wizard** — `/initialize` adapts to your experience level and risk tolerance
- **4 pluggable strategies** — Momentum (RSI+MACD+EMA), Mean Reversion (Bollinger+RSI), Breakout (resistance+volume), VWAP intraday
- **Built-in risk management** — Circuit breaker, PDT compliance, position limits, mandatory stop-losses
- **Paper & live trading** — Defaults to paper ($100K simulated); one config change for live
- **Two deployment modes** — Run inside Claude Code with AI analysis, or `/build` a standalone bot for any server
- **Full audit trail** — Every signal, risk decision, and order is logged

## Requirements

- [Claude Code](https://claude.ai/code) with plugin support
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (for dependency management and the Alpaca MCP server)
- [Alpaca](https://alpaca.markets/) account (free tier works for paper trading)

## Installation

### From a marketplace

First, add the marketplace that hosts this plugin:

```
/plugin marketplace add <owner>/<repo>
```

Then install the plugin:

```
/plugin install trading-bot@<marketplace-name>
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
├── commands/                    # /initialize, /build, /run
├── agents/                      # market-analyst, risk-manager, trade-executor
├── skills/trading-rules/        # Auto-loaded trading context
├── hooks/                       # SessionStart (deps), PreToolUse (order validation)
├── scripts/                     # Python trading modules
│   ├── bot.py                   # Main entry point (APScheduler loop)
│   ├── market_scanner.py        # OHLCV + indicator computation
│   ├── order_executor.py        # Alpaca order routing
│   ├── risk_manager.py          # Circuit breaker, PDT, position sizing
│   ├── claude_analyzer.py       # Claude recommendation parsing
│   ├── state_store.py           # SQLite persistence
│   └── strategies/              # momentum, mean_reversion, breakout, vwap
├── references/                  # Strategy docs, risk rules, API patterns
└── requirements.txt
```

## Configuration

After `/initialize`, your config is stored as JSON with these key settings:

| Setting | Description | Default |
|---------|-------------|---------|
| `experience_level` | beginner / intermediate / expert | — |
| `risk_tolerance` | conservative / moderate / aggressive | — |
| `paper` | Paper trading mode | `true` |
| `strategy` | Active strategy | `momentum` |
| `max_position_pct` | Max equity per position (5%/10%/15% by risk) | varies |
| `max_positions` | Max concurrent positions | `10` |
| `max_daily_loss_pct` | Circuit breaker threshold | varies |
| `watchlist` | Symbols to scan | `AAPL, MSFT, GOOGL, NVDA, TSLA` |

API keys are read from environment variables or `.env`:

```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true
```

## Safety

- **Circuit breaker** halts all trading when daily loss exceeds the configured threshold
- **PDT guard** blocks trades if 3+ day trades occur in a rolling 5-business-day window (accounts under $25K)
- **PreToolUse hook** validates every order submission before it reaches Alpaca
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

## License

MIT
