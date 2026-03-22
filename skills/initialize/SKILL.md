---
name: initialize
description: "This skill should be used when the user runs /trading-bot:initialize, wants to set up the trading bot, configure preferences, or generate config.json for the first time."
---

Guide the user through setting up their autonomous trading bot. This bot will scan markets, analyze opportunities using Claude, and execute trades on its own — the user only needs to configure preferences here, then the bot handles the rest.

Frame every question around configuring an autonomous system, not manual trading. Follow every step in order. Re-prompt with an explanation if the user provides invalid input.

## Pre-check

Use Bash to check whether `${CLAUDE_PLUGIN_DATA}/config.json` already exists:

```bash
test -f "${CLAUDE_PLUGIN_DATA}/config.json" && echo "EXISTS" || echo "NOT_FOUND"
```

If it exists AND the user did NOT pass `--reset`: ask whether to reconfigure or keep the existing setup. If keeping, stop and confirm config is unchanged. If `--reset` was passed, proceed with fresh setup.

## Step 1 — Experience Level

Use AskUserQuestion to ask:

> "What is your trading experience level? This helps the bot pick smart defaults for your autonomous setup.
> 1. Beginner — new to trading, the bot will use safe defaults and explain its decisions
> 2. Intermediate — some experience, the bot balances safety with flexibility
> 3. Expert — experienced trader, full control over parameters the bot uses"

Store as `experience_level`: `"beginner"`, `"intermediate"`, or `"expert"`.

## Step 2 — Involvement Level

Use AskUserQuestion to ask:

> "How involved do you want to be while the bot is running?
> 1. Hands-off — the bot trades autonomously, I'll check results when I want
> 2. Notify me — the bot trades autonomously but I want summaries and alerts
> 3. Approve trades — the bot finds opportunities but I approve before it executes"

Store as `involvement_level`: `"hands_off"`, `"notify"`, or `"approve"`.

**Beginner override:** If experience is beginner and they chose hands-off, gently note: "Since you're new to trading, the bot will start in notify mode so you can learn from its decisions. You can switch to fully hands-off anytime." Override to `"notify"`.

## Step 3 — Risk Tolerance

Tailor the prompt to experience level:

**Beginner:** Offer conservative (recommended) and moderate. Default to conservative.

**Intermediate/Expert:** Offer all three:
1. Conservative — max 5% per position, 2% daily loss limit
2. Moderate — max 10% per position, 3% daily loss limit
3. Aggressive — max 15% per position, 5% daily loss limit

Store as `risk_tolerance`.

## Step 4 — Budget and Trading Mode

Ask how much starting capital (in USD) the bot should trade with. Present these options:

1. $10 — Just testing — see the bot in action with minimal risk
2. $25 — Starter — enough for the bot to make a few real trades
3. $100 — Standard — gives the bot room to diversify across a few stocks
4. $500 — Comfortable — more flexibility for the bot's strategies
5. $1,000+ — Serious — the bot can fully utilize all strategies
6. Custom amount (minimum $1)

Store as `budget_usd` (positive number, minimum 1).

**Beginner:** Auto-set `paper_trading = true`. Inform the user paper mode is active.

**Intermediate/Expert:** Ask paper vs live trading. Store as `paper_trading` (true/false).

API keys are NOT collected interactively — they go in the `.env` file created in the Final Step. Tell the user: "You'll need your Alpaca API key and secret key. The setup will create a `.env` file where you add them. Get free keys at https://app.alpaca.markets/"

## Step 5 — Alpaca MCP Server

First, check if `uvx` is available (required for the MCP server):

```bash
command -v uvx &>/dev/null && echo "UVX_FOUND" || echo "UVX_NOT_FOUND"
```

**If UVX_NOT_FOUND:** Still ask the MCP question (below), but if the user says Yes, offer to install `uv` for them:

