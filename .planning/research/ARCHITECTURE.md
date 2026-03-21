# Architecture Research

**Domain:** Automated stock day trading Claude Code plugin
**Researched:** 2026-03-21
**Confidence:** HIGH (Claude Code plugin system via official docs; MEDIUM for trading bot patterns via multiple verified sources)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Claude Code Plugin Layer                         │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  /initialize │  │    /build    │  │          /run            │   │
│  │   command    │  │   command    │  │        command           │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘   │
│         │                 │                        │                 │
│  ┌──────▼──────────────────▼────────────────────────▼─────────────┐  │
│  │                    Plugin Agents                                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │  │
│  │  │  setup-    │  │  market-   │  │  trade-    │  │  risk-   │  │  │
│  │  │  wizard    │  │  analyst   │  │  executor  │  │  manager │  │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    Plugin Skills / Hooks                         │  │
│  │  trading-rules (auto-injected)   PreToolUse: trade-safety-check │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    MCP Server Layer (.mcp.json)                  │  │
│  │              Alpaca MCP Server (real-time market data,           │  │
│  │                    account, orders, positions)                   │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   Generated Python Runtime Layer                     │
│                     (produced by /build command)                     │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  Market      │    │  Signal      │    │  Risk Manager        │   │
│  │  Scanner     │───▶│  Generator   │───▶│  (pre-trade checks)  │   │
│  │              │    │  + Claude AI │    │                      │   │
│  └──────────────┘    └──────────────┘    └──────────┬───────────┘   │
│                                                      │               │
│  ┌──────────────┐    ┌──────────────┐               │               │
│  │  Portfolio   │◀───│  Order       │◀──────────────┘               │
│  │  Tracker     │    │  Executor    │                                │
│  └──────────────┘    └──────────────┘                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    State / Persistence Layer                     │  │
│  │       SQLite (trades, positions, P&L)   JSON (session state)    │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                      External APIs                               │  │
│  │   Alpaca REST (orders, account)    Alpaca WebSocket (live bars) │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| `/initialize` command | Interactive preference elicitation; writes `config.json` | User, setup-wizard agent |
| `/build` command | Reads `config.json`, generates Python scripts + cron/scheduler | config.json, plugin data dir |
| `/run` command | Launches the autonomous trading loop | Generated Python runtime |
| `setup-wizard` agent | Adapts questions to skill level (beginner vs expert); validates budget/risk inputs | /initialize command |
| `market-analyst` agent | Claude analysis sessions for in-Claude-Code mode; reads Alpaca MCP data | Alpaca MCP, /run command |
| `trade-executor` agent | Wraps order submission logic within Claude's tool calls | Alpaca MCP, risk-manager agent |
| `risk-manager` agent | Pre-trade validation, position sizing, circuit-breaker decisions | All agents |
| `trading-rules` skill | Auto-injected context: regulatory constraints, risk rules, strategy docs | All agents |
| `trade-safety-check` hook (PreToolUse) | Intercepts any order-submission tool call, validates limits before execution | Alpaca MCP tools |
| Alpaca MCP Server | Exposes Alpaca account, positions, orders, market data as Claude tools | All agents, /run command |
| Market Scanner | Polls Alpaca REST/WebSocket for bars, screens watchlist symbols | Alpaca API, Signal Generator |
| Signal Generator | Applies technical indicators (RSI, MACD, EMA); optionally calls Claude API for analysis | Market Scanner, Risk Manager |
| Risk Manager (Python) | Position sizing, max-loss checks, drawdown circuit breaker | Signal Generator, Order Executor |
| Order Executor | Constructs and submits `MarketOrderRequest`/`LimitOrderRequest` to Alpaca | Alpaca REST API, Portfolio Tracker |
| Portfolio Tracker | Records fills, updates P&L, writes trade history to SQLite | Order Executor, SQLite |
| State / SQLite | Persists trades, open positions, daily P&L, session state | All Python components |

## Recommended Project Structure

