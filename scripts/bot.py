"""Main entry point for the autonomous trading bot.

Wires all Phase 3 modules into a running bot:
  MarketScanner -> STRATEGY_REGISTRY -> OrderExecutor -> StateStore -> PortfolioTracker

Runs an APScheduler BackgroundScheduler at a 60-second interval. Checks the
market clock on every cycle. SIGINT/SIGTERM triggers a graceful shutdown that
finishes the current cycle, closes all open positions, and persists final state.

Usage:
    python -m scripts.bot
    # or
    python scripts/bot.py
"""
import json
import os
import signal as signal_module
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from scripts.market_scanner import MarketScanner
from scripts.order_executor import OrderExecutor
from scripts.portfolio_tracker import PortfolioTracker
from scripts.risk_manager import RiskManager
from scripts.state_store import StateStore
from scripts.strategies import STRATEGY_REGISTRY

# ------------------------------------------------------------------
# Module-level globals
# ------------------------------------------------------------------

_shutdown_requested: bool = False
ET = ZoneInfo("America/New_York")


# ------------------------------------------------------------------
# Signal handlers
# ------------------------------------------------------------------

def _handle_shutdown(signum, frame) -> None:
    """Set the shutdown flag on SIGINT or SIGTERM.

    The scheduler's current cycle will complete before the bot exits.
    """
    global _shutdown_requested
    logger.info(
        "Shutdown signal received ({}). Finishing current cycle...",
        signum,
    )
    _shutdown_requested = True


signal_module.signal(signal_module.SIGINT, _handle_shutdown)
signal_module.signal(signal_module.SIGTERM, _handle_shutdown)


# ------------------------------------------------------------------
# Configuration loading
# ------------------------------------------------------------------

