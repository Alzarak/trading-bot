"""SQLite-backed StateStore for persisting positions, orders, trade history, and day trades.

Provides crash recovery via Alpaca position reconciliation, and migrates legacy
pdt_trades.json data to SQLite on first use.

This is the safety substrate for position tracking. Without it, a crash means
lost position tracking, incorrect PDT counts, and no trade audit trail.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from loguru import logger


class StateStore:
    """SQLite-backed persistence for positions, orders, trades, and day trades.

    Args:
        db_path: Path to the SQLite database file (will be created if absent).

    On initialization:
        - Opens the database in WAL journal mode for crash robustness.
        - Creates the 4 required tables if they do not exist.
        - Migrates pdt_trades.json from the same directory if the file exists.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.commit()
        self._create_tables()

        # Migrate legacy PDT JSON if it exists alongside the database
        json_path = self.db_path.parent / "pdt_trades.json"
        if json_path.exists():
            self._migrate_pdt_json(json_path)

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        """Create all 4 tables if they do not already exist."""
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                qty INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                stop_price REAL NOT NULL,
                strategy TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                alpaca_order_id TEXT,
                status TEXT NOT NULL DEFAULT 'open'
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_order_id TEXT UNIQUE NOT NULL,
                alpaca_order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                qty INTEGER NOT NULL,
                limit_price REAL,
                stop_price REAL,
                status TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                filled_at TEXT
            );

            CREATE TABLE IF NOT EXISTS trade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                qty INTEGER NOT NULL,
                pnl REAL,
                strategy TEXT NOT NULL,
                order_type TEXT NOT NULL,
                logged_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS day_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Positions CRUD
    # ------------------------------------------------------------------

    def upsert_position(
        self,
        symbol: str,
        qty: int,
        entry_price: float,
        stop_price: float,
        strategy: str,
        opened_at: str | None = None,
        alpaca_order_id: str | None = None,
    ) -> None:
        """Insert or replace a position record.

        Args:
            symbol: Ticker symbol (PRIMARY KEY).
            qty: Number of shares held.
            entry_price: Average entry price per share.
            stop_price: Stop-loss price per share.
            strategy: Strategy name that opened the position.
            opened_at: ISO timestamp; defaults to current UTC time.
            alpaca_order_id: Alpaca order ID that opened the position.
        """
        if opened_at is None:
            opened_at = datetime.now().isoformat()

        self.conn.execute(
            """
            INSERT OR REPLACE INTO positions
                (symbol, qty, entry_price, stop_price, strategy, opened_at, alpaca_order_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (symbol, qty, entry_price, stop_price, strategy, opened_at, alpaca_order_id),
        )
        self.conn.commit()
        logger.debug("Upserted position: {} qty={} entry={:.2f}", symbol, qty, entry_price)

    def get_open_positions(self) -> dict[str, dict]:
        """Return all open positions keyed by symbol.

        Returns:
            Dict mapping symbol -> position dict with all columns.
        """
        cursor = self.conn.execute(
            "SELECT * FROM positions WHERE status='open'"
        )
        rows = cursor.fetchall()
        return {row["symbol"]: dict(row) for row in rows}

    def mark_position_closed(self, symbol: str) -> None:
        """Set position status to 'closed' for the given symbol.

        Args:
            symbol: Ticker symbol to close.
        """
        self.conn.execute(
            "UPDATE positions SET status='closed' WHERE symbol=?",
            (symbol,),
        )
        self.conn.commit()
        logger.info("Position closed in StateStore: {}", symbol)

    def get_position(self, symbol: str) -> dict | None:
        """Return a single position by symbol, or None if not found.

        Args:
            symbol: Ticker symbol.

        Returns:
            Position dict or None.
        """
        cursor = self.conn.execute(
            "SELECT * FROM positions WHERE symbol=?",
            (symbol,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Orders CRUD
    # ------------------------------------------------------------------

    def record_order(
        self,
        client_order_id: str,
        alpaca_order_id: str | None,
        symbol: str,
        side: str,
        order_type: str,
        qty: int,
        status: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> None:
        """Insert a new order record.

        Args:
            client_order_id: UUID used as idempotency key.
            alpaca_order_id: Alpaca-assigned order ID (may be None if submission failed).
            symbol: Ticker symbol.
            side: 'buy' or 'sell'.
            order_type: 'market', 'limit', 'bracket', etc.
            qty: Number of shares.
            status: Order status string (e.g. 'pending', 'filled').
            limit_price: Limit price (None for market orders).
            stop_price: Stop price (None for non-stop orders).
        """
        submitted_at = datetime.now().isoformat()
        self.conn.execute(
            """
            INSERT INTO orders
                (client_order_id, alpaca_order_id, symbol, side, order_type, qty,
                 limit_price, stop_price, status, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_order_id, alpaca_order_id, symbol, side, order_type, qty,
                limit_price, stop_price, status, submitted_at,
            ),
        )
        self.conn.commit()
        logger.debug("Order recorded: {} {} {} qty={}", side, qty, symbol, client_order_id)

    def update_order_status(
        self,
        client_order_id: str,
        status: str,
        filled_at: str | None = None,
    ) -> None:
        """Update the status (and optionally filled_at) of an existing order.

        Args:
            client_order_id: UUID identifying the order.
            status: New status string.
            filled_at: ISO timestamp of fill; None if not yet filled.
        """
        self.conn.execute(
            "UPDATE orders SET status=?, filled_at=? WHERE client_order_id=?",
            (status, filled_at, client_order_id),
        )
        self.conn.commit()
        logger.debug("Order status updated: {} -> {}", client_order_id, status)

    def get_order(self, client_order_id: str) -> dict | None:
        """Return a single order by client_order_id, or None if not found.

        Args:
            client_order_id: UUID identifying the order.

        Returns:
            Order dict or None.
        """
        cursor = self.conn.execute(
            "SELECT * FROM orders WHERE client_order_id=?",
            (client_order_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Trade log
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
        """Append an entry to the trade_log table.

        Args:
            symbol: Ticker symbol.
            action: 'buy' or 'sell'.
            price: Execution price.
            qty: Number of shares.
            strategy: Strategy that triggered the trade.
            order_type: Order type used (market, limit, bracket).
            pnl: Realized profit/loss (None for buy entries).
        """
        logged_at = datetime.now().isoformat()
        self.conn.execute(
            """
            INSERT INTO trade_log
                (symbol, action, price, qty, pnl, strategy, order_type, logged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, action, price, qty, pnl, strategy, order_type, logged_at),
        )
        self.conn.commit()
        logger.info(
            "Trade logged: {} {} {} @ {:.2f} pnl={}",
            action, qty, symbol, price, pnl,
        )

    def get_trade_history(self, limit: int = 100) -> list[dict]:
        """Return recent trades, most recent first.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            List of trade dicts ordered by logged_at DESC.
        """
        cursor = self.conn.execute(
            "SELECT * FROM trade_log ORDER BY logged_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Day trades (PDT tracking)
    # ------------------------------------------------------------------

    def record_day_trade(self, symbol: str, date: str) -> None:
        """Insert a day trade entry for PDT tracking.

        Args:
            symbol: Ticker symbol that was day-traded.
            date: Trade date as 'YYYY-MM-DD'.
        """
        self.conn.execute(
            "INSERT INTO day_trades (symbol, date) VALUES (?, ?)",
            (symbol, date),
        )
        self.conn.commit()
        logger.info("Day trade recorded: {} on {}", symbol, date)

    def get_day_trade_count(self, window_start: str) -> int:
        """Count day trades that occurred after window_start.

        Args:
            window_start: ISO date string 'YYYY-MM-DD'. Trades strictly
                          after this date are counted (exclusive).

        Returns:
            Integer count of matching day trades.
        """
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM day_trades WHERE date > ?",
            (window_start,),
        )
        return cursor.fetchone()[0]

    def get_day_trades(self, window_start: str) -> list[dict]:
        """Return all day trade entries after window_start.

        Args:
            window_start: ISO date string 'YYYY-MM-DD' (exclusive lower bound).

        Returns:
            List of day trade dicts.
        """
        cursor = self.conn.execute(
            "SELECT * FROM day_trades WHERE date > ? ORDER BY date ASC",
            (window_start,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Crash recovery / reconciliation
    # ------------------------------------------------------------------

    def reconcile_positions(self, trading_client) -> dict:
        """Reconcile SQLite open positions against live Alpaca positions.

        Three reconciliation cases:
          1. Position in Alpaca but NOT in SQLite -> insert with strategy='unknown_post_crash'
          2. Position in SQLite as 'open' but NOT in Alpaca -> mark closed
          3. Position in both -> update qty and entry_price from Alpaca (source of truth)

        Args:
            trading_client: Alpaca TradingClient instance. Must support
                            get_all_positions() returning objects with
                            .symbol, .qty, .avg_entry_price attributes.

        Returns:
            Summary dict: {"inserted": [symbols], "closed": [symbols], "updated": [symbols]}
        """
        alpaca_positions = trading_client.get_all_positions()
        alpaca_map: dict[str, object] = {p.symbol: p for p in alpaca_positions}

        sqlite_positions = self.get_open_positions()

        inserted: list[str] = []
        closed: list[str] = []
        updated: list[str] = []

        # Case 1 & 3: Iterate Alpaca positions
        for symbol, ap in alpaca_map.items():
            qty = int(ap.qty)
            entry_price = float(ap.avg_entry_price)

            if symbol not in sqlite_positions:
                # Case 1: Alpaca has it, SQLite does not -> insert
                logger.warning(
                    "Crash recovery: {} found in Alpaca but not SQLite — inserting",
                    symbol,
                )
                self.upsert_position(
                    symbol=symbol,
                    qty=qty,
                    entry_price=entry_price,
                    stop_price=0.0,
                    strategy="unknown_post_crash",
                )
                inserted.append(symbol)
            else:
                # Case 3: Both have it -> update from Alpaca (source of truth)
                logger.info(
                    "Crash recovery: updating {} qty={} entry={:.2f} from Alpaca",
                    symbol, qty, entry_price,
                )
                self.upsert_position(
                    symbol=symbol,
                    qty=qty,
                    entry_price=entry_price,
                    stop_price=sqlite_positions[symbol]["stop_price"],
                    strategy=sqlite_positions[symbol]["strategy"],
                    opened_at=sqlite_positions[symbol]["opened_at"],
                    alpaca_order_id=sqlite_positions[symbol].get("alpaca_order_id"),
                )
                updated.append(symbol)

        # Case 2: SQLite open but not in Alpaca -> mark closed
        for symbol in sqlite_positions:
            if symbol not in alpaca_map:
                logger.warning(
                    "Crash recovery: {} in SQLite as 'open' but not in Alpaca — marking closed",
                    symbol,
                )
                self.mark_position_closed(symbol)
                closed.append(symbol)

        summary = {"inserted": inserted, "closed": closed, "updated": updated}
        logger.info(
            "Reconciliation complete: inserted={} closed={} updated={}",
            len(inserted), len(closed), len(updated),
        )
        return summary

    # ------------------------------------------------------------------
    # PDT JSON migration
    # ------------------------------------------------------------------

    def _migrate_pdt_json(self, json_path: Path) -> None:
        """Migrate legacy pdt_trades.json to the day_trades SQLite table.

        Reads existing entries, inserts each into day_trades, then renames
        the JSON file to pdt_trades.json.migrated to prevent re-migration.

        Args:
            json_path: Absolute path to the pdt_trades.json file.
        """
        try:
            raw = json_path.read_text()
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read pdt_trades.json for migration: {}", exc)
            return

        if not isinstance(data, list):
            logger.warning(
                "pdt_trades.json has unexpected format (expected list) — skipping migration"
            )
            return

        count = 0
        for entry in data:
            symbol = entry.get("symbol")
            date = entry.get("date")
            if symbol and date:
                self.record_day_trade(symbol, date)
                count += 1

        migrated_path = json_path.parent / "pdt_trades.json.migrated"
        json_path.rename(migrated_path)
        logger.info(
            "Migrated {} PDT trade(s) from pdt_trades.json -> SQLite. "
            "Original renamed to {}",
            count, migrated_path,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.conn.close()
        logger.debug("StateStore connection closed: {}", self.db_path)