```
trading-bot-plugin/              # Plugin root
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest (name, version, description)
├── commands/
│   ├── initialize.md            # /initialize slash command
│   ├── build.md                 # /build slash command
│   └── run.md                   # /run slash command
├── agents/
│   ├── setup-wizard.md          # Preference elicitation agent
│   ├── market-analyst.md        # Market analysis + Claude decision agent
│   ├── trade-executor.md        # Order submission agent
│   └── risk-manager.md          # Pre-trade validation agent
├── skills/
│   └── trading-rules/
│       ├── SKILL.md             # Auto-invoked: injects trading rules into context
│       └── reference/
│           ├── risk-limits.md   # Max position size, daily loss limits
│           └── strategies.md    # Strategy documentation (RSI, MACD, etc.)
├── hooks/
│   └── hooks.json               # PreToolUse: trade-safety-check
├── scripts/
│   └── trade-safety-check.sh    # Hook script validating order parameters
├── .mcp.json                    # Alpaca MCP server configuration
├── templates/                   # Python script templates (filled by /build)
│   ├── scanner.py.j2
│   ├── signal_generator.py.j2
│   ├── risk_manager.py.j2
│   ├── order_executor.py.j2
│   ├── portfolio_tracker.py.j2
│   ├── main_loop.py.j2
│   └── config_loader.py.j2
├── settings.json                # Plugin default settings
└── README.md                    # User-facing documentation

# Generated output (written by /build into user's working dir or CLAUDE_PLUGIN_DATA)
trading-bot-generated/
├── config.json                  # User preferences from /initialize
├── scanner.py                   # Market scanner
├── signal_generator.py          # Technical analysis + Claude AI calls
├── risk_manager.py              # Position sizing, circuit breakers
├── order_executor.py            # Alpaca order submission
├── portfolio_tracker.py         # Trade history, P&L
├── main_loop.py                 # Autonomous orchestration loop
├── config_loader.py             # Loads config.json, injects env vars
├── state/
│   ├── trading.db               # SQLite: trades, positions, P&L
│   └── session.json             # Current loop state (last scan time, etc.)
└── logs/
    ├── trades.log               # Executed trades with reasoning
    └── errors.log               # Exceptions, circuit-breaker events
```

### Structure Rationale

- **commands/:** Each phase of the user journey is a distinct slash command — /initialize gathers, /build generates, /run executes. Separation prevents accidental re-initialization.
- **agents/:** Separate agents per concern allows Claude to invoke the right specialist. `market-analyst` focuses on analysis; `trade-executor` focuses on safe order submission.
- **skills/trading-rules/:** Auto-injected into every agent session. Ensures risk rules are always in context without requiring the user or other agents to remember to load them.
- **hooks/:** `PreToolUse` hook acts as a hard safety gate before any Alpaca tool call. Catches runaway agents before real orders are placed.
- **templates/:** Jinja2 (or simple string substitution) templates let `/build` produce user-specific Python scripts from a single source of truth.
- **state/:** Isolating state into SQLite + session JSON enables crash recovery — the loop restarts from last known position without replaying completed trades.

## Architectural Patterns

### Pattern 1: Three-Phase Pipeline (Initialize → Build → Run)

**What:** User interaction is separated from code generation, which is separated from execution. No phase bleeds into another.
**When to use:** Always. This is the core contract of the plugin.
**Trade-offs:** Adds one extra step for users, but makes the system inspectable (user can review generated files before running) and safe (no accidental live trading during setup).

**Example flow:**
```
/initialize  →  writes config.json
                ↓
/build       →  reads config.json, generates Python scripts
                ↓
/run         →  spawns main_loop.py (or runs market-analyst agent in Claude)
```

### Pattern 2: Claude as the Analysis Layer (Not the Execution Layer)

**What:** Claude AI is called for reasoning and signal confidence scoring, but never directly submits orders. Orders always go through the Python Risk Manager → Order Executor chain. Claude produces a structured analysis output (JSON) which Python components consume.
**When to use:** Always. This is the key safety boundary.
**Trade-offs:** Slightly slower per cycle due to API call latency; adds cost per analysis call. But prevents hallucinated trades and ensures risk checks run on every order.

**Example decision flow:**
```python
# signal_generator.py
analysis = claude_api.complete(
    prompt=f"Analyze {symbol}: price={price}, RSI={rsi}, volume={vol}. "
           f"Respond JSON: {{action: buy|sell|hold, confidence: 0-1, reasoning: str}}"
)
signal = json.loads(analysis)
if signal["confidence"] > config["min_confidence"]:
    risk_manager.evaluate(signal)  # Always goes through risk check
```