> "`uvx` is required for the MCP server but isn't installed. Would you like me to install it now?
> 1. Yes — install uv (runs: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
> 2. No — skip MCP, use Python SDK only"

If they say Yes, run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then verify it worked:

```bash
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" && command -v uvx &>/dev/null && echo "UVX_INSTALLED" || echo "UVX_FAILED"
```

If `UVX_INSTALLED`: continue with MCP setup below. If `UVX_FAILED`: set `use_mcp = false` and tell the user installation failed — they can install manually and re-run `/trading-bot:initialize --reset`.

If they say No: set `use_mcp = false` and continue.

**Use AskUserQuestion to ask:**

> "Would you like to enable the Alpaca MCP server? This gives Claude direct access to 44 Alpaca API tools (market data, positions, account info) during conversations.
> 1. Yes — enable MCP server (recommended, requires API keys)
> 2. No — use Python SDK only (the bot scripts handle all API calls)"

**If Yes (`use_mcp = true`):**

The MCP server also reads from the `.env` file. Tell the user: "The MCP server will use the same API keys from your `.env` file."

Use Bash to add the MCP server to the user's project:

```bash
claude mcp add alpaca \
  --scope project \
  --transport stdio \
  -- uvx alpaca-mcp-server serve
```

Tell the user: "Alpaca MCP server added to your project. The server defaults to paper trading mode. Run `/mcp` to verify it's connected."

**If No (`use_mcp = false`):**

Tell the user: "MCP server skipped. The bot will use the Python alpaca-py SDK for all API calls. You can enable MCP later by re-running `/trading-bot:initialize --reset`."

## Step 6 — Strategies

Read `references/trading-strategies.md` for strategy descriptions. Present all four:

1. **momentum** — RSI + MACD + EMA crossovers
2. **mean_reversion** — Bollinger Bands + RSI
3. **breakout** — Resistance breakout + volume confirmation
4. **vwap** — VWAP intraday reversion

**Beginner:** Recommend momentum, allow 1-2 strategies.
**Intermediate/Expert:** Allow any combination.

Build strategy objects with default params from the reference file. Assign equal weights.

## Step 7 — Autonomy Mode

This controls whether the bot uses fixed parameters or lets Claude adjust strategy parameters (position sizing, indicator thresholds) within the risk bounds configured above.

**Beginner:** Auto-set `autonomy_mode = "fixed_params"`. Tell the user: "The bot will use the exact parameters from your chosen strategies — consistent and predictable."

**Intermediate/Expert:** Use AskUserQuestion to ask:

> "How should the bot handle strategy parameters while trading?
> 1. Fixed parameters — the bot uses your configured settings exactly, every time
> 2. Claude-adaptive — Claude can adjust position sizes and indicator thresholds within your risk limits based on market conditions"

Store as `autonomy_mode`: `"fixed_params"` or `"claude_adaptive"`.

## Step 8 — Market Hours and Stock Discovery

Default `market_hours_only = true`. Experts can override.

Use AskUserQuestion to ask:

> "How should the bot find stocks to trade?
> 1. Auto-discover — the bot scans the market each session for the best opportunities (recommended)
> 2. Focused list — give the bot specific tickers to watch, it still analyzes and decides autonomously
> 3. Both — start with a focused list but also scan for new opportunities"

Store as `discovery_mode`: `"auto"`, `"focused"`, or `"both"`.

**If focused or both:** Ask for tickers (comma-separated, uppercase). Store as `watchlist`. Explain: "These are starting points — the bot will analyze these first but still makes its own trading decisions."

**If auto:** Set `watchlist` to `[]`. Tell the user: "The bot will scan market movers, volume leaders, and sector trends each session to find its own opportunities."

## Final Step — Write Config

Compute derived values from `risk_tolerance`:
- conservative: `max_position_pct=5.0`, `max_daily_loss_pct=2.0`
- moderate: `max_position_pct=10.0`, `max_daily_loss_pct=3.0`
- aggressive: `max_position_pct=15.0`, `max_daily_loss_pct=5.0`

Set `autonomy_level` from `involvement_level`: `hands_off`→`full_auto`, `notify`→`notify_only`, `approve`→`approval_required`.

Write `config.json` to `${CLAUDE_PLUGIN_DATA}/config.json` using Bash heredoc (env vars must be shell-expanded). Include `use_mcp` (true/false), `involvement_level`, `autonomy_mode`, and `discovery_mode` in the config.

**Never store API keys in config.json — keys go in .env only.**

Write `.env` to `${CLAUDE_PLUGIN_DATA}/.env` with this content:

```
# Alpaca API Credentials
# Get your free keys at: https://app.alpaca.markets/
# Both values are required — find them under API Keys in your Alpaca dashboard
ALPACA_API_KEY=
ALPACA_SECRET_KEY=

# Paper trading mode (true = simulated, false = real money)
ALPACA_PAPER=true
```

Set `ALPACA_PAPER` based on the user's paper/live choice from Step 4.

After writing, tell the user:
"Created `.env` file at `${CLAUDE_PLUGIN_DATA}/.env`. **Before running the bot, add your Alpaca credentials:**
1. Go to https://app.alpaca.markets/ and sign up (free)
2. Navigate to API Keys in your dashboard
3. Copy your **API Key ID** and **Secret Key**
4. Paste them into the `.env` file

Both the API key and secret key are required — the bot and MCP server won't work without them."

Display summary table including MCP status and involvement mode, then set expectations:

**Hands-off/Notify:** "Your bot is configured to trade autonomously. After building, just run `/trading-bot:run` and it will scan markets, analyze opportunities with Claude, and execute trades on its own within your risk limits."

**Approve:** "Your bot is configured to find trades and ask for your approval before executing. Run `/trading-bot:run` and it will present opportunities for you to approve or skip."

Tell the user the next step is `/trading-bot:build` to generate the trading scripts, then `/trading-bot:run` to start autonomous trading.
