---
name: run
description: "Start the autonomous trading loop — agent mode (default) or standalone Python mode"
allowed-tools: Bash, Read, Write
---

You are starting the autonomous trading bot. Follow the steps below in order.

## Pre-check

Use Bash to verify config.json exists at the plugin data directory:

```bash
test -f "${CLAUDE_PLUGIN_DATA}/config.json" && echo "EXISTS" || echo "NOT_FOUND"
```

If the output is "NOT_FOUND": tell the user — "No configuration found. Please run `/initialize` first to set up your trading preferences, then run `/run` again." Stop here.

## Read Config

Use Bash to read the configuration:

```bash
cat "${CLAUDE_PLUGIN_DATA}/config.json"
```

Parse the JSON to determine:
- `watchlist`: list of symbols to scan
- `autonomy_mode`: user's preferred mode (if set)
- `strategies`: active strategies and their params

## Determine Mode

If the user's message includes the word "standalone" OR the config does not contain an `autonomy_mode` field:
- Run **STANDALONE MODE** (see below)

Otherwise:
- Run **AGENT MODE** (default)

---

## STANDALONE MODE

Use Bash to verify the standalone directory exists:

```bash
test -d "${CLAUDE_PLUGIN_DATA}/trading-bot-standalone" && echo "EXISTS" || echo "NOT_FOUND"
```

If NOT_FOUND: tell the user — "No standalone bot found. Please run `/build` first to generate the standalone scripts, then run `/run standalone` again." Stop here.

If EXISTS, run the standalone bot:

```bash
cd "${CLAUDE_PLUGIN_DATA}/trading-bot-standalone" && python bot.py
```

Tell the user: "Running standalone bot. Press Ctrl+C to stop."

---

## AGENT MODE

In agent mode, you run the trading loop directly within Claude Code. You act as the market analyst, analyzing indicator data and producing structured JSON recommendations. The Python risk manager validates all signals before any order executes.

**You must NEVER call Alpaca order APIs directly. All order routing goes through the Python OrderExecutor and RiskManager.**

### Step 1 — Initialize Trading Components

Use Bash to run a Python snippet that initializes the trading components and checks market status:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" -c "
import json, sys
sys.path.insert(0, '.')
from pathlib import Path

config = json.loads(Path('${CLAUDE_PLUGIN_DATA}/config.json').read_text())
print('CONFIG:', json.dumps(config, indent=2))
print('WATCHLIST:', config.get('watchlist', []))
print('STRATEGIES:', [s['name'] for s in config.get('strategies', [])])
"
```

### Step 2 — Market Hours Check

Use Bash to check if the market is currently open:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" -c "
import json, sys, os
sys.path.insert(0, '.')
from pathlib import Path

config = json.loads(Path('${CLAUDE_PLUGIN_DATA}/config.json').read_text())
api_key = os.environ.get('ALPACA_API_KEY', '')
secret_key = os.environ.get('ALPACA_SECRET_KEY', '')
paper = config.get('paper_trading', True)

if not api_key or not secret_key:
    print('MARKET_STATUS: UNKNOWN (no API keys — set ALPACA_API_KEY and ALPACA_SECRET_KEY)')
    sys.exit(0)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from scripts.market_scanner import MarketScanner

    trading_client = TradingClient(api_key, secret_key, paper=paper)
    data_client = StockHistoricalDataClient(api_key, secret_key)
    scanner = MarketScanner(trading_client, data_client, config)
    is_open = scanner.is_market_open()
    print(f'MARKET_STATUS: {\"OPEN\" if is_open else \"CLOSED\"}')
except Exception as e:
    print(f'MARKET_STATUS: ERROR ({e})')
"
```

If MARKET_STATUS is CLOSED: tell the user the market is currently closed. Ask if they want to continue anyway (for testing) or wait for market hours (9:30 AM – 4:00 PM ET). If they choose to wait, stop here.

### Step 3 — Scan Indicators and Build Analysis Prompts

For each symbol in the watchlist, use Bash to fetch and compute indicators, then output the analysis prompt:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" -c "
import json, sys, os
sys.path.insert(0, '.')
from pathlib import Path

config = json.loads(Path('${CLAUDE_PLUGIN_DATA}/config.json').read_text())
api_key = os.environ.get('ALPACA_API_KEY', '')
secret_key = os.environ.get('ALPACA_SECRET_KEY', '')
paper = config.get('paper_trading', True)
watchlist = config.get('watchlist', [])
strategies = config.get('strategies', [{'name': 'momentum'}])
strategy_name = strategies[0]['name'] if strategies else 'momentum'

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from scripts.market_scanner import MarketScanner
from scripts.claude_analyzer import ClaudeAnalyzer

trading_client = TradingClient(api_key, secret_key, paper=paper)
data_client = StockHistoricalDataClient(api_key, secret_key)
scanner = MarketScanner(trading_client, data_client, config)
analyzer = ClaudeAnalyzer(config=config)
indicator_columns = scanner.get_indicator_columns()