### Pattern 3: Autonomous Loop with State Machine

**What:** The main loop runs as a Python process (or cron job) cycling through states: SCAN → ANALYZE → DECIDE → EXECUTE → TRACK → SLEEP → SCAN. State is persisted to SQLite so the loop can resume after crashes.
**When to use:** The standalone (non-Claude-Code) execution mode.
**Trade-offs:** Requires a persistent process or scheduler. Cron is simpler but coarser-grained; a long-running process with `time.sleep()` is more responsive but needs process supervision.

```
MARKET_CLOSED → wait for open
    ↓
SCANNING      → fetch bars for watchlist symbols
    ↓
ANALYZING     → run indicators, call Claude for reasoning
    ↓
DECIDING      → risk manager evaluates, sizes position
    ↓
EXECUTING     → submit order to Alpaca
    ↓
TRACKING      → poll order status, record fill in SQLite
    ↓
SLEEPING      → wait N seconds (configurable cadence)
    ↓
CIRCUIT_BREAKER (if max daily loss hit) → halt all trading, log alert
```

### Pattern 4: Dual-Mode Execution

**What:** The plugin supports two execution modes from the same generated code base: (a) in-Claude-Code mode where agents loop interactively, (b) standalone Python mode where `main_loop.py` runs on a server via cron or systemd.
**When to use:** Mode is selected during `/initialize` — beginners use Claude-Code mode (supervised), experts use standalone mode (fully autonomous).
**Trade-offs:** Two modes means two code paths to test. Keep shared logic (signal generation, risk, execution) in importable modules. Mode difference is only in the orchestration layer.

## Data Flow

### Full Trading Cycle

```
Market Open
    ↓
Market Scanner
    ├── Alpaca WebSocket stream (real-time bars for watchlist)
    └── Alpaca REST historical bars (for indicator lookups)
    ↓
Signal Generator
    ├── Technical indicators: RSI, MACD, EMA (via pandas-ta or ta-lib)
    ├── Builds context payload (price, indicators, account state)
    └── Calls Claude API with structured prompt
          ↓
    Claude Analysis Response (JSON: action, confidence, reasoning)
    ↓
Risk Manager
    ├── Check: daily loss limit not breached
    ├── Check: max concurrent positions not exceeded
    ├── Check: position size within budget allocation
    ├── Check: signal confidence above threshold
    └── Calculate: position size (Kelly fraction or fixed %)
    ↓ (PASS) or HALT (FAIL → log, skip, check circuit breaker)
Order Executor
    ├── Alpaca REST: submit MarketOrderRequest or LimitOrderRequest
    └── Poll order status until FILLED or CANCELED
    ↓
Portfolio Tracker
    ├── Record fill: symbol, qty, price, timestamp, reasoning
    ├── Update SQLite positions table
    ├── Recalculate daily P&L
    └── Write to trades.log
    ↓
State persisted to SQLite → loop sleeps → next scan cycle
```

### Initialize → Build Data Flow

```
/initialize command
    ↓ (spawns)
setup-wizard agent
    ├── Asks: paper vs live, budget, risk tolerance, strategy, market hours
    ├── Adapts questions to beginner/expert profile
    └── Validates all inputs (budget > 0, API keys present, etc.)
    ↓ (writes)
config.json
    {
      "mode": "paper|live",
      "budget": 10000,
      "risk_per_trade": 0.02,
      "max_daily_loss": 0.05,
      "watchlist": ["AAPL", "MSFT", ...],
      "strategy": "rsi_macd",
      "execution_mode": "claude-code|standalone",
      "min_claude_confidence": 0.7,
      "cadence_seconds": 60
    }
    ↓ (consumed by)
/build command
    ├── Reads config.json
    ├── Renders Python templates with user values
    ├── Writes generated/ directory
    └── Optionally generates cron entry or systemd unit file
```

### In-Claude-Code Mode Agent Flow

