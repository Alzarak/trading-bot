"""Unit tests for StateStore — SQLite persistence and crash recovery.

Covers:
  - Schema creation and WAL mode
  - Positions CRUD (upsert, read, close, replace)
  - Orders CRUD (record, status update)
  - Trade log (insert, ordering)
  - Day trades (record, count, window filtering)
  - Crash recovery reconciliation (3 cases + summary)
  - PDT JSON migration (roundtrip + no-op when file absent)
"""
import json
from unittest.mock import MagicMock

import pytest

from scripts.state_store import StateStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state_store(tmp_path):
    """Create a StateStore backed by a temp SQLite database.

    Yields the store; closes on teardown.
    """
    store = StateStore(tmp_path / "test.db")
    yield store
    store.close()


def _mock_alpaca_position(symbol: str, qty: int, avg_entry_price: float) -> MagicMock:
    """Return a MagicMock that looks like an alpaca-py Position object."""
    pos = MagicMock()
    pos.symbol = symbol
    pos.qty = str(qty)        # alpaca-py returns qty as string
    pos.avg_entry_price = str(avg_entry_price)
    return pos


# ---------------------------------------------------------------------------
# TestSchema
# ---------------------------------------------------------------------------


class TestSchema:
    """Verify that all 4 tables are created and WAL mode is active."""

    def test_tables_created(self, state_store):
        """StateStore init creates all 4 required tables."""
        cursor = state_store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "positions" in tables, "positions table missing"
        assert "orders" in tables, "orders table missing"
        assert "trade_log" in tables, "trade_log table missing"
        assert "day_trades" in tables, "day_trades table missing"

    def test_wal_mode(self, state_store):
        """journal_mode is set to WAL on the connection."""
        cursor = state_store.conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode == "wal", f"Expected WAL mode, got {mode}"


# ---------------------------------------------------------------------------
# TestPositions
# ---------------------------------------------------------------------------


class TestPositions:
    """Test positions table CRUD operations."""

    def test_upsert_and_read(self, state_store):
        """Insert a position and read it back with correct field values."""
        state_store.upsert_position(
            symbol="AAPL",
            qty=10,
            entry_price=150.0,
            stop_price=145.0,
            strategy="momentum",
            opened_at="2026-01-01T09:30:00",
            alpaca_order_id="order-123",
        )
        pos = state_store.get_position("AAPL")
        assert pos is not None
        assert pos["symbol"] == "AAPL"
        assert pos["qty"] == 10
        assert pos["entry_price"] == 150.0
        assert pos["stop_price"] == 145.0
        assert pos["strategy"] == "momentum"
        assert pos["opened_at"] == "2026-01-01T09:30:00"
        assert pos["alpaca_order_id"] == "order-123"
        assert pos["status"] == "open"

    def test_mark_closed(self, state_store):
        """mark_position_closed sets status to 'closed'."""
        state_store.upsert_position("MSFT", 5, 300.0, 290.0, "breakout")
        state_store.mark_position_closed("MSFT")

        pos = state_store.get_position("MSFT")
        assert pos["status"] == "closed"

    def test_mark_closed_not_in_open_positions(self, state_store):
        """A closed position does not appear in get_open_positions."""
        state_store.upsert_position("SPY", 2, 500.0, 490.0, "momentum")
        state_store.mark_position_closed("SPY")

        open_pos = state_store.get_open_positions()
        assert "SPY" not in open_pos

    def test_upsert_replaces(self, state_store):
        """Upserting the same symbol twice results in one row with updated values."""
        state_store.upsert_position("AAPL", 10, 150.0, 145.0, "momentum")
        state_store.upsert_position("AAPL", 20, 155.0, 148.0, "breakout")

        # Only one row in the table
        cursor = state_store.conn.execute(
            "SELECT COUNT(*) FROM positions WHERE symbol='AAPL'"
        )
        assert cursor.fetchone()[0] == 1

        pos = state_store.get_position("AAPL")
        assert pos["qty"] == 20
        assert pos["entry_price"] == 155.0
        assert pos["strategy"] == "breakout"

    def test_get_open_positions_returns_dict(self, state_store):
        """get_open_positions returns a dict keyed by symbol."""
        state_store.upsert_position("AAPL", 10, 150.0, 145.0, "momentum")
        state_store.upsert_position("GOOG", 3, 180.0, 175.0, "breakout")

        open_pos = state_store.get_open_positions()
        assert "AAPL" in open_pos
        assert "GOOG" in open_pos

    def test_get_position_missing_returns_none(self, state_store):
        """get_position returns None when the symbol is not in the table."""
        assert state_store.get_position("NONEXISTENT") is None


# ---------------------------------------------------------------------------
# TestOrders
# ---------------------------------------------------------------------------


