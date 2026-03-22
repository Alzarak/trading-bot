---
name: initialize
description: "Interactive setup wizard -- configure the trading bot preferences and generate config.json"
argument-hint: "[--reset]"
allowed-tools: AskUserQuestion, Write, Bash, Read
---

You are guiding the user through the trading bot setup wizard. Follow every step in order. Do not skip steps. Re-prompt with an explanation if the user provides invalid input.

## Pre-check

Use Bash to check whether `${CLAUDE_PLUGIN_DATA}/config.json` already exists:

```bash
test -f "${CLAUDE_PLUGIN_DATA}/config.json" && echo "EXISTS" || echo "NOT_FOUND"
```

If it exists AND the user did NOT pass `--reset`: ask whether they want to reconfigure or keep the existing setup. If they choose to keep it, stop and tell them the config is unchanged. If `--reset` was passed, proceed with a fresh setup regardless.

## Step 1 — Experience Level

Use AskUserQuestion to ask:

> "What is your trading experience level?
> 1. Beginner — new to trading, prefer guided defaults and explanations
> 2. Intermediate — some experience, want balanced options
> 3. Expert — understand trading well, show all parameters"

Store the answer as `experience_level`:
- "1" or "beginner" → `"beginner"`
- "2" or "intermediate" → `"intermediate"`
- "3" or "expert" → `"expert"`

If the input is anything else, re-prompt with: "Please enter 1, 2, or 3."

## Step 2 — Risk Tolerance

Use AskUserQuestion to ask about risk tolerance. Tailor the prompt to the experience level:

**Beginner:** "How cautious should the bot be with your money?
1. Conservative (recommended for beginners) — small positions, strict loss limits
2. Moderate — balanced risk and reward"
Default to conservative if they press Enter without answering. Valid values: conservative, moderate.

**Intermediate/Expert:** "Choose your risk tolerance:
1. Conservative — max 5% per position, 2% daily loss limit
2. Moderate — max 10% per position, 3% daily loss limit
3. Aggressive — max 15% per position, 5% daily loss limit"
No default. All three options valid.

Store the answer as `risk_tolerance`: `"conservative"`, `"moderate"`, or `"aggressive"`.
Re-prompt if input is invalid.

## Step 3 — Budget and Trading Mode

Use AskUserQuestion to ask for the starting capital to allocate to the bot (in USD). Store as `budget_usd` (a positive number). Re-prompt if the value is not a positive number.

**Beginner:** Do NOT ask about paper vs live. Inform the user: "For beginners, the bot runs in paper trading mode (simulated money) so you can practice safely. You can switch to live trading later." Set `paper_trading = true`.

**Intermediate/Expert:** Use AskUserQuestion to ask: "Use paper trading (simulated) or live trading (real money)?
1. Paper trading — Alpaca provides $100,000 simulated capital, no real money at risk
2. Live trading — uses real money in your Alpaca account (CAUTION: real losses possible)"

- "1" or "paper" → `paper_trading = true`
- "2" or "live" → `paper_trading = false`, then immediately ask:
  "Please provide your Alpaca API credentials (these go in .env only, never in config.json):
  - ALPACA_API_KEY:
  - ALPACA_SECRET_KEY:"
  Store these for the .env file. If the user declines, set `paper_trading = true` and continue.

## Step 4 — Strategies

Read `references/trading-strategies.md` for strategy descriptions.

Use AskUserQuestion to present all four strategies:
1. **momentum** — Follows trending stocks using RSI, MACD, and EMA crossovers. Good for trending markets.
2. **mean_reversion** — Bets that prices return to average after deviating. Uses Bollinger Bands + RSI.
3. **breakout** — Enters when price breaks above resistance with volume confirmation.
4. **vwap** — Trades mean reversion relative to intraday VWAP. Best mid-session (10am–3pm ET).

**Beginner:** "For simplicity, I recommend starting with just Momentum (option 1). You can add more strategies later. Which would you like? (default: 1)"
Allow selecting 1–2 strategies. Default to momentum.

**Intermediate/Expert:** Allow any combination. Ask for comma-separated list (e.g. "1,3" or "momentum,breakout").

For each selected strategy, build a strategy object with default params from the reference file:

- `momentum`: `{"rsi_period": 14, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "ema_short": 9, "ema_long": 21}`
- `mean_reversion`: `{"bb_period": 20, "bb_std_dev": 2.0, "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70}`
- `breakout`: `{"lookback_period": 20, "volume_multiplier": 1.5, "atr_period": 14}`
- `vwap`: `{"deviation_threshold_pct": 1.5, "rsi_period": 14, "max_deviation_pct": 2.0, "trading_start_hour": 10, "trading_end_hour": 15}`

