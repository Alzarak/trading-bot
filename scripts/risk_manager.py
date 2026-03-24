"""Risk management module for trading bot.

Enforces circuit breaker, position sizing, PDT tracking, max position limits,
and exponential backoff retry with ghost position prevention.

All methods are safety guardrails — no order can be submitted without passing
through these checks. This module is the safety substrate that Phase 3
(order execution) depends on.
"""
import json
import math
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from scripts.paths import get_data_dir

# Import conditionally to allow testing without alpaca-py installed
try:
    from alpaca.common.exceptions import APIError
except ImportError:
    APIError = Exception


class RiskManager:
    """Enforces all risk rules for the trading bot.

    Args:
        config: Trading configuration dict (from config.json).
        trading_client: Alpaca TradingClient instance (or mock).
    """

    def __init__(self, config: dict, trading_client, state_store=None, notifier=None) -> None:
        self.config = config
        self.client = trading_client
        self.state_store = state_store
        self.notifier = notifier
        self.circuit_breaker_triggered: bool = False
        self.start_equity: float | None = None
        if state_store is None:
            self._pdt_trades: list[dict] = self._load_pdt_trades()
        else:
            self._pdt_trades = []  # Not used when state_store provided

    # ------------------------------------------------------------------
    # Session initialization
    # ------------------------------------------------------------------

    def initialize_session(self) -> None:
        """Capture start equity for the session. Raises RuntimeError if
        a circuit_breaker.flag file exists from a previous triggered session.

        Manual intervention is required to clear the flag before restarting.
        """
        data_dir = get_data_dir()
        flag_file = data_dir / "circuit_breaker.flag"

        if flag_file.exists():
            logger.critical(
                "circuit_breaker.flag found — trading halted. "
                "Remove the flag file to restart: {}", flag_file
            )
            raise RuntimeError(
                f"circuit breaker flag present at {flag_file}. "
                "Remove it manually to restart trading."
            )

        account = self.client.get_account()
        self.start_equity = float(account.equity)
        logger.info("Session initialized. Start equity: ${:.2f}", self.start_equity)

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def check_circuit_breaker(self) -> bool:
        """Return True if daily loss has reached max_daily_loss_pct threshold.

        Once triggered, stays True for the remainder of the session even if
        equity recovers — manual restart is required.
        """
        if self.circuit_breaker_triggered:
            return True

        if self.start_equity is None:
            logger.warning("check_circuit_breaker called before initialize_session — skipping")
            return False

        account = self.client.get_account()
        current_equity = float(account.equity)
        loss_pct = (self.start_equity - current_equity) / self.start_equity * 100

        max_loss = float(self.config.get("max_daily_loss_pct", 2.0))

        if loss_pct >= max_loss:
            logger.critical(
                "Circuit breaker triggered! Loss: {:.2f}% >= threshold {:.2f}%. "
                "Start equity: ${:.2f}, Current equity: ${:.2f}",
                loss_pct, max_loss, self.start_equity, current_equity,
            )
            self._persist_circuit_breaker()
            self.circuit_breaker_triggered = True
            if self.notifier:
                drawdown_pct = abs(loss_pct)
                self.notifier.send(
                    "CIRCUIT BREAKER FIRED",
                    f"Daily drawdown {drawdown_pct:.2f}% exceeded threshold. Trading halted.",
                    level="critical",
                )
            return True

        return False

    def _persist_circuit_breaker(self) -> None:
        """Write circuit_breaker.flag to the trading bot data directory."""
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        flag_file = data_dir / "circuit_breaker.flag"
        flag_file.write_text("triggered")
        logger.info("Circuit breaker flag written to {}", flag_file)

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def _get_total_exposure(self) -> float:
        """Return total market value of all open positions.

        Used to enforce budget_usd as a portfolio-wide cap, not per-trade.
        """
        try:
            positions = self.client.get_all_positions()
            return sum(abs(float(p.market_value)) for p in positions)
        except Exception as exc:
            logger.warning("_get_total_exposure: failed to fetch positions: {}", exc)
            return 0.0

    def calculate_position_size(
        self,
        symbol: str,
        current_price: float,
        size_override_pct: float | None = None,
        budget_override: float | None = None,
    ) -> int | float:
        """Return the number of shares/units to buy, enforcing budget and position caps.

        Args:
            symbol: Ticker symbol (used for logging).
            current_price: Current market price per share/unit.
            size_override_pct: Claude-provided override percentage (claude_decides mode).
                               Clamped to [50%, 150%] of max_position_pct.
            budget_override: Use this budget instead of config budget_usd.
                             Used for crypto when separate_budget is enabled.

        Returns:
            Number of whole shares (int) for stocks, or fractional units (float)
            for crypto. Returns 0 if allocation is insufficient.
        """
        is_crypto = "/" in symbol  # crypto symbols use slash notation (BTC/USD)

        account = self.client.get_account()
        equity = float(account.equity)

        max_pct = float(self.config.get("max_position_pct", 5.0))

        if size_override_pct is not None:
            # Clamp to [50%, 150%] of configured max_position_pct
            lower_bound = max_pct * 0.5
            upper_bound = max_pct * 1.5
            effective_pct = max(lower_bound, min(upper_bound, size_override_pct))
            if effective_pct != size_override_pct:
                logger.warning(
                    "size_override_pct {:.1f}% clamped to {:.1f}% "
                    "(bounds: {:.1f}%–{:.1f}%)",
                    size_override_pct, effective_pct, lower_bound, upper_bound,
                )
        else:
            effective_pct = max_pct

        position_value = equity * (effective_pct / 100.0)

        # Cap at budget (total across ALL positions, not per-trade)
        budget = budget_override if budget_override is not None else float(self.config.get("budget_usd", equity))
        current_exposure = self._get_total_exposure()
        remaining_budget = max(budget - current_exposure, 0.0)

        if remaining_budget <= 0:
            logger.warning(
                "Budget exhausted: ${:.2f} exposure >= ${:.2f} budget — blocking",
                current_exposure, budget,
            )
            return 0

        if position_value > remaining_budget:
            logger.info(
                "Position value ${:.2f} exceeds remaining budget ${:.2f} "
                "(${:.2f} used of ${:.2f}) — capping",
                position_value, remaining_budget, current_exposure, budget,
            )
            position_value = remaining_budget

        # Both stocks and crypto support fractional quantities on Alpaca.
        # Crypto: round to 4 decimal places (e.g. 0.0015 BTC)
        # Stocks: round to 2 decimal places for fractional shares (e.g. 0.33 AAPL)
        precision = 4 if is_crypto else 2
        qty = round(position_value / current_price, precision)
        label = "units" if is_crypto else "shares"

        if qty <= 0:
            logger.warning(
                "Calculated 0 {} for {} at ${:.2f} "
                "(allocation ${:.2f} too small) — skipping",
                label, symbol, current_price, position_value,
            )
            return 0

        logger.info(
            "Position size for {}: {} {} @ ${:.2f} (value ${:.2f}, {:.1f}% of equity)",
            symbol, qty, label, current_price, qty * current_price, effective_pct,
        )
        return qty

    # ------------------------------------------------------------------
    # Position count
    # ------------------------------------------------------------------

    def check_position_count(self) -> bool:
        """Return True if a new position can be opened (under the limit).

        Returns False when open positions >= max_positions, blocking the entry.
        """
        max_positions = int(self.config.get("max_positions", 10))
        positions = self.client.get_all_positions()
        count = len(positions)

        if count >= max_positions:
            logger.warning(
                "Position count {} >= max_positions {} — new entry blocked",
                count, max_positions,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # PDT tracking
    # ------------------------------------------------------------------

    def check_pdt_limit(self, symbol: str, date: str) -> str:
        """Check day trade count over rolling 7-calendar-day window.

        Args:
            symbol: Ticker symbol being considered.
            date: Today's date as 'YYYY-MM-DD' string.

        Returns:
            'allow' (0-1 trades), 'warn' (2 trades), or 'block' (3+ trades).
        """
        today = datetime.strptime(date, "%Y-%m-%d")
        window_start = today - timedelta(days=7)

        if self.state_store is not None:
            count = self.state_store.get_day_trade_count(window_start.strftime("%Y-%m-%d"))
        else:
            count = sum(
                1 for trade in self._pdt_trades
                if datetime.strptime(trade["date"], "%Y-%m-%d") > window_start
            )

        if count >= 3:
            logger.warning(
                "PDT limit reached: {} day trades in rolling 7-day window — blocking {}",
                count, symbol,
            )
            return "block"

        if count == 2:
            logger.warning(
                "PDT warning: {} day trades in rolling 7-day window — approaching limit for {}",
                count, symbol,
            )
            return "warn"

        return "allow"

    def record_day_trade(self, symbol: str, date: str) -> None:
        """Record a day trade in memory and persist to pdt_trades.json.

        Args:
            symbol: Ticker symbol that was day-traded.
            date: Trade date as 'YYYY-MM-DD' string.
        """
        if self.state_store is not None:
            self.state_store.record_day_trade(symbol, date)
            logger.info("Day trade recorded via state_store: {} on {}", symbol, date)
        else:
            entry = {"symbol": symbol, "date": date}
            self._pdt_trades.append(entry)
            self._save_pdt_trades()
            logger.info("Day trade recorded: {} on {}", symbol, date)

    def _load_pdt_trades(self) -> list[dict]:
        """Read existing PDT trades from pdt_trades.json in the data directory."""
        data_dir = get_data_dir()
        json_file = data_dir / "pdt_trades.json"

        if json_file.exists():
            try:
                data = json.loads(json_file.read_text())
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load pdt_trades.json: {}", exc)

        return []

    def _save_pdt_trades(self) -> None:
        """Write _pdt_trades list to pdt_trades.json in the data directory."""
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        json_file = data_dir / "pdt_trades.json"
        json_file.write_text(json.dumps(self._pdt_trades, indent=2))

    # ------------------------------------------------------------------
    # Order submission with retry and ghost position prevention
    # ------------------------------------------------------------------

    def submit_with_retry(self, request, symbol: str) -> object | None:
        """Submit an order with exponential backoff, skipping on 422/403,
        and checking for ghost positions before each retry.

        Retry schedule (seconds between attempts): [1, 2, 4, 8]
        Total: up to 5 attempts (1 initial + 4 retries).

        Args:
            request: Alpaca order request object.
            symbol: Ticker symbol — used for ghost position check.

        Returns:
            Filled Order object on success, None if all attempts fail or order
            is skipped (422, 403, or ghost position detected).
        """
        wait_times = [1, 2, 4, 8]
        max_attempts = 5

        for attempt in range(max_attempts):
            try:
                order = self.client.submit_order(request)
                logger.info("Order submitted successfully on attempt {}", attempt + 1)
                return order

            except Exception as exc:
                # Check for non-retryable status codes
                status_code = getattr(exc, "status_code", None)

                if status_code == 422:
                    logger.error(
                        "Order validation failed (422) on attempt {} for {}: {}. "
                        "Skipping — this will not succeed on retry.",
                        attempt + 1, symbol, exc,
                    )
                    return None

                if status_code == 403:
                    logger.error(
                        "Order auth failed (403) on attempt {} for {}: {}. "
                        "Check API keys.",
                        attempt + 1, symbol, exc,
                    )
                    return None

                logger.warning(
                    "Order attempt {} failed for {}: {}",
                    attempt + 1, symbol, exc,
                )

                # Check for ghost position before retrying
                if attempt < max_attempts - 1:
                    if self._has_open_position(symbol):
                        logger.warning(
                            "Ghost position detected for {} after failed order — "
                            "skipping retry to prevent double submission",
                            symbol,
                        )
                        return None

                    wait = wait_times[attempt] if attempt < len(wait_times) else wait_times[-1]
                    logger.info("Retrying in {}s (attempt {}/{})", wait, attempt + 1, max_attempts)
                    time.sleep(wait)

        logger.error("Order failed after {} attempts for {} — skipping trade", max_attempts, symbol)
        return None

    def _has_open_position(self, symbol: str) -> bool:
        """Return True if a position already exists for symbol."""
        try:
            self.client.get_open_position(symbol)
            return True
        except Exception:
            return False
