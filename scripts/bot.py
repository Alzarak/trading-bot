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

from apscheduler.triggers.cron import CronTrigger
from scripts.paths import get_data_dir
from scripts.audit_logger import AuditLogger
from scripts.claude_analyzer import ClaudeAnalyzer
from scripts.eod_report import EODReportGenerator
from scripts.market_scanner import MarketScanner
from scripts.notifier import Notifier
from scripts.order_executor import OrderExecutor
from scripts.portfolio_tracker import PortfolioTracker
from scripts.risk_manager import RiskManager
from scripts.state_store import StateStore
from scripts.models import AssetType
from scripts.strategies import STRATEGY_REGISTRY

# ------------------------------------------------------------------
# Module-level globals
# ------------------------------------------------------------------

_shutdown_requested: bool = False

# Aggressiveness level → confidence threshold mapping
_AGGRESSIVENESS_THRESHOLDS: dict[str, float] = {
    "conservative": 0.6,
    "moderate": 0.45,
    "aggressive": 0.3,
}


def _get_confidence_threshold(config: dict) -> float:
    """Derive confidence threshold from config.

    Checks in order:
    1. Explicit confidence_threshold field
    2. signal_aggressiveness field → mapped to threshold
    3. Default: 0.45 (moderate)
    """
    if "confidence_threshold" in config:
        return float(config["confidence_threshold"])
    aggressiveness = config.get("signal_aggressiveness", "moderate")
    return _AGGRESSIVENESS_THRESHOLDS.get(aggressiveness, 0.45)

# Discovery cache — refreshed hourly, not every 60s scan cycle
_discovered_watchlist: list[str] = []
_discovery_timestamp: float = 0.0
_DISCOVERY_INTERVAL: float = 3600.0  # 1 hour

