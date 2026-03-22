# Alpaca API Patterns Reference

This document provides copy-paste-ready Python code patterns for all Alpaca API operations using the `alpaca-py` SDK (v0.43.2). Do NOT use the deprecated `alpaca-trade-api` package.

---

## Authentication

```python
import os
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient

# Paper trading (safe default — use for development and testing)
trading_client = TradingClient(
    api_key=os.environ["ALPACA_API_KEY"],
    secret_key=os.environ["ALPACA_SECRET_KEY"],
    paper=True,  # Routes to paper endpoint automatically
)

# Live trading (requires explicit opt-in — paper_trading=false in config)
trading_client = TradingClient(
    api_key=os.environ["ALPACA_API_KEY"],
    secret_key=os.environ["ALPACA_SECRET_KEY"],
    paper=False,  # Routes to live endpoint
)

# Market data client (same key pair, no paper flag needed)
data_client = StockHistoricalDataClient(
    api_key=os.environ["ALPACA_API_KEY"],
    secret_key=os.environ["ALPACA_SECRET_KEY"],
)
```

**Required environment variables:**
- `ALPACA_API_KEY` — Alpaca API key ID
- `ALPACA_SECRET_KEY` — Alpaca API secret key
- `ALPACA_PAPER` — `"true"` for paper trading, `"false"` for live (used by the bot's pydantic-settings)

> **Note:** The Alpaca MCP server uses a different env var: `ALPACA_PAPER_TRADE` (defaults to `True`). The bot's `ALPACA_PAPER` and the MCP server's `ALPACA_PAPER_TRADE` are independent — each controls its own system.

**Loading with pydantic-settings:**
```python
from pydantic_settings import BaseSettings

class BotConfig(BaseSettings):
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_paper: bool = True

    class Config:
        env_file = ".env"

config = BotConfig()
client = TradingClient(config.alpaca_api_key, config.alpaca_secret_key, paper=config.alpaca_paper)
```

---

## Market Data (Historical)

```python
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Fetch OHLCV bars for indicator calculation
def get_bars(symbol: str, days_back: int = 60) -> "pd.DataFrame":
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,          # 1-minute bars
        start=datetime.now(ET) - timedelta(days=days_back),
        end=datetime.now(ET),
        feed="iex",                          # Use IEX feed (free tier)
    )
    bars = data_client.get_stock_bars(request)
    df = bars.df                             # Returns pandas DataFrame
    return df.reset_index(level=0, drop=True)  # Drop symbol from multi-index
```

**TimeFrame options:** `TimeFrame.Minute`, `TimeFrame.Hour`, `TimeFrame.Day`

---

## Market Clock

```python
# Check if market is currently open before submitting orders
def is_market_open() -> bool:
    clock = trading_client.get_clock()
    return clock.is_open

# Get next open time for scheduling
def get_next_open() -> datetime:
    clock = trading_client.get_clock()
    return clock.next_open

# Full clock info
clock = trading_client.get_clock()
print(f"Market open: {clock.is_open}")
print(f"Current time: {clock.timestamp}")
print(f"Next open: {clock.next_open}")
print(f"Next close: {clock.next_close}")
```

---

## Order Submission

```python
import uuid
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    TrailingStopOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

# Market order (immediate fill at best available price)
def submit_market_order(symbol: str, qty: int, side: OrderSide) -> "Order":
    request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,                           # OrderSide.BUY or OrderSide.SELL
        time_in_force=TimeInForce.DAY,       # Day order (expires at market close)
        client_order_id=str(uuid.uuid4()),   # Idempotency key
    )
    return trading_client.submit_order(request)

# Bracket order (entry + take-profit + stop-loss in one atomic submission)
def submit_bracket_order(
    symbol: str,
    qty: int,
    limit_price: float,
    take_profit_price: float,
    stop_loss_price: float,
) -> "Order":
    request = LimitOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        client_order_id=str(uuid.uuid4()),
        order_class=OrderClass.BRACKET,      # Submits all three legs atomically
        limit_price=limit_price,
        take_profit=TakeProfitRequest(limit_price=take_profit_price),
        stop_loss=StopLossRequest(stop_price=stop_loss_price),
    )
    return trading_client.submit_order(request)

# Trailing stop order
def submit_trailing_stop(symbol: str, qty: int, trail_percent: float) -> "Order":
    request = TrailingStopOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.GTC,       # Good-till-cancelled for trailing stops
        client_order_id=str(uuid.uuid4()),
        trail_percent=trail_percent,         # Trail distance as percentage
    )
    return trading_client.submit_order(request)
```

---

## Account Info

```python
# Get account status and equity
def get_account_info():
    account = trading_client.get_account()
    return {
        "equity": float(account.equity),
        "buying_power": float(account.buying_power),
        "cash": float(account.cash),
        "portfolio_value": float(account.portfolio_value),
        "day_trade_count": account.daytrade_count,
        "pattern_day_trader": account.pattern_day_trader,
    }

# Check circuit breaker: has daily loss exceeded threshold?
def check_circuit_breaker(start_equity: float, max_daily_loss_pct: float) -> bool:
    account = trading_client.get_account()
    current_equity = float(account.equity)
    daily_loss_pct = (start_equity - current_equity) / start_equity * 100
    return daily_loss_pct >= max_daily_loss_pct
```

---

## Position Management

```python
from alpaca.trading.requests import ClosePositionRequest

# Get all open positions
def get_all_positions() -> list:
    return trading_client.get_all_positions()

# Get position for a specific symbol (raises exception if no position)
def get_position(symbol: str):
    try:
        return trading_client.get_open_position(symbol)
    except Exception:
        return None  # No position exists for this symbol

# Close a specific position (market order)
def close_position(symbol: str):
    trading_client.close_position(symbol)

# Close all positions (emergency exit)
def close_all_positions():
    trading_client.close_all_positions(cancel_orders=True)  # Also cancel open orders
```

---

## Error Handling

```python
import time
from alpaca.common.exceptions import APIError

def submit_order_with_retry(request, max_retries: int = 4) -> "Order | None":
    """
    Submit an order with exponential backoff retry.
    Skips retry on 422 (validation error) — these will not succeed on retry.
    """
    wait_times = [1, 2, 4, 8]  # Seconds between retries

    for attempt in range(max_retries + 1):
        try:
            return trading_client.submit_order(request)
        except APIError as e:
            if e.status_code == 422:
                # Validation error — retrying will not help
                logger.error(f"Order validation failed (422): {e}. Skipping.")
                return None
            if e.status_code == 403:
                # Auth error — retrying will not help
                logger.error(f"Order auth failed (403): {e}. Check API keys.")
                return None
            if attempt < max_retries:
                wait = wait_times[attempt]
                logger.warning(f"Order attempt {attempt + 1} failed: {e}. Retrying in {wait}s.")
                time.sleep(wait)
            else:
                logger.error(f"Order failed after {max_retries + 1} attempts: {e}")
                return None
    return None

# Ghost position check: verify position state after any order failure
def verify_position_state(symbol: str) -> bool:
    """Returns True if a position exists (order may have been filled before error)."""
    position = get_position(symbol)
    return position is not None
```