class TestOrders:
    """Test orders table record and status update operations."""

    def test_record_and_read(self, state_store):
        """record_order inserts an order; get_order returns it with correct fields."""
        state_store.record_order(
            client_order_id="uuid-1",
            alpaca_order_id="alpaca-abc",
            symbol="AAPL",
            side="buy",
            order_type="market",
            qty=10,
            status="pending",
            limit_price=None,
            stop_price=None,
        )
        order = state_store.get_order("uuid-1")
        assert order is not None
        assert order["client_order_id"] == "uuid-1"
        assert order["alpaca_order_id"] == "alpaca-abc"
        assert order["symbol"] == "AAPL"
        assert order["side"] == "buy"
        assert order["order_type"] == "market"
        assert order["qty"] == 10
        assert order["status"] == "pending"
        assert order["filled_at"] is None

    def test_update_status(self, state_store):
        """update_order_status changes status and sets filled_at."""
        state_store.record_order(
            client_order_id="uuid-2",
            alpaca_order_id="alpaca-def",
            symbol="MSFT",
            side="sell",
            order_type="limit",
            qty=5,
            status="pending",
            limit_price=305.0,
        )
        state_store.update_order_status(
            "uuid-2", status="filled", filled_at="2026-01-01T10:00:00"
        )
        order = state_store.get_order("uuid-2")
        assert order["status"] == "filled"
        assert order["filled_at"] == "2026-01-01T10:00:00"

    def test_get_order_missing_returns_none(self, state_store):
        """get_order returns None for a non-existent client_order_id."""
        assert state_store.get_order("does-not-exist") is None


# ---------------------------------------------------------------------------
# TestTradeLog
# ---------------------------------------------------------------------------


class TestTradeLog:
    """Test trade_log insertion and retrieval ordering."""

    def test_log_and_history(self, state_store):
        """Logging 3 trades; get_trade_history returns them newest-first."""
        state_store.log_trade("AAPL", "buy", 150.0, 10, "momentum", "market")
        state_store.log_trade("AAPL", "sell", 155.0, 10, "momentum", "market", pnl=50.0)
        state_store.log_trade("MSFT", "buy", 300.0, 5, "breakout", "limit")

        history = state_store.get_trade_history()
        assert len(history) == 3

        # Most recent first — MSFT buy was last inserted
        assert history[0]["symbol"] == "MSFT"
        assert history[0]["action"] == "buy"

    def test_history_limit(self, state_store):
        """get_trade_history respects the limit parameter."""
        for i in range(5):
            state_store.log_trade(
                f"SYM{i}", "buy", 100.0 + i, 1, "momentum", "market"
            )
        history = state_store.get_trade_history(limit=2)
        assert len(history) == 2

    def test_log_trade_pnl_optional(self, state_store):
        """log_trade with no pnl stores None."""
        state_store.log_trade("AAPL", "buy", 150.0, 10, "momentum", "market")
        history = state_store.get_trade_history(limit=1)
        assert history[0]["pnl"] is None


# ---------------------------------------------------------------------------
# TestDayTrades
# ---------------------------------------------------------------------------


class TestDayTrades:
    """Test day_trades table for PDT tracking."""

    def test_record_and_count(self, state_store):
        """Recording 2 day trades; count within window returns 2."""
        state_store.record_day_trade("AAPL", "2026-01-10")
        state_store.record_day_trade("MSFT", "2026-01-11")

        count = state_store.get_day_trade_count(window_start="2026-01-09")
        assert count == 2

    def test_window_filter(self, state_store):
        """Only trades strictly after window_start are counted."""
        state_store.record_day_trade("AAPL", "2026-01-01")  # outside window
        state_store.record_day_trade("MSFT", "2026-01-10")  # inside window
        state_store.record_day_trade("GOOG", "2026-01-11")  # inside window

        count = state_store.get_day_trade_count(window_start="2026-01-05")
        assert count == 2, f"Expected 2 but got {count}"

    def test_window_boundary_exclusive(self, state_store):
        """Trade on window_start date itself is NOT counted (exclusive bound)."""
        state_store.record_day_trade("AAPL", "2026-01-05")
        count = state_store.get_day_trade_count(window_start="2026-01-05")
        assert count == 0

    def test_get_day_trades_list(self, state_store):
        """get_day_trades returns a list of dict entries."""
        state_store.record_day_trade("AAPL", "2026-01-10")
        trades = state_store.get_day_trades(window_start="2026-01-09")
        assert len(trades) == 1
        assert trades[0]["symbol"] == "AAPL"
        assert trades[0]["date"] == "2026-01-10"


# ---------------------------------------------------------------------------
# TestCrashRecovery
# ---------------------------------------------------------------------------


