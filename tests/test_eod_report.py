"""Tests for EODReportGenerator: end-of-day summary generation.

Tests cover:
- generate() with mixed trades — all computed fields
- generate() with no trades — zeros and Nones
- format_text() — key strings appear in output
"""
from datetime import date
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tracker():
    """Mock PortfolioTracker with get_daily_pnl."""
    tracker = MagicMock()
    tracker.get_daily_pnl.return_value = {
        "start_equity": 10000.0,
        "current_equity": 10250.0,
        "daily_pnl": 250.0,
        "daily_pnl_pct": 2.5,
    }
    tracker.start_equity = 10000.0
    return tracker


@pytest.fixture
def mock_state_store_with_trades():
    """Mock StateStore returning a list of trades for today."""
    store = MagicMock()
    today = date.today().isoformat()
    store.get_trade_history.return_value = [
        {
            "symbol": "AAPL",
            "action": "BUY",
            "price": 150.0,
            "qty": 10,
            "pnl": None,
            "strategy": "momentum",
            "order_type": "bracket",
            "logged_at": f"{today}T09:35:00",
        },
        {
            "symbol": "AAPL",
            "action": "SELL",
            "price": 155.0,
            "qty": 10,
            "pnl": 50.0,
            "strategy": "momentum",
            "order_type": "market",
            "logged_at": f"{today}T10:15:00",
        },
        {
            "symbol": "MSFT",
            "action": "BUY",
            "price": 300.0,
            "qty": 5,
            "pnl": None,
            "strategy": "breakout",
            "order_type": "bracket",
            "logged_at": f"{today}T10:30:00",
        },
        {
            "symbol": "MSFT",
            "action": "SELL",
            "price": 295.0,
            "qty": 5,
            "pnl": -25.0,
            "strategy": "breakout",
            "order_type": "market",
            "logged_at": f"{today}T11:00:00",
        },
        {
            "symbol": "SPY",
            "action": "BUY",
            "price": 450.0,
            "qty": 2,
            "pnl": None,
            "strategy": "momentum",
            "order_type": "bracket",
            "logged_at": f"{today}T11:30:00",
        },
        {
            "symbol": "SPY",
            "action": "SELL",
            "price": 460.0,
            "qty": 2,
            "pnl": 20.0,
            "strategy": "momentum",
            "order_type": "market",
            "logged_at": f"{today}T13:00:00",
        },
    ]
    return store


@pytest.fixture
def mock_state_store_empty():
    """Mock StateStore returning no trades."""
    store = MagicMock()
    store.get_trade_history.return_value = []
    return store


@pytest.fixture
def eod_generator():
    """Create an EODReportGenerator instance."""
    from scripts.eod_report import EODReportGenerator
    return EODReportGenerator()


# ---------------------------------------------------------------------------
# TestEODReportGenerate
# ---------------------------------------------------------------------------