def load_config() -> dict:
    """Load config.json from CLAUDE_PLUGIN_DATA or the current directory.

    Returns:
        Parsed configuration dict.

    Raises:
        FileNotFoundError: If config.json is not found in either location.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    data_dir = Path(os.environ.get("CLAUDE_PLUGIN_DATA", "."))
    config_path = data_dir / "config.json"

    if not config_path.exists():
        # Fall back to current directory
        config_path = Path("config.json")

    if not config_path.exists():
        raise FileNotFoundError(
            f"config.json not found in {data_dir} or current directory. "
            "Run /initialize to generate your configuration."
        )

    logger.info("Loading config from {}", config_path)
    return json.loads(config_path.read_text())


# ------------------------------------------------------------------
# Client creation
# ------------------------------------------------------------------

def create_clients(config: dict) -> tuple:
    """Create and return Alpaca TradingClient and StockHistoricalDataClient.

    API keys are read from environment variables — never hardcoded.

    Args:
        config: Trading configuration dict. Uses config["paper_trading"] to
                set the paper flag on TradingClient.

    Returns:
        Tuple of (TradingClient, StockHistoricalDataClient).

    Raises:
        ImportError: If alpaca-py is not installed.
        ValueError: If ALPACA_API_KEY or ALPACA_SECRET_KEY are not set.
    """
    # Import conditionally for testability
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient
    except ImportError as exc:
        raise ImportError(
            "alpaca-py is required. Install it: pip install alpaca-py==0.43.2"
        ) from exc

    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")

    if not api_key or not secret_key:
        raise ValueError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set. "
            "Copy .env.template to .env and fill in your credentials."
        )

    paper = config.get("paper_trading", True)
    logger.info("Creating Alpaca clients (paper={})", paper)

    trading_client = TradingClient(api_key, secret_key, paper=paper)
    data_client = StockHistoricalDataClient(api_key, secret_key)

    return trading_client, data_client


# ------------------------------------------------------------------
# Core trading pipeline
# ------------------------------------------------------------------

def scan_and_trade(
    scanner: MarketScanner,
    strategies: list,
    executor: OrderExecutor,
    tracker: PortfolioTracker,
    state_store: StateStore,
    config: dict,
) -> None:
    """Run one full scan-and-trade cycle across all watchlist symbols.

    Called by APScheduler every 60 seconds. Guards against:
    - Shutdown requested (exits immediately)
    - Market closed (logs and returns without scanning)
    - Empty DataFrames from scanner (logs and skips symbol)

    For each symbol x strategy combination that produces an actionable signal:
    - BUY: execute bracket order, upsert position in SQLite, log trade
    - SELL: execute market order, mark position closed in SQLite, log trade with P&L

    Args:
        scanner: MarketScanner instance for fetching bars + indicators.
        strategies: List of strategy config dicts from config["strategies"].
        executor: OrderExecutor instance for order submission.
        tracker: PortfolioTracker instance for trade logging and P&L.
        state_store: StateStore instance for position persistence.
        config: Trading configuration dict.
    """
    if _shutdown_requested:
        logger.info("scan_and_trade: shutdown requested — skipping cycle")
        return

    if not scanner.is_market_open():
        logger.info("scan_and_trade: market closed — skipping cycle")
        return

    watchlist = config.get("watchlist", [])
    logger.info("scan_and_trade: scanning {} symbols", len(watchlist))

    for symbol in watchlist:
        try:
            df = scanner.scan(symbol)
            if df.empty:
                logger.warning("scan_and_trade: no data for {} — skipping", symbol)
                continue

            current_price = float(df.iloc[-1]["close"])

            for strategy_config in strategies:
                strategy_name = strategy_config.get("name")
                if strategy_name not in STRATEGY_REGISTRY:
                    logger.warning(
                        "scan_and_trade: unknown strategy '{}' — skipping",
                        strategy_name,
                    )
                    continue

                strategy_class = STRATEGY_REGISTRY[strategy_name]
                strategy = strategy_class()
                params = strategy_config.get("params", {})
                signal = strategy.generate_signal(df, symbol, params)

                if signal.action == "BUY":
                    logger.info(
                        "BUY signal: {} from {} (confidence={:.2f})",
                        symbol, strategy_name, signal.confidence,
                    )
                    order = executor.execute_signal(signal, current_price)
                    if order is not None:
                        qty = int(getattr(order, "qty", 0))
                        stop_price = signal.stop_price
                        state_store.upsert_position(
                            symbol=symbol,
                            qty=qty,
                            entry_price=current_price,
                            stop_price=stop_price,
                            strategy=signal.strategy,
                        )
                        tracker.log_trade(
                            symbol=symbol,
                            action="BUY",
                            price=current_price,
                            qty=qty,
                            strategy=signal.strategy,
                            order_type="bracket",
                        )

                elif signal.action == "SELL":
                    logger.info(
                        "SELL signal: {} from {} (confidence={:.2f})",
                        symbol, strategy_name, signal.confidence,
                    )
                    order = executor.execute_signal(signal, current_price)
                    if order is not None:
                        qty = int(getattr(order, "qty", 0))

                        # Compute P&L from entry price in SQLite
                        position = state_store.get_position(symbol)
                        pnl = None
                        if position is not None:
                            entry_price = position.get("entry_price", current_price)
                            pos_qty = position.get("qty", qty)
                            pnl = (current_price - entry_price) * pos_qty

                        state_store.mark_position_closed(symbol)
                        tracker.log_trade(
                            symbol=symbol,
                            action="SELL",
                            price=current_price,
                            qty=qty,
                            strategy=signal.strategy,
                            order_type="market",
                            pnl=pnl,
                        )

        except Exception as exc:
            logger.error(
                "scan_and_trade: error processing {}: {}",
                symbol, exc,
            )


# ------------------------------------------------------------------
# Graceful shutdown
# ------------------------------------------------------------------

def perform_graceful_shutdown(trading_client, state_store: StateStore) -> None:
    """Close all open Alpaca positions and mark them closed in SQLite.

    Called after the scheduler finishes its last cycle. Errors on individual
    position closures are caught and logged — the shutdown continues for
    remaining positions regardless of failures.

    Args:
        trading_client: Alpaca TradingClient with get_all_positions() and
                        close_position() methods.
        state_store: StateStore instance for position status updates.
    """
    logger.info("Closing all open positions...")

    try:
        positions = trading_client.get_all_positions()
    except Exception as exc:
        logger.error("Failed to fetch positions during shutdown: {}", exc)
        return

    if not positions:
        logger.info("No open positions to close.")
        return

    for pos in positions:
        symbol = pos.symbol
        try:
            trading_client.close_position(symbol)
            state_store.mark_position_closed(symbol)
            logger.info("Closed position: {}", symbol)
        except Exception as exc:
            logger.error("Failed to close position {}: {}", symbol, exc)

    logger.info("Graceful shutdown complete.")


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

def main() -> None:
    """Initialize and run the autonomous trading bot.

    Setup sequence:
    1. Load config.json
    2. Create Alpaca clients
    3. Initialize StateStore (SQLite at CLAUDE_PLUGIN_DATA/trading.db)
    4. Crash recovery via reconcile_positions
    5. Create RiskManager with state_store (PDT delegated to SQLite)
    6. Initialize session (capture start equity, check circuit breaker)
    7. Create MarketScanner, OrderExecutor, PortfolioTracker
    8. Load strategy configs from config["strategies"]
    9. Start BackgroundScheduler with 60-second IntervalTrigger
    10. Wait for shutdown signal (SIGINT/SIGTERM)
    11. Scheduler shutdown (wait for current cycle to complete)
    12. Graceful shutdown: close all positions
    13. Close SQLite connection
    14. Log final P&L summary
    """
    logger.info("=== Trading Bot Starting ===")

    # 1. Load config
    config = load_config()

    # 2. Create clients
    trading_client, data_client = create_clients(config)

    # 3. Initialize StateStore
    data_dir = Path(os.environ.get("CLAUDE_PLUGIN_DATA", "."))
    db_path = data_dir / "trading.db"
    state_store = StateStore(db_path)
    logger.info("StateStore initialized at {}", db_path)

    # 4. Crash recovery
    reconcile_result = state_store.reconcile_positions(trading_client)
    logger.info(
        "Crash recovery: inserted={}, closed={}, updated={}",
        len(reconcile_result["inserted"]),
        len(reconcile_result["closed"]),
        len(reconcile_result["updated"]),
    )

    # 5. Create RiskManager with state_store delegation
    risk_manager = RiskManager(config, trading_client, state_store=state_store)

    # 6. Initialize session (circuit breaker check + start equity capture)
    risk_manager.initialize_session()

    # 7. Create scanner, executor, tracker
    scanner = MarketScanner(trading_client, data_client, config)
    executor = OrderExecutor(risk_manager, config)
    tracker = PortfolioTracker(trading_client, state_store, config)

    # 8. Load strategies from config
    strategies = config.get("strategies", [])
    if not strategies:
        logger.warning("No strategies configured — bot will scan but not trade")

    logger.info(
        "Loaded {} strategies: {}",
        len(strategies),
        [s.get("name") for s in strategies],
    )

    # 9. Create and start APScheduler
    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(
        func=scan_and_trade,
        trigger=IntervalTrigger(seconds=60),
        args=[scanner, strategies, executor, tracker, state_store, config],
        id="scan_and_trade",
        name="Market scan and trade cycle",
        misfire_grace_time=30,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Trading bot started. Press Ctrl+C to stop.")

    # 10. Wait loop — sleep 1s at a time to stay responsive to shutdown signals
    while not _shutdown_requested:
        time.sleep(1)

    # 11. Scheduler shutdown — wait=True lets the current cycle finish
    logger.info("Stopping scheduler (waiting for current cycle to complete)...")
    scheduler.shutdown(wait=True)

    # 12. Graceful shutdown: close all positions
    perform_graceful_shutdown(trading_client, state_store)

    # 13. Close SQLite connection
    state_store.close()

    # 14. Log final P&L summary
    try:
        pnl = tracker.get_daily_pnl()
        logger.info(
            "=== Final P&L Summary === "
            "Daily P&L: ${:.2f} ({:.2f}%) | "
            "Start equity: ${:.2f} | Current equity: ${:.2f}",
            pnl["daily_pnl"],
            pnl["daily_pnl_pct"],
            pnl["start_equity"],
            pnl["current_equity"],
        )
    except Exception as exc:
        logger.warning("Could not compute final P&L: {}", exc)

    logger.info("=== Trading Bot Stopped ===")


if __name__ == "__main__":
    main()
