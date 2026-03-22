"""Portfolio tracker module for trading bot.

Logs every trade to a rotating loguru JSON file sink and to SQLite via StateStore.
Tracks P&L as (current_equity - start_equity) / start_equity percentage.

Two log destinations for every trade:
- Rotating JSON file at CLAUDE_PLUGIN_DATA/trades_{date}.log (90-day retention)
- SQLite trade_log table via StateStore.log_trade()
"""
import os
from pathlib import Path

from loguru import logger

# Configure a trade-specific loguru sink at module level.
# Only messages bound with trade=True flow to this sink.
_data_dir = Path(os.environ.get("CLAUDE_PLUGIN_DATA", "/tmp"))
logger.add(
    str(_data_dir / "trades_{time:YYYY-MM-DD}.log"),
    format="{message}",
    filter=lambda record: "trade" in record["extra"],
    rotation="1 day",
    retention="90 days",
    serialize=True,
)

trade_logger = logger.bind(trade=True)


class PortfolioTracker:
    """Tracks P&L and logs every trade to file and SQLite.

    Args:
        trading_client: Alpaca TradingClient instance (or mock) — used to
                        fetch account equity for P&L calculations.
        state_store: StateStore instance — receives every trade via log_trade().
        config: Trading configuration dict (from config.json).

    On initialization, fetches start_equity from the Alpaca account.
    This is the baseline for daily P&L calculations.
    """

    def __init__(self, trading_client, state_store, config: dict, notifier=None) -> None:
        self.trading_client = trading_client
        self.state_store = state_store
        self.config = config
        self.notifier = notifier

        # Capture start equity for P&L baseline
        account = trading_client.get_account()
        self.start_equity: float = float(account.equity)
        logger.info(
            "PortfolioTracker initialized. Start equity: ${:.2f}",
            self.start_equity,
        )

    # ------------------------------------------------------------------
    # Trade logging
    # ------------------------------------------------------------------

    def log_trade(
        self,
        symbol: str,
        action: str,
        price: float,
        qty: int,
        strategy: str,
        order_type: str,
        pnl: float | None = None,
    ) -> None:
        """Log a trade to both the rotating loguru JSON file and SQLite.

        Args:
            symbol: Ticker symbol (e.g. 'AAPL').
            action: Trade direction ('BUY' or 'SELL').
            price: Execution price per share.
            qty: Number of shares traded.
            strategy: Name of the strategy that produced this trade.
            order_type: Order type used ('bracket', 'market', 'limit', etc.).
            pnl: Realized profit/loss for SELL trades; None for BUY entries.
        """
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Log to rotating JSON file via loguru trade sink
        trade_logger.info(
            "TRADE",
            timestamp=timestamp,
            ticker=symbol,
            action=action,
            price=price,
            qty=qty,
            pnl=pnl,
            strategy=strategy,
            order_type=order_type,
        )

        # 2. Persist to SQLite via StateStore
        self.state_store.log_trade(
            symbol=symbol,
            action=action,
            price=price,
            qty=qty,
            strategy=strategy,
            order_type=order_type,
            pnl=pnl,
        )

        logger.info(
            "Trade logged: {} {} {} @ ${:.2f} (strategy={}, pnl={})",
            action, qty, symbol, price, strategy, pnl,
        )

        # Check for large event on SELL trades with realized P&L
        if action == "SELL" and pnl is not None and self.notifier:
            if self.notifier.is_large_event(pnl, self.start_equity):
                direction = "WIN" if pnl > 0 else "LOSS"
                self.notifier.send(
                    f"Large {direction}: {symbol}",
                    f"P&L: ${pnl:+.2f} on {qty} shares of {symbol} ({strategy})",
                    level="warning",
                )

    # ------------------------------------------------------------------
    # P&L calculations
    # ------------------------------------------------------------------

    def get_daily_pnl(self) -> dict:
        """Compute daily P&L relative to session start equity.

        Fetches current account equity from Alpaca and compares against
        the start_equity captured at initialization.

        Returns:
            Dict with keys: start_equity, current_equity, daily_pnl, daily_pnl_pct.
            daily_pnl_pct is a percentage (e.g. 5.0 means +5%).
        """
        account = self.trading_client.get_account()
        current_equity = float(account.equity)

        daily_pnl = current_equity - self.start_equity
        daily_pnl_pct = (daily_pnl / self.start_equity) * 100

        result = {
            "start_equity": self.start_equity,
            "current_equity": current_equity,
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
        }

        logger.info(
            "Daily P&L: ${:.2f} ({:.2f}%) — start=${:.2f}, current=${:.2f}",
            daily_pnl, daily_pnl_pct, self.start_equity, current_equity,
        )

        return result

    def get_total_return(self) -> dict:
        """Compute total return relative to prior day's closing equity.

        Uses account.last_equity (prior day close) as the baseline instead of
        session start_equity. This gives the running return from the previous
        close — the standard way brokerages report total return.

        Returns:
            Dict with keys: total_return, total_return_pct.
            total_return_pct is a percentage (e.g. -2.0 means -2%).
        """
        account = self.trading_client.get_account()
        current_equity = float(account.equity)
        last_equity = float(account.last_equity)

        total_return = current_equity - last_equity
        total_return_pct = (total_return / last_equity) * 100 if last_equity != 0 else 0.0

        result = {
            "total_return": total_return,
            "total_return_pct": total_return_pct,
        }

        logger.info(
            "Total return: ${:.2f} ({:.2f}%) vs prior close ${:.2f}",
            total_return, total_return_pct, last_equity,
        )

        return result