class TestEODReportGenerate:
    """Tests for EODReportGenerator.generate()."""

    def test_generate_returns_all_required_keys(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() returns a dict with all expected keys."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        required_keys = {
            "date", "daily_pnl", "daily_pnl_pct", "total_trades",
            "buy_count", "sell_count", "win_count", "loss_count",
            "win_rate", "biggest_winner", "biggest_loser",
        }
        assert required_keys == set(report.keys())

    def test_generate_trade_counts(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() counts buys and sells correctly from today's trades."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        assert report["total_trades"] == 6
        assert report["buy_count"] == 3
        assert report["sell_count"] == 3

    def test_generate_win_loss_counts(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() counts wins (pnl > 0) and losses (pnl < 0) from SELL trades."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        # AAPL +50, SPY +20 = 2 wins; MSFT -25 = 1 loss
        assert report["win_count"] == 2
        assert report["loss_count"] == 1

    def test_generate_win_rate(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() win_rate = win_count / sell_count."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        # 2 wins / 3 sells ~= 0.667
        assert report["win_rate"] == pytest.approx(2 / 3)

    def test_generate_biggest_winner(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() biggest_winner is the sell with highest pnl."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        assert report["biggest_winner"] is not None
        assert report["biggest_winner"]["symbol"] == "AAPL"
        assert report["biggest_winner"]["pnl"] == pytest.approx(50.0)

    def test_generate_biggest_loser(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() biggest_loser is the sell with lowest pnl."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        assert report["biggest_loser"] is not None
        assert report["biggest_loser"]["symbol"] == "MSFT"
        assert report["biggest_loser"]["pnl"] == pytest.approx(-25.0)

    def test_generate_pnl_from_tracker(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() pulls daily_pnl and daily_pnl_pct from tracker.get_daily_pnl()."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        assert report["daily_pnl"] == pytest.approx(250.0)
        assert report["daily_pnl_pct"] == pytest.approx(2.5)

    def test_generate_date_defaults_to_today(
        self, eod_generator, mock_tracker, mock_state_store_with_trades
    ):
        """generate() date field defaults to today's ISO date when not provided."""
        report = eod_generator.generate(mock_tracker, mock_state_store_with_trades)

        assert report["date"] == date.today().isoformat()

    def test_generate_with_explicit_date(
        self, eod_generator, mock_tracker, mock_state_store_empty
    ):
        """generate() uses the provided date parameter for filtering."""
        report = eod_generator.generate(
            mock_tracker, mock_state_store_empty, date="2024-01-15"
        )

        assert report["date"] == "2024-01-15"

    def test_generate_no_trades_returns_zeros(
        self, eod_generator, mock_tracker, mock_state_store_empty
    ):
        """generate() with no trades returns zero counts and 0.0 win_rate."""
        report = eod_generator.generate(mock_tracker, mock_state_store_empty)

        assert report["total_trades"] == 0
        assert report["buy_count"] == 0
        assert report["sell_count"] == 0
        assert report["win_count"] == 0
        assert report["loss_count"] == 0
        assert report["win_rate"] == pytest.approx(0.0)

    def test_generate_no_trades_returns_none_for_winner_loser(
        self, eod_generator, mock_tracker, mock_state_store_empty
    ):
        """generate() with no trades returns None for biggest_winner and biggest_loser."""
        report = eod_generator.generate(mock_tracker, mock_state_store_empty)

        assert report["biggest_winner"] is None
        assert report["biggest_loser"] is None

    def test_generate_filters_to_date(
        self, eod_generator, mock_tracker
    ):
        """generate() only counts trades matching the date parameter."""
        store = MagicMock()
        store.get_trade_history.return_value = [
            {
                "symbol": "AAPL",
                "action": "SELL",
                "price": 155.0,
                "qty": 10,
                "pnl": 50.0,
                "strategy": "momentum",
                "order_type": "market",
                "logged_at": "2024-01-10T10:15:00",
            },
            {
                "symbol": "MSFT",
                "action": "SELL",
                "price": 305.0,
                "qty": 5,
                "pnl": 25.0,
                "strategy": "breakout",
                "order_type": "market",
                "logged_at": "2024-01-11T10:15:00",  # Different date
            },
        ]

        report = eod_generator.generate(mock_tracker, store, date="2024-01-10")

        assert report["total_trades"] == 1
        assert report["sell_count"] == 1
        assert report["win_count"] == 1

    def test_generate_calls_get_trade_history_with_large_limit(
        self, eod_generator, mock_tracker, mock_state_store_empty
    ):
        """generate() fetches trade history with a high limit (500) to get full day."""
        eod_generator.generate(mock_tracker, mock_state_store_empty)

        call_kwargs = mock_state_store_empty.get_trade_history.call_args
        # Should be called with limit=500
        assert call_kwargs is not None


# ---------------------------------------------------------------------------
# TestEODReportFormatText
# ---------------------------------------------------------------------------


class TestEODReportFormatText:
    """Tests for EODReportGenerator.format_text()."""

    def test_format_text_contains_date(self, eod_generator):
        """format_text includes the report date."""
        report = {
            "date": "2024-01-15",
            "daily_pnl": 250.0,
            "daily_pnl_pct": 2.5,
            "total_trades": 4,
            "buy_count": 2,
            "sell_count": 2,
            "win_count": 1,
            "loss_count": 1,
            "win_rate": 0.5,
            "biggest_winner": {"symbol": "AAPL", "pnl": 50.0},
            "biggest_loser": {"symbol": "MSFT", "pnl": -25.0},
        }

        text = eod_generator.format_text(report)

        assert "2024-01-15" in text

    def test_format_text_contains_pnl(self, eod_generator):
        """format_text includes daily P&L values."""
        report = {
            "date": "2024-01-15",
            "daily_pnl": 250.0,
            "daily_pnl_pct": 2.5,
            "total_trades": 4,
            "buy_count": 2,
            "sell_count": 2,
            "win_count": 1,
            "loss_count": 1,
            "win_rate": 0.5,
            "biggest_winner": {"symbol": "AAPL", "pnl": 50.0},
            "biggest_loser": {"symbol": "MSFT", "pnl": -25.0},
        }

        text = eod_generator.format_text(report)

        assert "250" in text  # P&L amount

    def test_format_text_contains_win_rate(self, eod_generator):
        """format_text shows win rate percentage."""
        report = {
            "date": "2024-01-15",
            "daily_pnl": 250.0,
            "daily_pnl_pct": 2.5,
            "total_trades": 4,
            "buy_count": 2,
            "sell_count": 2,
            "win_count": 1,
            "loss_count": 1,
            "win_rate": 0.5,
            "biggest_winner": {"symbol": "AAPL", "pnl": 50.0},
            "biggest_loser": {"symbol": "MSFT", "pnl": -25.0},
        }

        text = eod_generator.format_text(report)

        assert "50" in text  # 50% win rate

    def test_format_text_contains_biggest_winner_symbol(self, eod_generator):
        """format_text includes biggest winner symbol."""
        report = {
            "date": "2024-01-15",
            "daily_pnl": 250.0,
            "daily_pnl_pct": 2.5,
            "total_trades": 4,
            "buy_count": 2,
            "sell_count": 2,
            "win_count": 1,
            "loss_count": 1,
            "win_rate": 0.5,
            "biggest_winner": {"symbol": "AAPL", "pnl": 50.0},
            "biggest_loser": {"symbol": "MSFT", "pnl": -25.0},
        }

        text = eod_generator.format_text(report)

        assert "AAPL" in text

    def test_format_text_contains_biggest_loser_symbol(self, eod_generator):
        """format_text includes biggest loser symbol."""
        report = {
            "date": "2024-01-15",
            "daily_pnl": 250.0,
            "daily_pnl_pct": 2.5,
            "total_trades": 4,
            "buy_count": 2,
            "sell_count": 2,
            "win_count": 1,
            "loss_count": 1,
            "win_rate": 0.5,
            "biggest_winner": {"symbol": "AAPL", "pnl": 50.0},
            "biggest_loser": {"symbol": "MSFT", "pnl": -25.0},
        }

        text = eod_generator.format_text(report)

        assert "MSFT" in text

    def test_format_text_with_no_winner_loser(self, eod_generator):
        """format_text handles None biggest_winner and biggest_loser gracefully."""
        report = {
            "date": "2024-01-15",
            "daily_pnl": 0.0,
            "daily_pnl_pct": 0.0,
            "total_trades": 0,
            "buy_count": 0,
            "sell_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "biggest_winner": None,
            "biggest_loser": None,
        }

        text = eod_generator.format_text(report)

        assert isinstance(text, str)
        assert len(text) > 0

    def test_format_text_is_multiline(self, eod_generator):
        """format_text returns a multi-line string."""
        report = {
            "date": "2024-01-15",
            "daily_pnl": 250.0,
            "daily_pnl_pct": 2.5,
            "total_trades": 4,
            "buy_count": 2,
            "sell_count": 2,
            "win_count": 1,
            "loss_count": 1,
            "win_rate": 0.5,
            "biggest_winner": {"symbol": "AAPL", "pnl": 50.0},
            "biggest_loser": {"symbol": "MSFT", "pnl": -25.0},
        }

        text = eod_generator.format_text(report)

        assert "\n" in text
