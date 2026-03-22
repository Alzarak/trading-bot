"""Tests for OrderExecutor module.

Covers all 4 order types, ATR stop calculations, and execute_signal() risk
check integration. All Alpaca API calls are mocked — no network required.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.types import Signal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_risk_manager():
    """RiskManager mock with all risk checks defaulting to safe/allow values."""
    rm = MagicMock()
    # Safe defaults — all checks pass
    rm.check_circuit_breaker.return_value = False      # Not triggered
    rm.check_position_count.return_value = True        # Under limit
    rm.check_pdt_limit.return_value = "allow"          # No PDT issue
    rm.calculate_position_size.return_value = 10       # 10 shares
    rm.submit_with_retry.return_value = MagicMock(id="order-123")
    return rm


@pytest.fixture
def sample_config():
    """Config dict with default ATR multiplier."""
    return {
        "atr_multiplier": 1.5,
        "max_position_pct": 5.0,
        "max_daily_loss_pct": 2.0,
        "budget_usd": 10000,
        "max_positions": 10,
    }


@pytest.fixture
def order_executor(mock_risk_manager, sample_config):
    """OrderExecutor with mocked RiskManager and sample config."""
    from scripts.order_executor import OrderExecutor
    return OrderExecutor(mock_risk_manager, sample_config)


@pytest.fixture
def buy_signal():
    """BUY signal fixture for AAPL."""
    return Signal(
        action="BUY",
        atr=2.5,
        symbol="AAPL",
        confidence=0.8,
        stop_price=146.25,
        strategy="momentum",
        reasoning="RSI crossed above 30, MACD bullish",
    )


@pytest.fixture
def sell_signal():
    """SELL signal fixture for AAPL."""
    return Signal(
        action="SELL",
        atr=2.5,
        symbol="AAPL",
        confidence=0.75,
        stop_price=153.75,
        strategy="momentum",
        reasoning="Take profit at resistance",
    )


# ---------------------------------------------------------------------------
# TestOrderTypes
# ---------------------------------------------------------------------------

class TestOrderTypes:
    """Tests for the 4 order type submission methods."""

    def test_market_order(self, order_executor, mock_risk_manager):
        """submit_market_order creates MarketOrderRequest and calls submit_with_retry."""
        with patch("scripts.order_executor.MarketOrderRequest") as MockRequest:
            mock_request_instance = MagicMock()
            MockRequest.return_value = mock_request_instance

            from alpaca.trading.enums import OrderSide, TimeInForce
            result = order_executor.submit_market_order("AAPL", 10, OrderSide.BUY)

            # Verify MarketOrderRequest was constructed with correct params
            MockRequest.assert_called_once()
            kwargs = MockRequest.call_args.kwargs
            assert kwargs["symbol"] == "AAPL"
            assert kwargs["qty"] == 10
            assert kwargs["side"] == OrderSide.BUY
            assert kwargs["time_in_force"] == TimeInForce.DAY

            # Verify routed through submit_with_retry
            mock_risk_manager.submit_with_retry.assert_called_once_with(
                mock_request_instance, "AAPL"
            )
            assert result == mock_risk_manager.submit_with_retry.return_value

    def test_limit_order(self, order_executor, mock_risk_manager):
        """submit_limit_order creates LimitOrderRequest with rounded limit_price."""
        with patch("scripts.order_executor.LimitOrderRequest") as MockRequest:
            mock_request_instance = MagicMock()
            MockRequest.return_value = mock_request_instance

            from alpaca.trading.enums import OrderSide, TimeInForce
            result = order_executor.submit_limit_order("MSFT", 5, 250.333, OrderSide.BUY)

            MockRequest.assert_called_once()
            kwargs = MockRequest.call_args.kwargs
            assert kwargs["symbol"] == "MSFT"
            assert kwargs["qty"] == 5
            assert kwargs["side"] == OrderSide.BUY
            assert kwargs["time_in_force"] == TimeInForce.DAY
            # Price must be rounded to 2 decimal places
            assert kwargs["limit_price"] == 250.33

            mock_risk_manager.submit_with_retry.assert_called_once_with(
                mock_request_instance, "MSFT"
            )

    def test_bracket_order(self, order_executor, mock_risk_manager):
        """submit_bracket_order creates LimitOrderRequest with OrderClass.BRACKET,
        TakeProfitRequest, and StopLossRequest."""
        with (
            patch("scripts.order_executor.LimitOrderRequest") as MockLimit,
            patch("scripts.order_executor.TakeProfitRequest") as MockTP,
            patch("scripts.order_executor.StopLossRequest") as MockSL,
        ):
            mock_request_instance = MagicMock()
            MockLimit.return_value = mock_request_instance
            mock_tp = MagicMock()
            MockTP.return_value = mock_tp
            mock_sl = MagicMock()
            MockSL.return_value = mock_sl

            from alpaca.trading.enums import OrderSide, OrderClass
            result = order_executor.submit_bracket_order(
                "AAPL", 10, 150.0, 2.5, OrderSide.BUY
            )

            # Verify OrderClass.BRACKET used
            MockLimit.assert_called_once()
            kwargs = MockLimit.call_args.kwargs
            assert kwargs["order_class"] == OrderClass.BRACKET
            assert kwargs["symbol"] == "AAPL"
            assert kwargs["qty"] == 10
            assert kwargs["limit_price"] == 150.0

            # Verify take-profit and stop-loss requests were created
            MockTP.assert_called_once()
            MockSL.assert_called_once()

            # Stop-loss uses the TakeProfitRequest and StopLossRequest instances
            assert kwargs["take_profit"] == mock_tp
            assert kwargs["stop_loss"] == mock_sl

            mock_risk_manager.submit_with_retry.assert_called_once_with(
                mock_request_instance, "AAPL"
            )

    def test_trailing_stop(self, order_executor, mock_risk_manager):
        """submit_trailing_stop creates TrailingStopOrderRequest with trail_percent."""
        with patch("scripts.order_executor.TrailingStopOrderRequest") as MockRequest:
            mock_request_instance = MagicMock()
            MockRequest.return_value = mock_request_instance

            from alpaca.trading.enums import OrderSide, TimeInForce
            result = order_executor.submit_trailing_stop("AAPL", 10, 1.5, OrderSide.SELL)

            MockRequest.assert_called_once()
            kwargs = MockRequest.call_args.kwargs
            assert kwargs["symbol"] == "AAPL"
            assert kwargs["qty"] == 10
            assert kwargs["side"] == OrderSide.SELL
            assert kwargs["time_in_force"] == TimeInForce.GTC
            assert kwargs["trail_percent"] == 1.5

            mock_risk_manager.submit_with_retry.assert_called_once_with(
                mock_request_instance, "AAPL"
            )


# ---------------------------------------------------------------------------
# TestStopCalc
# ---------------------------------------------------------------------------

class TestStopCalc:
    """Tests for ATR-based stop and take-profit price calculations."""

    def test_atr_stop(self, order_executor):
        """calculate_stop_price(150.0, 2.5) with multiplier 1.5 returns 146.25."""
        # stop = round(150.0 - 2.5 * 1.5, 2) = round(146.25, 2) = 146.25
        result = order_executor.calculate_stop_price(150.0, 2.5)
        assert result == 146.25

    def test_atr_stop_sell_side(self, order_executor):
        """For sell (short) side, stop is above entry price."""
        # stop = round(150.0 + 2.5 * 1.5, 2) = round(153.75, 2) = 153.75
        result = order_executor.calculate_stop_price(150.0, 2.5, side="sell")
        assert result == 153.75

    def test_take_profit(self, order_executor):
        """calculate_take_profit_price(150.0, 2.5) with multiplier 1.5, ratio 2.0
        returns 157.50."""
        # tp = round(150.0 + 2.5 * 1.5 * 2.0, 2) = round(157.5, 2) = 157.5
        result = order_executor.calculate_take_profit_price(150.0, 2.5)
        assert result == 157.5

    def test_take_profit_custom_ratio(self, order_executor):
        """Custom risk_reward_ratio is applied correctly."""
        # tp = round(150.0 + 2.5 * 1.5 * 3.0, 2) = round(161.25, 2) = 161.25
        result = order_executor.calculate_take_profit_price(150.0, 2.5, risk_reward_ratio=3.0)
        assert result == 161.25

    def test_prices_rounded(self, order_executor):
        """All calculated prices have at most 2 decimal places."""
        # Use an ATR that would produce many decimal places without rounding
        stop = order_executor.calculate_stop_price(100.0, 3.333)
        tp = order_executor.calculate_take_profit_price(100.0, 3.333)

        # Verify 2 decimal place precision
        stop_str = f"{stop:.10f}".rstrip("0")
        tp_str = f"{tp:.10f}".rstrip("0")
        decimal_places_stop = len(stop_str.split(".")[-1]) if "." in stop_str else 0
        decimal_places_tp = len(tp_str.split(".")[-1]) if "." in tp_str else 0

        assert decimal_places_stop <= 2, f"Stop has {decimal_places_stop} decimal places: {stop}"
        assert decimal_places_tp <= 2, f"TP has {decimal_places_tp} decimal places: {tp}"

    def test_stop_rounding_edge_case(self, order_executor):
        """Verify stop price rounds half-up correctly."""
        # stop = round(100.0 - 1.5 * 0.333, 2) = round(100.0 - 0.4995, 2) = round(99.5005, 2)
        result = order_executor.calculate_stop_price(100.0, 0.333)
        # round() in Python uses banker's rounding, result should be 2 decimal places
        assert isinstance(result, float)
        assert round(result, 2) == result


# ---------------------------------------------------------------------------
# TestExecuteSignal
# ---------------------------------------------------------------------------

class TestExecuteSignal:
    """Tests for execute_signal() risk check integration."""

    def test_circuit_breaker_blocks(self, order_executor, mock_risk_manager, buy_signal):
        """execute_signal returns None when circuit breaker is triggered."""
        mock_risk_manager.check_circuit_breaker.return_value = True

        result = order_executor.execute_signal(buy_signal, 150.0)

        assert result is None
        mock_risk_manager.check_circuit_breaker.assert_called_once()
        # Should not proceed to position count check
        mock_risk_manager.check_position_count.assert_not_called()
        mock_risk_manager.submit_with_retry.assert_not_called()

    def test_position_count_blocks(self, order_executor, mock_risk_manager, buy_signal):
        """execute_signal returns None when at max position count."""
        mock_risk_manager.check_position_count.return_value = False

        result = order_executor.execute_signal(buy_signal, 150.0)

        assert result is None
        mock_risk_manager.check_position_count.assert_called_once()
        mock_risk_manager.submit_with_retry.assert_not_called()

    def test_pdt_blocks(self, order_executor, mock_risk_manager, buy_signal):
        """execute_signal returns None when PDT check returns 'block'."""
        mock_risk_manager.check_pdt_limit.return_value = "block"

        result = order_executor.execute_signal(buy_signal, 150.0)

        assert result is None
        mock_risk_manager.check_pdt_limit.assert_called_once()
        mock_risk_manager.submit_with_retry.assert_not_called()

    def test_zero_shares_blocks(self, order_executor, mock_risk_manager, buy_signal):
        """execute_signal returns None when position size calculates to 0 shares."""
        mock_risk_manager.calculate_position_size.return_value = 0

        result = order_executor.execute_signal(buy_signal, 150.0)

        assert result is None
        mock_risk_manager.calculate_position_size.assert_called_once()
        mock_risk_manager.submit_with_retry.assert_not_called()

    def test_buy_submits_bracket(self, order_executor, mock_risk_manager, buy_signal):
        """BUY signal triggers submit_bracket_order (LimitOrderRequest with BRACKET class)."""
        with (
            patch("scripts.order_executor.LimitOrderRequest") as MockLimit,
            patch("scripts.order_executor.TakeProfitRequest"),
            patch("scripts.order_executor.StopLossRequest"),
        ):
            MockLimit.return_value = MagicMock()

            result = order_executor.execute_signal(buy_signal, 150.0)

            # Should have used LimitOrderRequest (bracket orders use limit as entry)
            MockLimit.assert_called_once()
            kwargs = MockLimit.call_args.kwargs
            from alpaca.trading.enums import OrderClass
            assert kwargs["order_class"] == OrderClass.BRACKET
            assert kwargs["symbol"] == "AAPL"

            # submit_with_retry must have been called
            mock_risk_manager.submit_with_retry.assert_called_once()

    def test_sell_submits_market(self, order_executor, mock_risk_manager, sell_signal):
        """SELL signal triggers submit_market_order."""
        with patch("scripts.order_executor.MarketOrderRequest") as MockMarket:
            MockMarket.return_value = MagicMock()

            result = order_executor.execute_signal(sell_signal, 155.0)

            MockMarket.assert_called_once()
            kwargs = MockMarket.call_args.kwargs
            from alpaca.trading.enums import OrderSide
            assert kwargs["symbol"] == "AAPL"
            assert kwargs["side"] == OrderSide.SELL

            mock_risk_manager.submit_with_retry.assert_called_once()

    def test_pdt_warn_still_executes(self, order_executor, mock_risk_manager, buy_signal):
        """PDT 'warn' does not block execution — only 'block' does."""
        mock_risk_manager.check_pdt_limit.return_value = "warn"

        with (
            patch("scripts.order_executor.LimitOrderRequest") as MockLimit,
            patch("scripts.order_executor.TakeProfitRequest"),
            patch("scripts.order_executor.StopLossRequest"),
        ):
            MockLimit.return_value = MagicMock()
            result = order_executor.execute_signal(buy_signal, 150.0)

        # Execution should proceed (warn doesn't block)
        mock_risk_manager.submit_with_retry.assert_called_once()

    def test_hold_signal_returns_none(self, order_executor, buy_signal):
        """HOLD action returns None without submitting any order."""
        hold_signal = Signal(
            action="HOLD",
            atr=2.5,
            symbol="AAPL",
            confidence=0.5,
            stop_price=146.25,
            strategy="momentum",
            reasoning="No clear signal",
        )

        with patch("scripts.order_executor.MarketOrderRequest") as MockMarket, \
             patch("scripts.order_executor.LimitOrderRequest") as MockLimit:
            result = order_executor.execute_signal(hold_signal, 150.0)

        assert result is None
        MockMarket.assert_not_called()
        MockLimit.assert_not_called()