for symbol in watchlist:
    print(f'=== ANALYZING: {symbol} ===')
    df = scanner.scan(symbol)
    if df.empty:
        print(f'SKIP: {symbol} — insufficient data')
        continue
    prompt = analyzer.build_analysis_prompt(symbol, df, strategy_name, indicator_columns)
    print(f'PROMPT_START:{symbol}')
    print(prompt)
    print(f'PROMPT_END:{symbol}')
"
```

### Step 4 — Analyze Each Symbol (Your Role as Market Analyst)

For each PROMPT_START/PROMPT_END block in the output above:

1. Read the indicator data shown in the prompt carefully.
2. Apply the strategy analysis logic:
   - For **momentum**: Look for RSI < 30 (oversold) or RSI > 70 (overbought), MACD histogram direction, EMA crossovers
   - For **mean_reversion**: Look for price near Bollinger Band extremes, RSI reversals from overbought/oversold
   - For **breakout**: Look for price breaking above recent highs with volume confirmation, ATR expansion
3. Produce a structured JSON recommendation matching the ClaudeRecommendation schema:
   ```json
   {
     "symbol": "AAPL",
     "action": "BUY" | "SELL" | "HOLD",
     "confidence": 0.0-1.0,
     "reasoning": "explicit explanation",
     "strategy": "momentum",
     "atr": 1.45,
     "stop_price": 148.55
   }
   ```

**Key instruction:** You are the analyst. Read the indicators, reason about the trade, and return your JSON recommendation. The Python risk manager will validate before any order executes. You must NEVER call Alpaca order APIs directly.

### Step 5 — Parse Recommendations and Execute Signals

After producing your JSON recommendations, use Bash to parse them through ClaudeAnalyzer and route valid signals through OrderExecutor:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" -c "
import json, sys, os
sys.path.insert(0, '.')
from pathlib import Path

# Paste your JSON recommendation(s) here — one per symbol
RECOMMENDATIONS_JSON = '''
[REPLACE_WITH_YOUR_JSON_RECOMMENDATIONS]
'''

config = json.loads(Path('${CLAUDE_PLUGIN_DATA}/config.json').read_text())
api_key = os.environ.get('ALPACA_API_KEY', '')
secret_key = os.environ.get('ALPACA_SECRET_KEY', '')
paper = config.get('paper_trading', True)

from scripts.claude_analyzer import ClaudeAnalyzer
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from scripts.market_scanner import MarketScanner
from scripts.risk_manager import RiskManager
from scripts.state_store import StateStore
from scripts.order_executor import OrderExecutor
from scripts.portfolio_tracker import PortfolioTracker

trading_client = TradingClient(api_key, secret_key, paper=paper)
data_client = StockHistoricalDataClient(api_key, secret_key)
scanner = MarketScanner(trading_client, data_client, config)

data_dir = os.environ.get('CLAUDE_PLUGIN_DATA', '.')
state_store = StateStore(os.path.join(data_dir, 'trading.db'))
risk_manager = RiskManager(config, trading_client, state_store=state_store)
executor = OrderExecutor(risk_manager, config)
tracker = PortfolioTracker(trading_client, state_store, config)
analyzer = ClaudeAnalyzer(config=config)

# Parse each recommendation from your JSON output
import re
for json_block in re.findall(r'\{[^{}]+\}', RECOMMENDATIONS_JSON, re.DOTALL):
    recs = analyzer.parse_response(json_block)
    for rec in recs:
        print(f'Signal: {rec.symbol} {rec.action} confidence={rec.confidence:.2f}')
        signal = rec.to_signal()
        account = trading_client.get_account()
        current_price = float(scanner.scan(rec.symbol).iloc[-1]['close']) if not scanner.scan(rec.symbol).empty else 0.0
        if current_price > 0:
            order = executor.execute_signal(signal, current_price)
            if order:
                tracker.log_trade(rec.symbol, rec.action, current_price, 1, rec.strategy or 'claude', 'market')
                print(f'Order submitted: {order}')
            else:
                print(f'Signal blocked by risk manager: {rec.symbol}')
        else:
            print(f'Could not get current price for {rec.symbol}')
"
```

Replace `[REPLACE_WITH_YOUR_JSON_RECOMMENDATIONS]` with the actual JSON objects you produced in Step 4.

### Step 6 — Loop Control

After completing one scan cycle:

- Display a summary of signals analyzed, orders submitted, and any blocks.
- Ask the user: "Continue scanning? (yes to scan again in 60 seconds, no to stop)"
- If yes: wait 60 seconds, then repeat from Step 2.
- If no: display final portfolio summary and stop.

**Loop timing note:** Claude manages the loop timing by checking market hours and waiting between cycles. This ensures respectful API usage and proper market-hours enforcement.

---

## Safety Reminders

- **Paper trading by default** — All generated configs use `paper_trading: true` until the user explicitly changes it.
- **Risk checks are mandatory** — OrderExecutor runs RiskManager checks before every order. Signals blocked by the risk manager are expected behavior, not errors.
- **No direct Alpaca order calls** — You must NEVER call `trading_client.submit_order()` or any Alpaca order API directly. Always route through `OrderExecutor.execute_signal()`.
- **ClaudeAnalyzer is the bridge** — Use `build_analysis_prompt()` to format indicator data, and `parse_response()` to parse your own recommendations. This ensures consistent JSON schema validation.