```
/run command
    ↓ (spawns)
market-analyst agent
    ├── Uses Alpaca MCP tools to get current bars
    ├── Applies trading-rules skill (auto-injected context)
    ├── Performs analysis, generates signal
    └── Calls trade-executor agent if signal is strong
    ↓
trade-executor agent
    ├── Receives signal from market-analyst
    ├── PreToolUse hook fires (trade-safety-check.sh validates)
    ├── Calls Alpaca MCP order tool
    └── Reports fill back to market-analyst
    ↓
market-analyst agent
    ├── Records trade via portfolio-tracker logic
    └── Sleeps, then starts next cycle
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user, paper trading | Single Python process, SQLite, fixed watchlist of 10-20 symbols. No scaling needed. |
| 1 user, live trading | Same architecture. Add process supervisor (systemd or PM2). Circuit breakers mandatory. |
| Multi-user (marketplace install) | Each user generates their own config + scripts. No shared state. Plugin is stateless; state lives in user's data dir. |
| High-frequency scanning (many symbols) | Batch symbol requests; use Alpaca WebSocket stream instead of REST polling. One WebSocket connection per account limit is a hard constraint. |

### Scaling Priorities

1. **First bottleneck:** Claude API call latency per cycle (200-2000ms). Mitigation: only call Claude when technical indicators produce a candidate signal (pre-filter with Python), not on every bar.
2. **Second bottleneck:** Alpaca WebSocket one-connection-per-account limit. Mitigation: one shared stream handler, fan out to all strategy modules internally.

## Anti-Patterns

### Anti-Pattern 1: Claude Directly Submits Orders

**What people do:** Let the LLM agent call the order submission tool without any intermediate risk check layer.
**Why it's wrong:** LLMs hallucinate. A misconstrued symbol, wrong quantity, or wrong direction goes straight to the market. A single hallucinated trade can exceed the entire daily budget.
**Do this instead:** Claude outputs a structured JSON recommendation. Python Risk Manager validates it. Order Executor submits only after passing all checks. PreToolUse hook adds a final hard gate.

### Anti-Pattern 2: Hardcoding Preferences in the Plugin

**What people do:** Set default watchlists, risk percentages, or strategies in the plugin code itself.
**Why it's wrong:** The plugin must work for beginners (conservative defaults) and experts (aggressive strategies). Hardcoded values alienate one group and may be unsafe for the other.
**Do this instead:** All preferences flow through `/initialize` → `config.json`. The plugin has no opinions about strategy — it only has opinions about safety (circuit breakers, mandatory stop-losses).

### Anti-Pattern 3: Stateless Trading Loop

**What people do:** Run the trading loop in memory without persisting state to disk.
**Why it's wrong:** If the process crashes mid-cycle, you lose track of open positions. On restart you may double-buy or miss a stop-loss.
**Do this instead:** Persist every state transition to SQLite. On startup, reconcile local state with Alpaca's actual positions via REST API before starting the loop.

### Anti-Pattern 4: Single Execution Mode

**What people do:** Build only a Claude-Code-interactive version or only a standalone Python version.
**Why it's wrong:** Claude Code is not always running. Beginners need interactive supervision. Experts need fully autonomous server-side execution. Both user types need to be served.
**Do this instead:** Generate a `main_loop.py` that runs standalone, but also provide Claude agents that can be invoked within Claude Code. Same business logic, different orchestration layer.

### Anti-Pattern 5: Paper → Live Switch in Code

**What people do:** Use `if paper: ... else: ...` branches scattered through the codebase.
**Why it's wrong:** Easy to accidentally enable live mode; impossible to audit which branches are active.
**Do this instead:** The Alpaca client is initialized once from config at startup. `TradingClient(paper=config["paper"])`. All downstream code is mode-agnostic. Mode is a single config value.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Alpaca REST API | `alpaca-py` SDK (`TradingClient`, `StockHistoricalDataClient`) | One client instance, initialized from config. Paper vs live = one constructor flag. |
| Alpaca WebSocket | `StockDataStream` via `alpaca-py` | One connection per account. All symbol subscriptions share this connection. |
| Alpaca MCP Server | `.mcp.json` in plugin root; `${CLAUDE_PLUGIN_ROOT}` variable for path | Starts automatically when plugin is enabled. Exposes Alpaca tools directly to Claude agents. |
| Claude API | Direct Anthropic SDK call from `signal_generator.py` in standalone mode | In Claude-Code mode, this is implicit (agents are already Claude). In standalone mode, explicit API call with structured prompt + JSON response parsing. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `/initialize` command → `config.json` | File write (JSON) | Config is the contract between setup and runtime. Schema must be versioned. |
| `config.json` → generated Python scripts | Template rendering at build time | Values baked in at `/build` time; not re-read at runtime except `config_loader.py` |
| Signal Generator → Risk Manager | Python function call (in-process) | Same process, direct call. Risk Manager returns `(approved: bool, size: float, reason: str)`. |
| Risk Manager → Order Executor | Python function call (in-process) | Only called on approval. Executor is thin — it only translates to Alpaca API calls. |
| Order Executor → Portfolio Tracker | Callback on fill event | Executor polls fill status; on FILLED, calls `tracker.record_fill(fill_data)`. |
| Portfolio Tracker → SQLite | SQLAlchemy or raw sqlite3 | Wrap in transactions. Rollback on error. Reconcile with Alpaca on startup. |
| Plugin agents → Alpaca MCP | MCP tool calls (JSON-RPC over stdio) | Alpaca MCP server must be running. Plugin starts it automatically via `.mcp.json`. |
| PreToolUse hook → trade-safety-check script | Shell script (stdin: tool call JSON, stdout: allow/block) | Script must be executable. Receives full tool call JSON, exits 0 to allow, non-zero to block. |

## Build Order Implications

Components must be built in this dependency order:

1. **config.json schema + /initialize command** — Everything depends on configuration. Build this first.
2. **Plugin manifest + MCP configuration** — Required for any agent to access Alpaca data.
3. **`trading-rules` skill + risk limit reference files** — Must exist before any agent can operate safely.
4. **`setup-wizard` agent** — Powers /initialize; depends on config schema.
5. **`risk-manager` agent + PreToolUse hook** — Safety layer must exist before trade execution agents.
6. **`market-analyst` agent** — Depends on Alpaca MCP and trading-rules skill.
7. **`trade-executor` agent** — Depends on risk-manager agent and hook.
8. **Python runtime templates** (scanner → signal generator → risk manager → order executor → portfolio tracker → main loop) — Generated at `/build` time; build in data-flow order.
9. **`/build` command** — Assembles templates into user scripts.
10. **`/run` command** — Final entry point; depends on everything else working.

## Sources

- [Claude Code Plugins Reference (official)](https://code.claude.com/docs/en/plugins-reference) — Plugin manifest schema, component structure, hook events, MCP server config, CLAUDE_PLUGIN_DATA
- [Claude Code GitHub plugins/README.md](https://github.com/anthropics/claude-code/blob/main/plugins/README.md) — Plugin directory structure conventions
- [Building an AI Trading Chatbot with Alpaca MCP (FlowHunt)](https://www.flowhunt.io/blog/building-ai-trading-chatbot-alpaca-mcp/) — Alpaca MCP integration patterns, data flow loop, cron scheduling
- [Alpaca Algorithmic Trading Python Part 1 (Alpaca official)](https://alpaca.markets/learn/algorithmic-trading-python-alpaca) — REST client initialization, order types, paper vs live
- [Stock Trading Bot Architecture Core Components (Medium)](https://medium.com/@halljames9963/stock-trading-bot-architecture-core-components-explained-d46f5d77c019) — Component breakdown: scanner, signal generator, risk manager, executor
- [alpaca-py Python SDK (GitHub)](https://github.com/alpacahq/alpaca-py) — Official SDK, StockDataStream, TradingClient, order request objects
- [Integrating Alpaca MCP into Python Trading Systems (Medium)](https://medium.com/@philipp.tschakert/integrating-alpaca-mcp-server-into-python-trading-systems-for-data-driven-trading-c1c8506c13cd) — MCP + Python hybrid architecture
- [Polymarket AI Trading Bot (GitHub)](https://github.com/artvandelay/polymarket-agents) — SQLite persistence + Claude decision-making pattern reference
- [MCP for Trading 2026 (varrd.com)](https://www.varrd.com/guides/mcp-trading.html) — MCP tool exposure patterns for trading agents

---
*Architecture research for: Automated stock day trading Claude Code plugin*
*Researched: 2026-03-21*
