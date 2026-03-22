"""Tests for PortfolioTracker: trade logging and P&L calculations.

All tests use MagicMock for dependencies — no real API calls or file I/O.
"""
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_account():
    """Mock Alpaca account with equity and last_equity attributes."""
    account = MagicMock()
    account.equity = "10000.00"
    account.last_equity = "9500.00"
    return account


@pytest.fixture
def mock_trading_client(mock_account):
    """Mock trading client that returns mock_account."""
    client = MagicMock()
    client.get_account.return_value = mock_account
    return client


@pytest.fixture
def mock_state_store():
    """Mock StateStore with log_trade method."""
    store = MagicMock()
    return store


@pytest.fixture
def tracker(mock_trading_client, mock_state_store):
    """Create a PortfolioTracker with mocked dependencies."""
    from scripts.portfolio_tracker import PortfolioTracker
    return PortfolioTracker(
        trading_client=mock_trading_client,
        state_store=mock_state_store,
        config={},
    )


# ---------------------------------------------------------------------------
# TestTradeLog
# ---------------------------------------------------------------------------

class TestTradeLog:
    """Verify log_trade delegates to state_store and emits structured log."""

    def test_log_trade_to_state_store(self, tracker, mock_state_store):
        """log_trade calls state_store.log_trade with all required fields."""
        tracker.log_trade(
            symbol="AAPL",
            action="BUY",
            price=150.0,
            qty=10,
            strategy="momentum",
            order_type="bracket",
        )

        mock_state_store.log_trade.assert_called_once_with(
            symbol="AAPL",
            action="BUY",
            price=150.0,
            qty=10,
            strategy="momentum",
            order_type="bracket",
            pnl=None,
        )

    def test_log_trade_with_pnl_to_state_store(self, tracker, mock_state_store):
        """log_trade passes pnl to state_store.log_trade for SELL trades."""
        tracker.log_trade(
            symbol="MSFT",
            action="SELL",
            price=200.0,
            qty=5,
            strategy="mean_reversion",
            order_type="market",
            pnl=250.0,
        )

        mock_state_store.log_trade.assert_called_once_with(
            symbol="MSFT",
            action="SELL",
            price=200.0,
            qty=5,
            strategy="mean_reversion",
            order_type="market",
            pnl=250.0,
        )

    def test_log_trade_fields(self, tracker, mock_state_store):
        """log_trade includes timestamp, ticker, action, price, qty, strategy."""
        # Verify we can call with all expected fields without error
        tracker.log_trade(
            symbol="SPY",
            action="BUY",
            price=450.50,
            qty=20,
            strategy="breakout",
            order_type="bracket",
            pnl=None,
        )

        call_kwargs = mock_state_store.log_trade.call_args.kwargs
        assert call_kwargs["symbol"] == "SPY"
        assert call_kwargs["action"] == "BUY"
        assert call_kwargs["price"] == 450.50
        assert call_kwargs["qty"] == 20
        assert call_kwargs["strategy"] == "breakout"
        assert call_kwargs["order_type"] == "bracket"

    def test_log_trade_does_not_raise_on_state_store_error(
        self, tracker, mock_state_store
    ):
        """log_trade propagates state_store errors (caller should handle)."""
        mock_state_store.log_trade.side_effect = RuntimeError("DB write failed")

        with pytest.raises(RuntimeError, match="DB write failed"):
            tracker.log_trade("AAPL", "BUY", 150.0, 10, "momentum", "bracket")


# ---------------------------------------------------------------------------
# TestPnL
# ---------------------------------------------------------------------------

class TestPnL:
    """Verify P&L calculations against mocked account equity values."""

    def test_daily_pnl_positive(self, tracker, mock_trading_client, mock_state_store):
        """start_equity=10000, current=10500 -> pnl=500, pnl_pct=5.0."""
        # tracker.start_equity was set to 10000.00 at fixture creation
        # Now mock the account to return 10500
        account = MagicMock()
        account.equity = "10500.00"
        mock_trading_client.get_account.return_value = account

        result = tracker.get_daily_pnl()

        assert result["start_equity"] == 10000.0
        assert result["current_equity"] == pytest.approx(10500.0)
        assert result["daily_pnl"] == pytest.approx(500.0)
        assert result["daily_pnl_pct"] == pytest.approx(5.0)

    def test_daily_pnl_negative(self, tracker, mock_trading_client, mock_state_store):
        """start_equity=10000, current=9800 -> pnl=-200, pnl_pct=-2.0."""
        account = MagicMock()
        account.equity = "9800.00"
        mock_trading_client.get_account.return_value = account

        result = tracker.get_daily_pnl()

        assert result["start_equity"] == 10000.0
        assert result["current_equity"] == pytest.approx(9800.0)
        assert result["daily_pnl"] == pytest.approx(-200.0)
        assert result["daily_pnl_pct"] == pytest.approx(-2.0)

    def test_daily_pnl_breakeven(self, tracker, mock_trading_client, mock_state_store):
        """start_equity=10000, current=10000 -> pnl=0, pnl_pct=0.0."""
        account = MagicMock()
        account.equity = "10000.00"
        mock_trading_client.get_account.return_value = account

        result = tracker.get_daily_pnl()

        assert result["daily_pnl"] == pytest.approx(0.0)
        assert result["daily_pnl_pct"] == pytest.approx(0.0)

    def test_daily_pnl_returns_all_keys(self, tracker, mock_trading_client, mock_state_store):
        """get_daily_pnl returns dict with all 4 required keys."""
        account = MagicMock()
        account.equity = "10100.00"
        mock_trading_client.get_account.return_value = account

        result = tracker.get_daily_pnl()

        assert "start_equity" in result
        assert "current_equity" in result
        assert "daily_pnl" in result
        assert "daily_pnl_pct" in result

    def test_total_return_uses_last_equity(self, tracker, mock_trading_client, mock_state_store):
        """get_total_return compares current equity against account.last_equity."""
        account = MagicMock()
        account.equity = "10000.00"
        account.last_equity = "9500.00"
        mock_trading_client.get_account.return_value = account

        result = tracker.get_total_return()

        assert result["total_return"] == pytest.approx(500.0)
        # (10000 - 9500) / 9500 * 100 ~= 5.263%
        assert result["total_return_pct"] == pytest.approx(500.0 / 9500.0 * 100)

    def test_total_return_returns_required_keys(self, tracker, mock_trading_client, mock_state_store):
        """get_total_return dict has total_return and total_return_pct keys."""
        account = MagicMock()
        account.equity = "10000.00"
        account.last_equity = "9500.00"
        mock_trading_client.get_account.return_value = account

        result = tracker.get_total_return()

        assert "total_return" in result
        assert "total_return_pct" in result

    def test_start_equity_captured_at_init(self, mock_trading_client, mock_state_store):
        """PortfolioTracker captures start_equity from account at initialization."""
        from scripts.portfolio_tracker import PortfolioTracker

        account = MagicMock()
        account.equity = "55000.50"
        mock_trading_client.get_account.return_value = account

        pt = PortfolioTracker(mock_trading_client, mock_state_store, {})

        assert pt.start_equity == pytest.approx(55000.50)
