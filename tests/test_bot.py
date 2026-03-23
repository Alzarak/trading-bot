"""Tests for bot.py: graceful shutdown and market hours guard.

All tests use MagicMock for dependencies — no real API calls, schedulers,
or file I/O.
"""
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_shutdown_flag():
    """Reset _shutdown_requested to False before and after each test."""
    import scripts.bot as bot_module
    bot_module._shutdown_requested = False
    yield
    bot_module._shutdown_requested = False


@pytest.fixture
def mock_trading_client():
    """Mock Alpaca TradingClient."""
    client = MagicMock()
    client.get_all_positions.return_value = []
    return client


@pytest.fixture
def mock_state_store():
    """Mock StateStore."""
    store = MagicMock()
    return store


@pytest.fixture
def mock_scanner():
    """Mock MarketScanner."""
    scanner = MagicMock()
    scanner.is_market_open.return_value = True
    return scanner


@pytest.fixture
def mock_executor():
    """Mock OrderExecutor."""
    return MagicMock()


@pytest.fixture
def mock_tracker():
    """Mock PortfolioTracker."""
    return MagicMock()


@pytest.fixture
def sample_config():
    """Minimal config for bot tests."""
    return {
        "watchlist": ["AAPL", "MSFT"],
        "strategies": [
            {"name": "momentum", "params": {"rsi_period": 14}},
        ],
        "paper_trading": True,
    }


# ---------------------------------------------------------------------------
# TestGracefulShutdown
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    """Verify graceful shutdown closes all positions and marks them in SQLite."""

    def test_shutdown_flag_set(self):
        """_handle_shutdown sets _shutdown_requested to True."""
        import scripts.bot as bot_module

        assert bot_module._shutdown_requested is False
        bot_module._handle_shutdown(2, None)  # SIGINT = 2
        assert bot_module._shutdown_requested is True

    def test_shutdown_closes_positions(self, mock_trading_client, mock_state_store):
        """perform_graceful_shutdown calls close_position for each open position."""
        from scripts.bot import perform_graceful_shutdown

        pos1 = MagicMock()
        pos1.symbol = "AAPL"
        pos2 = MagicMock()
        pos2.symbol = "MSFT"
        mock_trading_client.get_all_positions.return_value = [pos1, pos2]

        perform_graceful_shutdown(mock_trading_client, mock_state_store)

        mock_trading_client.close_position.assert_any_call("AAPL")
        mock_trading_client.close_position.assert_any_call("MSFT")
        assert mock_trading_client.close_position.call_count == 2

    def test_shutdown_marks_closed_in_store(self, mock_trading_client, mock_state_store):
        """perform_graceful_shutdown calls state_store.mark_position_closed for each."""
        from scripts.bot import perform_graceful_shutdown

        pos1 = MagicMock()
        pos1.symbol = "AAPL"
        pos2 = MagicMock()
        pos2.symbol = "GOOGL"
        mock_trading_client.get_all_positions.return_value = [pos1, pos2]

        perform_graceful_shutdown(mock_trading_client, mock_state_store)

        mock_state_store.mark_position_closed.assert_any_call("AAPL")
        mock_state_store.mark_position_closed.assert_any_call("GOOGL")
        assert mock_state_store.mark_position_closed.call_count == 2

    def test_shutdown_continues_on_close_failure(
        self, mock_trading_client, mock_state_store
    ):
        """Failed close_position is caught and logged; shutdown continues for next position."""
        from scripts.bot import perform_graceful_shutdown

        pos1 = MagicMock()
        pos1.symbol = "AAPL"
        pos2 = MagicMock()
        pos2.symbol = "MSFT"
        mock_trading_client.get_all_positions.return_value = [pos1, pos2]

        # AAPL close fails
        mock_trading_client.close_position.side_effect = [
            Exception("Order rejected"),
            None,  # MSFT succeeds
        ]

        # Should not raise — error is caught and logged
        perform_graceful_shutdown(mock_trading_client, mock_state_store)

        # MSFT should still be marked closed even though AAPL failed
        mock_state_store.mark_position_closed.assert_called_with("MSFT")

    def test_shutdown_no_positions(self, mock_trading_client, mock_state_store):
        """perform_graceful_shutdown with no open positions does nothing."""
        from scripts.bot import perform_graceful_shutdown

        mock_trading_client.get_all_positions.return_value = []

        perform_graceful_shutdown(mock_trading_client, mock_state_store)

        mock_trading_client.close_position.assert_not_called()
        mock_state_store.mark_position_closed.assert_not_called()

    def test_shutdown_handles_get_positions_failure(
        self, mock_trading_client, mock_state_store
    ):
        """perform_graceful_shutdown handles failure to fetch positions gracefully."""
        from scripts.bot import perform_graceful_shutdown

        mock_trading_client.get_all_positions.side_effect = Exception("API error")

        # Should not raise
        perform_graceful_shutdown(mock_trading_client, mock_state_store)

        mock_trading_client.close_position.assert_not_called()


