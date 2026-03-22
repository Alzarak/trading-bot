---
name: initialize
description: "This skill should be used when the user runs /trading-bot:initialize, wants to set up the trading bot, configure preferences, or generate config.json for the first time."
---

Guide the user through the trading bot setup wizard. Follow every step in order. Re-prompt with an explanation if the user provides invalid input.

## Pre-check

Use Bash to check whether `${CLAUDE_PLUGIN_DATA}/config.json` already exists:

```bash
test -f "${CLAUDE_PLUGIN_DATA}/config.json" && echo "EXISTS" || echo "NOT_FOUND"
```

If it exists AND the user did NOT pass `--reset`: ask whether to reconfigure or keep the existing setup. If keeping, stop and confirm config is unchanged. If `--reset` was passed, proceed with fresh setup.

## Step 1 — Experience Level

Use AskUserQuestion to ask:

> "What is your trading experience level?
> 1. Beginner — new to trading, prefer guided defaults and explanations
> 2. Intermediate — some experience, want balanced options
> 3. Expert — understand trading well, show all parameters"

Store as `experience_level`: `"beginner"`, `"intermediate"`, or `"expert"`.

## Step 2 — Risk Tolerance

Tailor the prompt to experience level:

**Beginner:** Offer conservative (recommended) and moderate. Default to conservative.

**Intermediate/Expert:** Offer all three:
1. Conservative — max 5% per position, 2% daily loss limit
2. Moderate — max 10% per position, 3% daily loss limit
3. Aggressive — max 15% per position, 5% daily loss limit

Store as `risk_tolerance`.

## Step 3 — Budget and Trading Mode

Ask for starting capital in USD. Store as `budget_usd` (positive number).

**Beginner:** Auto-set `paper_trading = true`. Inform the user paper mode is active.

**Intermediate/Expert:** Ask paper vs live trading.
- Live → collect ALPACA_API_KEY and ALPACA_SECRET_KEY for `.env` file. If user declines, default to paper.

## Step 4 — Alpaca MCP Server

First, check if `uvx` is available (required for the MCP server):

```bash
command -v uvx &>/dev/null && echo "UVX_FOUND" || echo "UVX_NOT_FOUND"
```

**If UVX_NOT_FOUND:** Skip the MCP question entirely. Set `use_mcp = false`. Inform the user:

> "Note: The Alpaca MCP server requires `uvx` (part of `uv`). Since it's not installed, the bot will use the Python SDK for all API calls. To enable MCP later, install uv (https://docs.astral.sh/uv/getting-started/installation/) and re-run `/trading-bot:initialize --reset`."

**If UVX_FOUND:** Use AskUserQuestion to ask:

> "Would you like to enable the Alpaca MCP server? This gives Claude direct access to 44 Alpaca API tools (market data, positions, account info) during conversations.
> 1. Yes — enable MCP server (recommended, requires API keys)
> 2. No — use Python SDK only (the bot scripts handle all API calls)"

**If Yes (`use_mcp = true`):**

Check if API keys were already collected in Step 3. If not, ask for them now:

> "The MCP server needs your Alpaca API credentials. Get free keys at https://app.alpaca.markets/
> - ALPACA_API_KEY:
> - ALPACA_SECRET_KEY:"

Then use Bash to add the MCP server to the user's project:

```bash
claude mcp add alpaca \
  --scope project \
  --transport stdio \
  -- uvx alpaca-mcp-server serve
```

Tell the user: "Alpaca MCP server added to your project. The server defaults to paper trading mode. Run `/mcp` to verify it's connected."

**If No (`use_mcp = false`):**

Tell the user: "MCP server skipped. The bot will use the Python alpaca-py SDK for all API calls. You can enable MCP later by re-running `/trading-bot:initialize --reset`."

## Step 5 — Strategies

Read `references/trading-strategies.md` for strategy descriptions. Present all four:

1. **momentum** — RSI + MACD + EMA crossovers
2. **mean_reversion** — Bollinger Bands + RSI
3. **breakout** — Resistance breakout + volume confirmation
4. **vwap** — VWAP intraday reversion

**Beginner:** Recommend momentum, allow 1-2 strategies.
**Intermediate/Expert:** Allow any combination.

Build strategy objects with default params from the reference file. Assign equal weights.

## Step 6 — Autonomy Mode

**Beginner:** Auto-set `autonomy_mode = "fixed_params"`.

**Intermediate/Expert:** Ask fixed parameters vs Claude decides (adjusts position size within bounds).

## Step 7 — Market Hours and Watchlist

Default `market_hours_only = true`. Experts can override.

Ask for watchlist tickers (comma-separated, uppercase).
**Beginner default:** `["AAPL", "MSFT", "GOOGL", "AMZN", "SPY"]`.

## Final Step — Write Config

Compute derived values from `risk_tolerance`:
- conservative: `max_position_pct=5.0`, `max_daily_loss_pct=2.0`
- moderate: `max_position_pct=10.0`, `max_daily_loss_pct=3.0`
- aggressive: `max_position_pct=15.0`, `max_daily_loss_pct=5.0`

Set `autonomy_level`: beginner→`notify_only`, intermediate→`semi_auto`, expert→`full_auto`.

Write `config.json` to `${CLAUDE_PLUGIN_DATA}/config.json` using Bash heredoc (env vars must be shell-expanded). Include `use_mcp` (true/false) in the config. Write `.env` template to `${CLAUDE_PLUGIN_DATA}/.env`.

**Never store API keys in config.json — keys go in .env only.**

Display summary table including MCP status, then tell the user to run `/trading-bot:build` or `/trading-bot:run` next.