Assign equal weights to all selected strategies (e.g., 2 strategies → each gets weight 0.5; 1 strategy → weight 1.0).

Store as `strategies` array with `{name, weight, params}` objects.
Re-prompt if no valid strategy is selected.

## Step 5 — Autonomy Mode

**Beginner:** Automatically set `autonomy_mode = "fixed_params"`. Inform the user: "The bot will use the exact risk parameters you've set. You can change this later."

**Intermediate/Expert:** Use AskUserQuestion to ask:
"How should the bot decide trade aggressiveness?
1. Fixed parameters — bot uses exactly the risk limits you configured
2. Claude decides — Claude analyzes each trade opportunity and adjusts position size and entry thresholds within your bounds"

- "1" or "fixed" → `autonomy_mode = "fixed_params"`
- "2" or "claude" → `autonomy_mode = "claude_decides"`

Re-prompt if invalid.

## Step 6 — Market Hours and Watchlist

**Market hours:** Default `market_hours_only = true`. For Experts only, ask: "Restrict trading to market hours (9:30am–4:00pm ET)? (yes/no, default: yes)". If "no", set `market_hours_only = false`.

**Watchlist:** Use AskUserQuestion to ask for ticker symbols (comma-separated, uppercase).

**Beginner:** "Enter ticker symbols to watch, or press Enter for the recommended defaults (AAPL, MSFT, GOOGL, AMZN, SPY):"
If the user presses Enter or leaves blank, use `["AAPL", "MSFT", "GOOGL", "AMZN", "SPY"]`.

**Expert:** "Enter ticker symbols to trade (comma-separated, e.g. AAPL,TSLA,SPY):"
No default — require at least one entry.

Validate: each ticker must be uppercase letters only (A-Z). Strip spaces. Re-prompt if any ticker is invalid or the list is empty.
Store as `watchlist` array of uppercase strings.

## Final Step — Write Config

Use Bash to resolve the plugin data directory:

```bash
echo "${CLAUDE_PLUGIN_DATA}"
```

Capture the output as `PLUGIN_DATA_DIR`.

Compute derived values based on `risk_tolerance`:
- `conservative`: `max_position_pct = 5.0`, `max_daily_loss_pct = 2.0`
- `moderate`: `max_position_pct = 10.0`, `max_daily_loss_pct = 3.0`
- `aggressive`: `max_position_pct = 15.0`, `max_daily_loss_pct = 5.0`

Set `autonomy_level`:
- beginner → `"notify_only"`
- intermediate → `"semi_auto"`
- expert → `"full_auto"`

Set `config_version = "1"`.

Get the current ISO 8601 timestamp for `created_at`:

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

Write `config.json` to `${CLAUDE_PLUGIN_DATA}/config.json` using Bash heredoc (never use Write tool for this — env vars must be expanded by the shell):

```bash
mkdir -p "${CLAUDE_PLUGIN_DATA}"
cat > "${CLAUDE_PLUGIN_DATA}/config.json" << 'CONFIGEOF'
<insert the complete JSON config here with all collected values>
CONFIGEOF
```

The JSON must include all fields: `experience_level`, `paper_trading`, `risk_tolerance`, `autonomy_mode`, `max_position_pct`, `max_daily_loss_pct`, `budget_usd`, `strategies`, `market_hours_only`, `watchlist`, `autonomy_level`, `config_version`, `created_at`.

IMPORTANT: Never store API keys in config.json. API keys go in .env only.

Write the .env template to `${CLAUDE_PLUGIN_DATA}/.env`:

```bash
cat > "${CLAUDE_PLUGIN_DATA}/.env" << 'ENVEOF'
ALPACA_API_KEY=<user_key_or_your_key_here>
ALPACA_SECRET_KEY=<user_secret_or_your_secret_here>
ALPACA_PAPER=<true_or_false>
ENVEOF
```

If the user provided live API keys in Step 3, substitute the real values. Otherwise use `your_key_here` and `your_secret_here` as placeholders, and set `ALPACA_PAPER=true`.

Display a summary table of the final configuration using plain text or markdown formatting. Then tell the user:
- Where config.json was written
- Where .env was written
- What to do next: "Run `/build` to generate the trading bot scripts, then `/run` to start trading."