class TestCrashRecovery:
    """Test reconcile_positions against all 3 reconciliation cases."""

    def test_alpaca_position_not_in_sqlite(self, state_store):
        """Case 1: Alpaca has AAPL, SQLite empty -> AAPL inserted."""
        trading_client = MagicMock()
        trading_client.get_all_positions.return_value = [
            _mock_alpaca_position("AAPL", 10, 150.0)
        ]

        state_store.reconcile_positions(trading_client)

        pos = state_store.get_position("AAPL")
        assert pos is not None
        assert pos["qty"] == 10
        assert pos["entry_price"] == 150.0
        assert pos["strategy"] == "unknown_post_crash"
        assert pos["status"] == "open"

    def test_sqlite_position_not_in_alpaca(self, state_store):
        """Case 2: SQLite has AAPL open, Alpaca returns empty -> AAPL marked closed."""
        state_store.upsert_position("AAPL", 10, 150.0, 145.0, "momentum")

        trading_client = MagicMock()
        trading_client.get_all_positions.return_value = []

        state_store.reconcile_positions(trading_client)

        pos = state_store.get_position("AAPL")
        assert pos["status"] == "closed"

    def test_both_exist_updates(self, state_store):
        """Case 3: Both have AAPL, Alpaca has different qty -> qty updated from Alpaca."""
        state_store.upsert_position("AAPL", 10, 150.0, 145.0, "momentum")

        trading_client = MagicMock()
        # Alpaca shows different qty and entry_price (e.g. averaged into position)
        trading_client.get_all_positions.return_value = [
            _mock_alpaca_position("AAPL", 15, 152.0)
        ]

        state_store.reconcile_positions(trading_client)

        pos = state_store.get_position("AAPL")
        assert pos["qty"] == 15
        assert pos["entry_price"] == 152.0
        # stop_price and strategy preserved from SQLite
        assert pos["stop_price"] == 145.0
        assert pos["strategy"] == "momentum"

    def test_reconcile_returns_summary(self, state_store):
        """reconcile_positions returns a dict with inserted/closed/updated lists."""
        # Setup: one open in SQLite (will be closed), one new in Alpaca (will be inserted)
        state_store.upsert_position("MSFT", 5, 300.0, 290.0, "breakout")

        trading_client = MagicMock()
        trading_client.get_all_positions.return_value = [
            _mock_alpaca_position("AAPL", 10, 150.0)
        ]

        summary = state_store.reconcile_positions(trading_client)

        assert "inserted" in summary
        assert "closed" in summary
        assert "updated" in summary
        assert isinstance(summary["inserted"], list)
        assert isinstance(summary["closed"], list)
        assert isinstance(summary["updated"], list)
        assert "AAPL" in summary["inserted"]
        assert "MSFT" in summary["closed"]

    def test_all_three_cases_simultaneously(self, state_store):
        """All 3 cases handled in a single reconcile call."""
        # Case 2: will be stale (in SQLite, not Alpaca)
        state_store.upsert_position("STALE", 3, 100.0, 95.0, "momentum")
        # Case 3: will be updated (in both)
        state_store.upsert_position("BOTH", 5, 200.0, 190.0, "breakout")

        trading_client = MagicMock()
        trading_client.get_all_positions.return_value = [
            _mock_alpaca_position("NEW", 2, 50.0),    # Case 1: insert
            _mock_alpaca_position("BOTH", 8, 205.0),  # Case 3: update
        ]

        summary = state_store.reconcile_positions(trading_client)

        assert "NEW" in summary["inserted"]
        assert "STALE" in summary["closed"]
        assert "BOTH" in summary["updated"]


# ---------------------------------------------------------------------------
# TestMigration
# ---------------------------------------------------------------------------


class TestMigration:
    """Test pdt_trades.json -> SQLite migration."""

    def test_pdt_json_migrated(self, tmp_path):
        """Existing pdt_trades.json entries land in day_trades table; file renamed."""
        pdt_data = [
            {"symbol": "AAPL", "date": "2026-01-10"},
            {"symbol": "MSFT", "date": "2026-01-11"},
        ]
        json_file = tmp_path / "pdt_trades.json"
        json_file.write_text(json.dumps(pdt_data))

        store = StateStore(tmp_path / "test.db")
        try:
            # Original file renamed
            assert not json_file.exists(), "Original pdt_trades.json should be renamed"
            migrated = tmp_path / "pdt_trades.json.migrated"
            assert migrated.exists(), "pdt_trades.json.migrated should exist"

            # Entries in the day_trades table
            trades = store.get_day_trades(window_start="2026-01-09")
            symbols = [t["symbol"] for t in trades]
            assert "AAPL" in symbols
            assert "MSFT" in symbols
        finally:
            store.close()

    def test_no_json_no_error(self, tmp_path):
        """StateStore init without pdt_trades.json raises no error."""
        # Verify json file does not exist
        assert not (tmp_path / "pdt_trades.json").exists()

        store = StateStore(tmp_path / "test.db")
        try:
            # Should be zero day trades — migration was a no-op
            count = store.get_day_trade_count(window_start="2000-01-01")
            assert count == 0
        finally:
            store.close()

    def test_migration_idempotent(self, tmp_path):
        """After migration, a second StateStore init does not re-migrate."""
        pdt_data = [{"symbol": "AAPL", "date": "2026-01-10"}]
        json_file = tmp_path / "pdt_trades.json"
        json_file.write_text(json.dumps(pdt_data))

        # First init: migrates
        store1 = StateStore(tmp_path / "test.db")
        count_after_first = store1.get_day_trade_count(window_start="2026-01-01")
        store1.close()

        # Second init: .migrated exists, not .json, so no re-migration
        store2 = StateStore(tmp_path / "test.db")
        count_after_second = store2.get_day_trade_count(window_start="2026-01-01")
        store2.close()

        assert count_after_first == 1
        assert count_after_second == 1, "Re-migration should not double-insert"
