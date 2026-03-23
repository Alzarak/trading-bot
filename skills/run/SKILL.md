---
name: run
description: "This skill should be used when the user runs /trading-bot:run, wants to start the trading loop, begin autonomous trading, or execute the bot in agent or standalone mode."
---

Start the autonomous trading bot. Follow steps in order.

## Pre-check

Verify config.json exists:

```bash
BOT_DIR="$(pwd)/trading-bot"
MISSING=""

if [ ! -d "${BOT_DIR}" ]; then
  MISSING="trading-bot folder"
fi

if [ ! -f "${BOT_DIR}/config.json" ] || [ "$(cat "${BOT_DIR}/config.json" 2>/dev/null)" = "{}" ]; then
  MISSING="${MISSING:+${MISSING}, }config.json (empty or missing)"
fi

if [ -n "$MISSING" ]; then
  echo "MISSING: ${MISSING}"
else
  echo "ALL_FOUND"
fi
```

**If MISSING:** Tell the user: "Missing: {list}. Please run `/trading-bot:initialize` first to set up your bot." Stop.

Read the config to determine `watchlist`, `autonomy_mode`, `strategies`, and `use_mcp`.

If `use_mcp` is true, Alpaca MCP tools are available for real-time market data queries (account info, positions, quotes) during the trading loop. Use MCP tools to supplement indicator data when available.

If `use_mcp` is false or not set, all market data comes through the Python alpaca-py SDK via MarketScanner. Do not attempt to call MCP tools.

## Mode Selection

If user's message includes "standalone" OR config has no `autonomy_mode`: run **STANDALONE MODE**.
Otherwise: run **AGENT MODE** (default).

---

## STANDALONE MODE

Verify bot directory exists, then run:

```bash
cd "$(pwd)/trading-bot/bot" && python bot.py
```

If directory missing: tell user to run `/trading-bot:build` first.

---

## AGENT MODE

Run the trading loop within Claude Code using external scripts. Claude analyzes indicator output and produces JSON recommendations. The Python risk manager validates all signals before order execution.

**NEVER call Alpaca order APIs directly. All orders go through OrderExecutor and RiskManager.**
**NEVER write inline Python that creates Alpaca clients or constructors. Always call the provided scripts.**

### Path variables

Use these exact variables for ALL bash commands in this skill:
```
BOT_DIR="$(pwd)/trading-bot"
VENV="${BOT_DIR}/venv/bin/python"
SCRIPTS="$(pwd)/.claude/trading-bot"
```

### Step 1 — Scan Market Indicators

Run the scan script. Do NOT modify this command — copy it exactly:

```bash
BOT_DIR="$(pwd)/trading-bot"
VENV="${BOT_DIR}/venv/bin/python"
SCRIPTS="$(pwd)/.claude/trading-bot"

PYTHONPATH="${SCRIPTS}" ${VENV} "${SCRIPTS}/scripts/cli_scan.py"
```

To scan specific symbols instead of the config watchlist:
```bash
PYTHONPATH="${SCRIPTS}" ${VENV} "${SCRIPTS}/scripts/cli_scan.py" AAPL MSFT NVDA
```

Display the scan results to the user. If market is closed, ask whether to continue (for testing) or wait.

### Step 2 — Analyze Each Symbol

Read the indicator output from Step 1. For each symbol, apply the configured strategy logic:

- **momentum**: RSI extremes (>70 overbought, <30 oversold), MACD histogram direction, EMA crossovers
- **mean_reversion**: Bollinger Band extremes, RSI reversals
- **breakout**: Price breaking resistance with volume, ATR expansion
- **vwap**: Price vs VWAP reversion

For each symbol, produce a recommendation as JSON:

```json
{
  "symbol": "AAPL",
  "action": "BUY",
  "confidence": 0.78,
  "reasoning": "RSI at 28 (oversold), MACD histogram turning positive, EMA_9 crossing above EMA_21",
  "strategy": "momentum",
  "atr": 1.45,
  "stop_price": 148.55
}
```

- `action`: `"BUY"`, `"SELL"`, or `"HOLD"`
- `confidence`: 0.0 to 1.0 — only >= 0.6 will pass through to execution
- `stop_price`: entry price minus (ATR * 2) for BUY, plus (ATR * 2) for SELL
- `reasoning`: explicit explanation — never omit, required for audit trail

### Step 3 — Execute Signals

Write the recommendations from Step 2 to a JSON file, then run through the execution pipeline:

```bash
BOT_DIR="$(pwd)/trading-bot"
VENV="${BOT_DIR}/venv/bin/python"
SCRIPTS="$(pwd)/.claude/trading-bot"

# Write recommendations to file (replace RECOMMENDATIONS_JSON with actual JSON array)
cat > "${BOT_DIR}/recommendations.json" << 'RECEOF'
RECOMMENDATIONS_JSON
RECEOF

PYTHONPATH="${SCRIPTS}" ${VENV} -c "
import json, os, sys
sys.path.insert(0, '${SCRIPTS}')

from dotenv import load_dotenv
load_dotenv('${BOT_DIR}/.env')

from scripts.bot import create_clients, load_config
from scripts.order_executor import OrderExecutor
from scripts.risk_manager import RiskManager
from scripts.state_store import StateStore
from scripts.audit_logger import AuditLogger
from scripts.claude_analyzer import ClaudeAnalyzer
from scripts.bot import execute_claude_recommendation
from scripts.portfolio_tracker import PortfolioTracker
from scripts.notifier import Notifier
from pathlib import Path

config = json.loads(Path('${BOT_DIR}/config.json').read_text())
trading_client, data_client = create_clients(config)
state_store = StateStore(Path('${BOT_DIR}/trading.db'))
audit_logger = AuditLogger(Path('${BOT_DIR}'))
notifier = Notifier(config)
risk_manager = RiskManager(config, trading_client, state_store=state_store, notifier=notifier)
risk_manager.initialize_session()
executor = OrderExecutor(risk_manager, config)
tracker = PortfolioTracker(trading_client, state_store, config, notifier=notifier)
analyzer = ClaudeAnalyzer(config)

recs = json.loads(Path('${BOT_DIR}/recommendations.json').read_text())
for rec_json in recs:
    result = execute_claude_recommendation(
        json.dumps(rec_json), executor, tracker, state_store, audit_logger, analyzer
    )
    print(json.dumps(result, indent=2))

state_store.close()
"
```

Replace `RECOMMENDATIONS_JSON` with the actual JSON array from Step 2. Display results to user.

### Step 4 — Loop Control

Display scan cycle summary. Ask user to continue (scan again in 60s) or stop. If stopping, display final portfolio summary.

---

## Safety

- Paper trading by default — all configs use `paper_trading: true`
- Risk checks mandatory — OrderExecutor runs RiskManager before every order
- No direct Alpaca order calls — always route through OrderExecutor
- ClaudeAnalyzer bridges analysis to execution with consistent JSON validation