# Crypto discovery cache (separate from stocks)
_discovered_crypto_watchlist: list[str] = []
_crypto_discovery_timestamp: float = 0.0
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
    """Load config.json from the trading bot data directory.

    Returns:
        Parsed configuration dict.

    Raises:
        FileNotFoundError: If config.json is not found.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    data_dir = get_data_dir()
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
    """Create and return Alpaca TradingClient, StockHistoricalDataClient, and CryptoHistoricalDataClient.

    API keys are read from environment variables — never hardcoded.
    The CryptoHistoricalDataClient is always created (lightweight) but only
    used if crypto trading is enabled in config.

    Args:
        config: Trading configuration dict. Uses config["paper_trading"] to
                set the paper flag on TradingClient.

    Returns:
        Tuple of (TradingClient, StockHistoricalDataClient, CryptoHistoricalDataClient).

    Raises:
        ImportError: If alpaca-py is not installed.
        ValueError: If ALPACA_API_KEY or ALPACA_SECRET_KEY are not set.
    """
    # Import conditionally for testability
    try:
        from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
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
    crypto_enabled = config.get("crypto", {}).get("enabled", False)
    logger.info("Creating Alpaca clients (paper={}, crypto={})", paper, crypto_enabled)

    trading_client = TradingClient(api_key, secret_key, paper=paper)
    data_client = StockHistoricalDataClient(api_key, secret_key)
    crypto_data_client = CryptoHistoricalDataClient(api_key, secret_key)

    return trading_client, data_client, crypto_data_client


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

    global _discovered_watchlist, _discovery_timestamp

    # --- Check budget before full scan ---
    budget = float(config.get("budget_usd", 100))
    min_trade_value = 0.50  # minimum useful trade
    try:
        positions = scanner.trading_client.get_all_positions()
        total_exposure = sum(abs(float(p.market_value)) for p in positions)
        remaining_budget = budget - total_exposure

        if remaining_budget < min_trade_value and positions:
            logger.info(
                "scan_and_trade: budget exhausted (${:.2f} remaining of ${:.2f}). "
                "Monitoring {} open positions for exit signals only.",
                remaining_budget, budget, len(positions),
            )
            # Only scan held positions for SELL signals
            held_symbols = [p.symbol for p in positions]
            for pos in positions:
                logger.info(
                    "  Position: {} | {} shares @ ${} | P&L: ${}",
                    pos.symbol, pos.qty, pos.avg_entry_price, pos.unrealized_pl,
                )
            # Scan held positions for exit signals
            for symbol in held_symbols:
                try:
                    df = scanner.scan(symbol)
                    if df.empty:
                        continue
                    current_price = float(df.iloc[-1]["close"])
                    for strategy_config in strategies:
                        strategy_name = strategy_config.get("name")
                        if strategy_name not in STRATEGY_REGISTRY:
                            continue
                        strategy = STRATEGY_REGISTRY[strategy_name]()
                        params = strategy_config.get("params", {})
                        signal = strategy.generate_signal(df, symbol, params)
                        threshold = _get_confidence_threshold(config)
                        if signal.action == "SELL" and signal.confidence >= threshold:
                            logger.info(
                                "SELL signal for held position: {} (confidence={:.2f})",
                                symbol, signal.confidence,
                            )
                            order = executor.execute_signal(signal, current_price)
                            if order is not None:
                                state_store.mark_position_closed(symbol)
                                tracker.log_trade(
                                    symbol=symbol, action="SELL",
                                    price=current_price,
                                    qty=int(getattr(order, "qty", 0)),
                                    strategy=signal.strategy, order_type="market",
                                )
                except Exception as exc:
                    logger.error("Error scanning held position {}: {}", symbol, exc)
            return

    except Exception as exc:
        logger.debug("scan_and_trade: exposure check failed: {} — continuing with full scan", exc)

    # --- Full scan cycle ---
    watchlist = config.get("watchlist", [])
    if not watchlist:
        # Auto-discover affordable stocks, cached hourly
        if time.time() - _discovery_timestamp > _DISCOVERY_INTERVAL or not _discovered_watchlist:
            _discovered_watchlist = scanner.discover_symbols()
            _discovery_timestamp = time.time()
            logger.info("Auto-discovered {} symbols: {}", len(_discovered_watchlist), _discovered_watchlist)
        watchlist = _discovered_watchlist

    # Always include held positions in scan so SELL signals fire
    try:
        positions = scanner.trading_client.get_all_positions()
        held_symbols = [p.symbol for p in positions]
        for sym in held_symbols:
            if sym not in watchlist:
                watchlist.append(sym)
    except Exception:
        pass  # non-critical — watchlist still works without held positions

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
                threshold = _get_confidence_threshold(config)

                if signal.action == "BUY" and signal.confidence >= threshold:
                    logger.info(
                        "BUY signal: {} from {} (confidence={:.2f}, threshold={:.2f})",
                        symbol, strategy_name, signal.confidence, threshold,
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

                elif signal.action == "SELL" and signal.confidence >= threshold:
                    logger.info(
                        "SELL signal: {} from {} (confidence={:.2f}, threshold={:.2f})",
                        symbol, strategy_name, signal.confidence, threshold,
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
# Crypto scan-and-trade cycle
# ------------------------------------------------------------------


def scan_and_trade_crypto(
    scanner: MarketScanner,
    strategies: list,
    executor: OrderExecutor,
    tracker: PortfolioTracker,
    state_store: StateStore,
    config: dict,
) -> None:
    """Run one crypto scan-and-trade cycle across all crypto watchlist symbols.

    Mirrors scan_and_trade() but with crypto-specific behavior:
    - No market hours check (crypto trades 24/7)
    - Uses crypto watchlist from config or auto-discovery
    - Passes AssetType.CRYPTO through the pipeline
    - Uses crypto budget when separate_budget is enabled
    """
    if _shutdown_requested:
        logger.info("scan_and_trade_crypto: shutdown requested — skipping cycle")
        return

    global _discovered_crypto_watchlist, _crypto_discovery_timestamp

    crypto_config = config.get("crypto", {})
    separate_budget = crypto_config.get("separate_budget", False)
    if separate_budget:
        budget = float(crypto_config.get("budget_usd", 100))
    else:
        budget = float(config.get("budget_usd", 100))

    min_trade_value = 0.50

    # --- Check crypto budget before full scan ---
    try:
        positions = scanner.trading_client.get_all_positions()
        # Filter to crypto positions only
        crypto_positions = [p for p in positions if "/" in p.symbol or MarketScanner.is_crypto_symbol(
            MarketScanner.normalize_crypto_symbol(p.symbol)
        )]
        crypto_exposure = sum(abs(float(p.market_value)) for p in crypto_positions)
        remaining_budget = budget - crypto_exposure

        if remaining_budget < min_trade_value and crypto_positions:
            logger.info(
                "scan_and_trade_crypto: budget exhausted (${:.2f} remaining of ${:.2f}). "
                "Monitoring {} crypto positions for exit signals only.",
                remaining_budget, budget, len(crypto_positions),
            )
            for pos in crypto_positions:
                symbol = MarketScanner.normalize_crypto_symbol(pos.symbol)
                try:
                    df = scanner.scan(symbol, crypto=True)
                    if df.empty:
                        continue
                    current_price = float(df.iloc[-1]["close"])
                    for strategy_config in strategies:
                        strategy_name = strategy_config.get("name")
                        if strategy_name not in STRATEGY_REGISTRY:
                            continue
                        strategy = STRATEGY_REGISTRY[strategy_name]()
                        params = strategy_config.get("params", {})
                        signal = strategy.generate_signal(df, symbol, params)
                        signal.asset_type = AssetType.CRYPTO
                        threshold = _get_confidence_threshold(config)
                        if signal.action == "SELL" and signal.confidence >= threshold:
                            logger.info(
                                "SELL signal for crypto position: {} (confidence={:.2f})",
                                symbol, signal.confidence,
                            )
                            order = executor.execute_signal(signal, current_price)
                            if order is not None:
                                state_store.mark_position_closed(symbol)
                                tracker.log_trade(
                                    symbol=symbol, action="SELL",
                                    price=current_price,
                                    qty=float(getattr(order, "qty", 0)),
                                    strategy=signal.strategy, order_type="market",
                                )
                except Exception as exc:
                    logger.error("Error scanning crypto position {}: {}", symbol, exc)
            return

    except Exception as exc:
        logger.debug("scan_and_trade_crypto: exposure check failed: {} — continuing", exc)

    # --- Full crypto scan cycle ---
    watchlist = crypto_config.get("watchlist", [])
    if not watchlist:
        if time.time() - _crypto_discovery_timestamp > _DISCOVERY_INTERVAL or not _discovered_crypto_watchlist:
            _discovered_crypto_watchlist = scanner.discover_crypto_symbols()
            _crypto_discovery_timestamp = time.time()
            logger.info("Auto-discovered {} crypto symbols: {}", len(_discovered_crypto_watchlist), _discovered_crypto_watchlist)
        watchlist = _discovered_crypto_watchlist

    # Include held crypto positions in scan
    try:
        positions = scanner.trading_client.get_all_positions()
        for p in positions:
            sym = MarketScanner.normalize_crypto_symbol(p.symbol)
            if MarketScanner.is_crypto_symbol(sym) and sym not in watchlist:
                watchlist.append(sym)
    except Exception:
        pass

    logger.info("scan_and_trade_crypto: scanning {} crypto symbols", len(watchlist))

    budget_override = budget if separate_budget else None

    for symbol in watchlist:
        try:
            df = scanner.scan(symbol, crypto=True)
            if df.empty:
                logger.warning("scan_and_trade_crypto: no data for {} — skipping", symbol)
                continue

            current_price = float(df.iloc[-1]["close"])

            for strategy_config in strategies:
                strategy_name = strategy_config.get("name")
                if strategy_name not in STRATEGY_REGISTRY:
                    continue

                strategy_class = STRATEGY_REGISTRY[strategy_name]
                strategy = strategy_class()
                params = strategy_config.get("params", {})
                signal = strategy.generate_signal(df, symbol, params)
                signal.asset_type = AssetType.CRYPTO
                if budget_override is not None:
                    signal.budget_override = budget_override
                threshold = _get_confidence_threshold(config)

                if signal.action == "BUY" and signal.confidence >= threshold:
                    logger.info(
                        "BUY signal: {} from {} (confidence={:.2f}, threshold={:.2f})",
                        symbol, strategy_name, signal.confidence, threshold,
                    )
                    order = executor.execute_signal(signal, current_price)
                    if order is not None:
                        qty = float(getattr(order, "qty", 0))
                        state_store.upsert_position(
                            symbol=symbol, qty=qty,
                            entry_price=current_price,
                            stop_price=signal.stop_price,
                            strategy=signal.strategy,
                        )
                        tracker.log_trade(
                            symbol=symbol, action="BUY",
                            price=current_price, qty=qty,
                            strategy=signal.strategy, order_type="limit",
                        )

                elif signal.action == "SELL" and signal.confidence >= threshold:
                    logger.info(
                        "SELL signal: {} from {} (confidence={:.2f}, threshold={:.2f})",
                        symbol, strategy_name, signal.confidence, threshold,
                    )
                    order = executor.execute_signal(signal, current_price)
                    if order is not None:
                        qty = float(getattr(order, "qty", 0))
                        position = state_store.get_position(symbol)
                        pnl = None
                        if position is not None:
                            entry_price = position.get("entry_price", current_price)
                            pos_qty = position.get("qty", qty)
                            pnl = (current_price - entry_price) * pos_qty
                        state_store.mark_position_closed(symbol)
                        tracker.log_trade(
                            symbol=symbol, action="SELL",
                            price=current_price, qty=qty,
                            strategy=signal.strategy, order_type="market",
                            pnl=pnl,
                        )

        except Exception as exc:
            logger.error("scan_and_trade_crypto: error processing {}: {}", symbol, exc)


# ------------------------------------------------------------------
# Claude analysis pipeline helpers (agent mode)
# ------------------------------------------------------------------

def get_analysis_context(scanner: MarketScanner, config: dict) -> dict:
    """Generate analysis context for all watchlist symbols.

    Builds a ClaudeAnalyzer prompt for each symbol x strategy combination.
    Used by the /run command agent mode to prepare analysis inputs for Claude.
    Claude receives these prompts, responds with JSON recommendations, and
    the responses are processed by execute_claude_recommendation().

    This function does NOT call Claude — it only prepares prompts.

    Args:
        scanner: MarketScanner instance for fetching bars and indicators.
        config: Trading configuration dict with watchlist and strategies.

    Returns:
        Dict of {"symbol_strategy": {"symbol", "strategy", "prompt",
        "current_price"}} for each valid symbol x strategy combination.
        Symbols with empty DataFrames are skipped.
    """
    analyzer = ClaudeAnalyzer(config, confidence_threshold=_get_confidence_threshold(config))
    watchlist = config.get("watchlist", [])
    context: dict = {}

    for symbol in watchlist:
        try:
            df = scanner.scan(symbol)
            if df.empty:
                logger.warning("get_analysis_context: no data for {} — skipping", symbol)
                continue

            current_price = float(df.iloc[-1]["close"])

            for strategy_config in config.get("strategies", []):
                strategy_name = strategy_config.get("name", "unknown")
                prompt = analyzer.build_analysis_prompt(symbol, df, strategy_name)
                key = f"{symbol}_{strategy_name}"
                context[key] = {
                    "symbol": symbol,
                    "strategy": strategy_name,
                    "prompt": prompt,
                    "current_price": current_price,
                }
                logger.debug(
                    "get_analysis_context: prepared prompt for {} / {}",
                    symbol,
                    strategy_name,
                )
        except Exception as exc:
            logger.error(
                "get_analysis_context: error preparing context for {}: {}",
                symbol,
                exc,
            )

    logger.info(
        "get_analysis_context: {} prompts prepared for {} symbols",
        len(context),
        len(watchlist),
    )
    return context


def execute_claude_recommendation(
    recommendation_json: str,
    executor: OrderExecutor,
    tracker: PortfolioTracker,
    state_store: StateStore,
    audit_logger: AuditLogger,
    analyzer: ClaudeAnalyzer,
) -> dict:
    """Parse a Claude recommendation JSON and execute through the risk manager.

    Implements the complete Claude analysis pipeline:
      1. Parse Claude's JSON response into ClaudeRecommendation objects
      2. Log each recommendation to the audit trail
      3. Convert to Signal via to_signal()
      4. Route through OrderExecutor.execute_signal() (all 4 risk checks)
      5. Log execution result (submitted/blocked/failed) to audit trail

    Claude never submits orders directly. All recommendations pass through
    the deterministic Python risk manager before any Alpaca order is placed.

    Args:
        recommendation_json: Raw Claude response text containing JSON recommendation.
        executor: OrderExecutor instance with risk manager wired in.
        tracker: PortfolioTracker for trade logging.
        state_store: StateStore for position persistence.
        audit_logger: AuditLogger for NDJSON decision audit trail.
        analyzer: ClaudeAnalyzer instance for parsing the response.

    Returns:
        Dict with "results" key containing a list of per-recommendation outcome
        dicts: {"symbol", "action", "status"}.
    """
    recs = analyzer.parse_response(recommendation_json)
    if not recs:
        logger.warning("execute_claude_recommendation: no valid recommendations parsed")
        return {"results": []}

    results = []
    for rec in recs:
        # Always log the recommendation before attempting execution
        audit_logger.log_recommendation(rec)

        if rec.action in ("BUY", "SELL"):
            signal = rec.to_signal()
            # Use stop_price as proxy for current_price since agent mode
            # should supply accurate price via context from get_analysis_context
            order = executor.execute_signal(signal, rec.stop_price)
            status = "submitted" if order is not None else "blocked"
            order_id = str(getattr(order, "id", None)) if order else None
            audit_logger.log_execution_result(rec, status, order_id)
            results.append(
                {"symbol": rec.symbol, "action": rec.action, "status": status}
            )
            logger.info(
                "execute_claude_recommendation: {} {} — {}",
                rec.action,
                rec.symbol,
                status,
            )
        else:
            # HOLD — log it but do not submit any order
            audit_logger.log_execution_result(rec, "hold", reason="HOLD signal — no order")
            results.append({"symbol": rec.symbol, "action": "HOLD", "status": "hold"})
            logger.debug(
                "execute_claude_recommendation: HOLD {} — no order submitted",
                rec.symbol,
            )

    return {"results": results}


# ------------------------------------------------------------------
# End-of-day report
# ------------------------------------------------------------------

def end_of_day_report(
    tracker: PortfolioTracker,
    state_store: StateStore,
    notifier: Notifier,
    eod_generator: EODReportGenerator,
) -> None:
    """Generate and dispatch the end-of-day trading summary.

    Called by APScheduler at 16:05 ET (5 minutes after market close).
    Generates a full report from trade history and P&L, logs it, sends
    it via the notifier, and checks each SELL trade for large events.

    Args:
        tracker: PortfolioTracker for P&L data and start equity.
        state_store: StateStore for trade history.
        notifier: Notifier for dispatching messages.
        eod_generator: EODReportGenerator for building the report dict.
    """
    try:
        report = eod_generator.generate(tracker, state_store)
        formatted = eod_generator.format_text(report)

        logger.info("End-of-day report:\n{}", formatted)
        notifier.send("End of Day Report", formatted)

        # Check sell trades for large events
        today_sells = [
            t for t in state_store.get_trade_history(limit=500)
            if t.get("action") == "SELL" and t.get("pnl") is not None
        ]
        for trade in today_sells:
            pnl = trade["pnl"]
            if notifier.is_large_event(pnl, tracker.start_equity):
                direction = "WIN" if pnl > 0 else "LOSS"
                notifier.send(
                    f"Large {direction}: {trade['symbol']}",
                    f"P&L: ${pnl:+.2f} on {trade['qty']} shares "
                    f"of {trade['symbol']} ({trade['strategy']})",
                    level="warning",
                )
    except Exception as exc:
        logger.error("end_of_day_report: failed to generate report: {}", exc)


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
    3. Initialize StateStore (SQLite at ./trading-bot/trading.db)
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
    trading_client, data_client, crypto_data_client = create_clients(config)

    # 3. Initialize StateStore
    data_dir = get_data_dir()
    db_path = data_dir / "trading.db"
    state_store = StateStore(db_path)
    logger.info("StateStore initialized at {}", db_path)

    # 3b. Initialize AuditLogger for Claude analysis pipeline
    audit_logger = AuditLogger(data_dir)
    logger.info("AuditLogger initialized at {}", audit_logger.audit_file)

    # 4. Crash recovery
    reconcile_result = state_store.reconcile_positions(trading_client)
    logger.info(
        "Crash recovery: inserted={}, closed={}, updated={}",
        len(reconcile_result["inserted"]),
        len(reconcile_result["closed"]),
        len(reconcile_result["updated"]),
    )

    # 5. Create Notifier and EODReportGenerator
    notifier = Notifier(config)
    eod_generator = EODReportGenerator()

    # 6. Create RiskManager with state_store and notifier
    risk_manager = RiskManager(config, trading_client, state_store=state_store, notifier=notifier)

    # 7. Initialize session (circuit breaker check + start equity capture)
    risk_manager.initialize_session()

    # 8. Create scanner, executor, tracker (tracker gets notifier for large trade alerts)
    scanner = MarketScanner(trading_client, data_client, config, crypto_data_client=crypto_data_client)
    executor = OrderExecutor(risk_manager, config)
    tracker = PortfolioTracker(trading_client, state_store, config, notifier=notifier)

    # 9. Load strategies from config
    strategies = config.get("strategies", [])
    if not strategies:
        logger.warning("No strategies configured — bot will scan but not trade")

    logger.info(
        "Loaded {} strategies: {}",
        len(strategies),
        [s.get("name") for s in strategies],
    )

    # 10. Create and start APScheduler
    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(
        func=scan_and_trade,
        trigger=IntervalTrigger(seconds=300),
        args=[scanner, strategies, executor, tracker, state_store, config],
        id="scan_and_trade",
        name="Market scan and trade cycle",
        misfire_grace_time=30,
        coalesce=True,
    )
    scheduler.add_job(
        func=end_of_day_report,
        trigger=CronTrigger(hour=16, minute=5, timezone="America/New_York"),
        args=[tracker, state_store, notifier, eod_generator],
        id="end_of_day_report",
        name="End-of-day summary report",
        misfire_grace_time=300,
        coalesce=True,
    )

    # 10b. Crypto scan job (24/7, no market hours check)
    crypto_config = config.get("crypto", {})
    if crypto_config.get("enabled", False):
        crypto_interval = int(crypto_config.get("scan_interval_seconds", 300))
        scheduler.add_job(
            func=scan_and_trade_crypto,
            trigger=IntervalTrigger(seconds=crypto_interval),
            args=[scanner, strategies, executor, tracker, state_store, config],
            id="scan_and_trade_crypto",
            name="Crypto scan and trade cycle (24/7)",
            misfire_grace_time=30,
            coalesce=True,
        )
        logger.info("Crypto trading enabled — scanning every {}s (24/7)", crypto_interval)
    else:
        logger.info("Crypto trading disabled — set crypto.enabled=true in config to activate")

    scheduler.start()
    logger.info("Trading bot started. Press Ctrl+C to stop.")

    # 11. Wait loop — sleep 1s at a time to stay responsive to shutdown signals
    while not _shutdown_requested:
        time.sleep(1)

    # 12. Scheduler shutdown — wait=True lets the current cycle finish
    logger.info("Stopping scheduler (waiting for current cycle to complete)...")
    scheduler.shutdown(wait=True)

    # 13. Graceful shutdown: close all positions
    perform_graceful_shutdown(trading_client, state_store)

    # 14. Close SQLite connection
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