# ---------------------------------------------------------------------------
# TestScanAndTrade
# ---------------------------------------------------------------------------

class TestScanAndTrade:
    """Verify scan_and_trade market hours guard and pipeline flow."""

    def test_skips_when_market_closed(
        self,
        mock_scanner,
        mock_executor,
        mock_tracker,
        mock_state_store,
        sample_config,
    ):
        """scan_and_trade returns early when is_market_open() is False."""
        from scripts.bot import scan_and_trade

        mock_scanner.is_market_open.return_value = False
        strategies = sample_config["strategies"]

        scan_and_trade(
            mock_scanner, strategies, mock_executor, mock_tracker,
            mock_state_store, sample_config,
        )

        # scan() should NOT be called — market guard should short-circuit
        mock_scanner.scan.assert_not_called()

    def test_skips_when_shutdown_requested(
        self,
        mock_scanner,
        mock_executor,
        mock_tracker,
        mock_state_store,
        sample_config,
    ):
        """scan_and_trade returns early when _shutdown_requested is True."""
        import scripts.bot as bot_module
        from scripts.bot import scan_and_trade

        bot_module._shutdown_requested = True
        strategies = sample_config["strategies"]

        scan_and_trade(
            mock_scanner, strategies, mock_executor, mock_tracker,
            mock_state_store, sample_config,
        )

        mock_scanner.is_market_open.assert_not_called()
        mock_scanner.scan.assert_not_called()

    def test_skips_empty_df_symbol(
        self,
        mock_scanner,
        mock_executor,
        mock_tracker,
        mock_state_store,
        sample_config,
    ):
        """scan_and_trade skips symbols where scanner returns empty DataFrame."""
        import pandas as pd
        from scripts.bot import scan_and_trade

        mock_scanner.is_market_open.return_value = True
        mock_scanner.scan.return_value = pd.DataFrame()  # empty — skip
        strategies = sample_config["strategies"]

        scan_and_trade(
            mock_scanner, strategies, mock_executor, mock_tracker,
            mock_state_store, sample_config,
        )

        # executor should not be called — no data
        mock_executor.execute_signal.assert_not_called()

    def test_buy_signal_executes_and_logs(
        self,
        mock_scanner,
        mock_executor,
        mock_tracker,
        mock_state_store,
        sample_config,
    ):
        """scan_and_trade executes BUY signal and logs trade."""
        import pandas as pd
        from scripts.bot import scan_and_trade
        from scripts.models import Signal

        # Mock scanner returns minimal DataFrame
        df = pd.DataFrame({
            "close": [150.0],
            "open": [148.0], "high": [151.0], "low": [147.0], "volume": [1000],
        })
        mock_scanner.is_market_open.return_value = True
        mock_scanner.scan.return_value = df

        buy_signal = Signal(
            action="BUY",
            confidence=0.8,
            symbol="AAPL",
            strategy="momentum",
            atr=1.5,
            stop_price=148.5,
            reasoning="RSI oversold",
        )

        mock_order = MagicMock()
        mock_order.qty = 10

        # Patch STRATEGY_REGISTRY to return a strategy that emits our signal
        mock_strategy_instance = MagicMock()
        mock_strategy_instance.generate_signal.return_value = buy_signal
        mock_strategy_class = MagicMock(return_value=mock_strategy_instance)

        mock_executor.execute_signal.return_value = mock_order
        mock_state_store.get_position.return_value = None

        config = {
            "watchlist": ["AAPL"],
            "strategies": [{"name": "test_strategy", "params": {}}],
        }

        with patch("scripts.bot.STRATEGY_REGISTRY", {"test_strategy": mock_strategy_class}):
            scan_and_trade(
                mock_scanner, config["strategies"], mock_executor, mock_tracker,
                mock_state_store, config,
            )

        mock_executor.execute_signal.assert_called_once_with(buy_signal, 150.0)
        mock_state_store.upsert_position.assert_called_once()
        mock_tracker.log_trade.assert_called_once()

    def test_hold_signal_no_execution(
        self,
        mock_scanner,
        mock_executor,
        mock_tracker,
        mock_state_store,
        sample_config,
    ):
        """scan_and_trade does not execute HOLD signals."""
        import pandas as pd
        from scripts.bot import scan_and_trade
        from scripts.models import Signal

        df = pd.DataFrame({
            "close": [150.0],
            "open": [148.0], "high": [151.0], "low": [147.0], "volume": [1000],
        })
        mock_scanner.is_market_open.return_value = True
        mock_scanner.scan.return_value = df

        hold_signal = Signal(
            action="HOLD",
            confidence=0.3,
            symbol="AAPL",
            strategy="momentum",
            atr=1.5,
            stop_price=148.5,
            reasoning="No clear signal",
        )

        mock_strategy_instance = MagicMock()
        mock_strategy_instance.generate_signal.return_value = hold_signal
        mock_strategy_class = MagicMock(return_value=mock_strategy_instance)

        config = {
            "watchlist": ["AAPL"],
            "strategies": [{"name": "test_strategy", "params": {}}],
        }

        with patch("scripts.bot.STRATEGY_REGISTRY", {"test_strategy": mock_strategy_class}):
            scan_and_trade(
                mock_scanner, config["strategies"], mock_executor, mock_tracker,
                mock_state_store, config,
            )

        mock_executor.execute_signal.assert_not_called()

    def test_buy_below_threshold_not_executed(
        self,
        mock_scanner,
        mock_executor,
        mock_tracker,
        mock_state_store,
    ):
        """BUY signal with confidence below threshold should NOT execute."""
        import pandas as pd
        from scripts.bot import scan_and_trade
        from scripts.models import Signal

        df = pd.DataFrame({
            "close": [150.0],
            "open": [148.0], "high": [151.0], "low": [147.0], "volume": [1000],
        })
        mock_scanner.is_market_open.return_value = True
        mock_scanner.scan.return_value = df

        weak_buy = Signal(
            action="BUY",
            confidence=0.4,
            symbol="AAPL",
            strategy="momentum",
            atr=1.5,
            stop_price=148.5,
            reasoning="Weak signal",
        )

        mock_strategy_instance = MagicMock()
        mock_strategy_instance.generate_signal.return_value = weak_buy
        mock_strategy_class = MagicMock(return_value=mock_strategy_instance)

        config = {
            "watchlist": ["AAPL"],
            "strategies": [{"name": "test_strategy", "params": {}}],
            "confidence_threshold": 0.6,
        }

        with patch("scripts.bot.STRATEGY_REGISTRY", {"test_strategy": mock_strategy_class}):
            scan_and_trade(
                mock_scanner, config["strategies"], mock_executor, mock_tracker,
                mock_state_store, config,
            )

        mock_executor.execute_signal.assert_not_called()

    def test_buy_above_threshold_executed(
        self,
        mock_scanner,
        mock_executor,
        mock_tracker,
        mock_state_store,
    ):
        """BUY signal with confidence above threshold should execute."""
        import pandas as pd
        from scripts.bot import scan_and_trade
        from scripts.models import Signal

        df = pd.DataFrame({
            "close": [150.0],
            "open": [148.0], "high": [151.0], "low": [147.0], "volume": [1000],
        })
        mock_scanner.is_market_open.return_value = True
        mock_scanner.scan.return_value = df

        buy_signal = Signal(
            action="BUY",
            confidence=0.5,
            symbol="AAPL",
            strategy="momentum",
            atr=1.5,
            stop_price=148.5,
            reasoning="Moderate signal",
        )

        mock_order = MagicMock()
        mock_order.qty = 10
        mock_executor.execute_signal.return_value = mock_order
        mock_state_store.get_position.return_value = None

        mock_strategy_instance = MagicMock()
        mock_strategy_instance.generate_signal.return_value = buy_signal
        mock_strategy_class = MagicMock(return_value=mock_strategy_instance)

        config = {
            "watchlist": ["AAPL"],
            "strategies": [{"name": "test_strategy", "params": {}}],
            "confidence_threshold": 0.45,
        }

        with patch("scripts.bot.STRATEGY_REGISTRY", {"test_strategy": mock_strategy_class}):
            scan_and_trade(
                mock_scanner, config["strategies"], mock_executor, mock_tracker,
                mock_state_store, config,
            )

        mock_executor.execute_signal.assert_called_once()
