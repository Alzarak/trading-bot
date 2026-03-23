"""Order execution module for trading bot.

Wraps all 4 Alpaca order types (market, limit, bracket, trailing stop) with
ATR-based dynamic stop placement. Every order routes through RiskManager safety
checks before reaching the Alpaca API.

All prices are rounded to 2 decimal places — Alpaca rejects fractional prices.
"""
from datetime import datetime, timezone

from loguru import logger

# Import conditionally to allow testing without alpaca-py installed
try:
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import (
        LimitOrderRequest,
        MarketOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
        TrailingStopOrderRequest,
    )
except ImportError:
    # Stubs for environments without alpaca-py (test/CI)
    OrderClass = None  # type: ignore[assignment]
    OrderSide = None  # type: ignore[assignment]
    TimeInForce = None  # type: ignore[assignment]
    LimitOrderRequest = None  # type: ignore[assignment]
    MarketOrderRequest = None  # type: ignore[assignment]
    StopLossRequest = None  # type: ignore[assignment]
    TakeProfitRequest = None  # type: ignore[assignment]
    TrailingStopOrderRequest = None  # type: ignore[assignment]

from scripts.models import Signal


class OrderExecutor:
    """Submits orders to Alpaca through RiskManager safety checks.

    All 4 order types are supported:
    - Market orders (immediate fill)
    - Limit orders (price-controlled entry)
    - Bracket orders (entry + take-profit + stop-loss atomically)
    - Trailing stop orders (dynamic exit)

    Every submission goes through RiskManager.submit_with_retry() — never
    directly to trading_client.

    Args:
        risk_manager: RiskManager instance with submit_with_retry and
                      all risk check methods.
        config: Trading configuration dict (from config.json).
    """

    def __init__(self, risk_manager, config: dict) -> None:
        self.risk_manager = risk_manager
        self.config = config
        self.atr_multiplier: float = float(config.get("atr_multiplier", 1.5))

    # ------------------------------------------------------------------
    # ATR-based price calculations
    # ------------------------------------------------------------------

    def calculate_stop_price(
        self,
        entry_price: float,
        atr: float,
        side: str = "buy",
    ) -> float:
        """Compute ATR-based stop-loss price rounded to 2 decimal places.

        For buy (long) orders: stop is below entry by ATR * multiplier.
        For sell (short) orders: stop is above entry by ATR * multiplier.

        Args:
            entry_price: Expected entry price.
            atr: Average True Range at time of signal.
            side: "buy" for long entries, "sell" for short entries.

        Returns:
            Rounded stop price (2 decimal places).
        """
        stop_distance = atr * self.atr_multiplier
        if side.lower() == "sell":
            return round(entry_price + stop_distance, 2)
        return round(entry_price - stop_distance, 2)

    def calculate_take_profit_price(
        self,
        entry_price: float,
        atr: float,
        risk_reward_ratio: float = 2.0,
    ) -> float:
        """Compute take-profit price using ATR and risk/reward ratio.

        Formula: entry_price + (ATR * multiplier * risk_reward_ratio)

        Args:
            entry_price: Expected entry price.
            atr: Average True Range at time of signal.
            risk_reward_ratio: Multiple of stop distance for take-profit.
                               Default 2.0 means 2:1 reward-to-risk.

        Returns:
            Rounded take-profit price (2 decimal places).
        """
        return round(entry_price + (atr * self.atr_multiplier * risk_reward_ratio), 2)

    # ------------------------------------------------------------------
    # Order type methods
    # ------------------------------------------------------------------

    def submit_market_order(
        self,
        symbol: str,
        qty: int,
        side: "OrderSide",
    ) -> object | None:
        """Submit a market order. Fills immediately at best available price.

        Args:
            symbol: Ticker symbol.
            qty: Number of shares.
            side: OrderSide.BUY or OrderSide.SELL.

        Returns:
            Alpaca Order on success, None on failure.
        """
        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        logger.info(
            "Submitting market order: {} {} shares of {}",
            side, qty, symbol,
        )
        return self.risk_manager.submit_with_retry(request, symbol)

    def submit_limit_order(
        self,
        symbol: str,
        qty: int,
        limit_price: float,
        side: "OrderSide",
    ) -> object | None:
        """Submit a limit order. Fills only at or better than limit_price.

        Args:
            symbol: Ticker symbol.
            qty: Number of shares.
            limit_price: Maximum (buy) or minimum (sell) acceptable fill price.
            side: OrderSide.BUY or OrderSide.SELL.

        Returns:
            Alpaca Order on success, None on failure.
        """
        rounded_limit = round(limit_price, 2)
        request = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
            limit_price=rounded_limit,
        )
        logger.info(
            "Submitting limit order: {} {} shares of {} @ ${:.2f}",
            side, qty, symbol, rounded_limit,
        )
        return self.risk_manager.submit_with_retry(request, symbol)

    def submit_bracket_order(
        self,
        symbol: str,
        qty: int,
        limit_price: float,
        atr: float,
        side: "OrderSide | None" = None,
    ) -> object | None:
        """Submit a bracket order with ATR-based stop-loss and take-profit.

        A bracket order submits 3 legs atomically:
        - Entry (limit)
        - Take-profit (limit above entry)
        - Stop-loss (stop below entry)

        Args:
            symbol: Ticker symbol.
            qty: Number of shares.
            limit_price: Entry limit price.
            atr: Average True Range used to compute stop and take-profit.
            side: OrderSide.BUY by default.

        Returns:
            Alpaca Order on success, None on failure.
        """
        if side is None:
            side = OrderSide.BUY

        rounded_limit = round(limit_price, 2)
        stop_price = self.calculate_stop_price(limit_price, atr)
        take_profit_price = self.calculate_take_profit_price(limit_price, atr)

        request = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
            limit_price=rounded_limit,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit_price),
            stop_loss=StopLossRequest(stop_price=stop_price),
        )
        logger.info(
            "Submitting bracket order: {} {} shares of {} @ ${:.2f} "
            "(stop=${:.2f}, tp=${:.2f})",
            side, qty, symbol, rounded_limit, stop_price, take_profit_price,
        )
        return self.risk_manager.submit_with_retry(request, symbol)

    def submit_trailing_stop(
        self,
        symbol: str,
        qty: int,
        trail_percent: float,
        side: "OrderSide | None" = None,
    ) -> object | None:
        """Submit a trailing stop order. Follows price and triggers on reversal.

        Good-till-cancelled (GTC) so it persists across trading sessions.

        Args:
            symbol: Ticker symbol.
            qty: Number of shares.
            trail_percent: Trailing distance as a percentage of price.
            side: OrderSide.SELL by default (trailing stops exit long positions).

        Returns:
            Alpaca Order on success, None on failure.
        """
        if side is None:
            side = OrderSide.SELL

        rounded_trail = round(trail_percent, 2)
        request = TrailingStopOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC,
            trail_percent=rounded_trail,
        )
        logger.info(
            "Submitting trailing stop: {} {} shares of {} ({:.2f}% trail)",
            side, qty, symbol, rounded_trail,
        )
        return self.risk_manager.submit_with_retry(request, symbol)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute_signal(self, signal: Signal, current_price: float) -> object | None:
        """Execute a trade signal through all risk checks and order submission.

        Risk checks run in this order (each can abort execution):
        1. Circuit breaker — halts all trading when daily loss exceeded
        2. Position count — blocks new entries when at max concurrent positions
        3. PDT limit — blocks entries that would trigger Pattern Day Trader rule
        4. Position size — blocks if calculated shares < 1

        For BUY signals: submits a bracket order with ATR-based stops.
        For SELL signals: submits a market order to close the position immediately.

        Args:
            signal: Trade signal from market scanner or Claude analysis.
            current_price: Current market price for position sizing.

        Returns:
            Alpaca Order on success, None if blocked or failed.
        """
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Circuit breaker
        if self.risk_manager.check_circuit_breaker():
            logger.warning(
                "execute_signal blocked for {} — circuit breaker triggered",
                signal.symbol,
            )
            return None

        # 2. Position count
        if not self.risk_manager.check_position_count():
            logger.warning(
                "execute_signal blocked for {} — at max position count",
                signal.symbol,
            )
            return None

        # 3. PDT limit
        pdt_status = self.risk_manager.check_pdt_limit(signal.symbol, today_str)
        if pdt_status == "block":
            logger.warning(
                "execute_signal blocked for {} — PDT limit reached",
                signal.symbol,
            )
            return None

        # 4. Position sizing
        size_override = getattr(signal, "size_override_pct", None)
        qty = self.risk_manager.calculate_position_size(
            signal.symbol, current_price, size_override
        )
        if qty == 0:
            logger.warning(
                "execute_signal blocked for {} — calculated 0 shares",
                signal.symbol,
            )
            return None

        # Submit appropriate order type based on signal action
        if signal.action == "BUY":
            logger.info(
                "Executing BUY signal for {} (strategy={}, confidence={:.2f}): "
                "{} shares @ ${:.2f}",
                signal.symbol, signal.strategy, signal.confidence, qty, current_price,
            )
            order = self.submit_bracket_order(
                symbol=signal.symbol,
                qty=qty,
                limit_price=current_price,
                atr=signal.atr,
            )
        elif signal.action == "SELL":
            logger.info(
                "Executing SELL signal for {} (strategy={}, confidence={:.2f}): "
                "{} shares @ market",
                signal.symbol, signal.strategy, signal.confidence, qty,
            )
            order = self.submit_market_order(
                symbol=signal.symbol,
                qty=qty,
                side=OrderSide.SELL,
            )
        else:
            logger.debug(
                "Signal action '{}' for {} is not actionable — skipping",
                signal.action, signal.symbol,
            )
            return None

        if order is not None:
            logger.info(
                "Order submitted for {}: {} — reasoning: {}",
                signal.symbol, order, signal.reasoning,
            )
        else:
            logger.warning(
                "Order submission failed for {} after all retries",
                signal.symbol,
            )

        return order
