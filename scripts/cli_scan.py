"""CLI entry point for scanning market indicators.

Called by /trading-bot:run agent mode to fetch and display indicator data.
Outputs structured text that Claude reads and analyzes.

Usage:
    python cli_scan.py                    # scan watchlist from config
    python cli_scan.py AAPL MSFT NVDA     # scan specific symbols
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Resolve paths
def _find_bot_dir() -> Path:
    """Find the trading-bot data directory."""
    # Check env var first
    if os.environ.get("TRADING_BOT_DIR"):
        return Path(os.environ["TRADING_BOT_DIR"])
    # Project-level
    project_dir = Path.cwd() / "trading-bot"
    if project_dir.is_dir():
        return project_dir
    return Path.cwd()


def main() -> None:
    bot_dir = _find_bot_dir()

    # Load .env for API credentials
    env_file = bot_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    # Load config
    config_file = bot_dir / "config.json"
    if not config_file.exists():
        print("ERROR: config.json not found. Run /trading-bot:initialize first.", file=sys.stderr)
        sys.exit(1)

    config = json.loads(config_file.read_text())

    # Create Alpaca clients
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient

    key = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env", file=sys.stderr)
        sys.exit(1)

    paper = config.get("paper_trading", True)
    trading_client = TradingClient(key, secret, paper=paper)
    data_client = StockHistoricalDataClient(key, secret)

    # Create scanner
    from scripts.market_scanner import MarketScanner
    scanner = MarketScanner(trading_client, data_client, config)

    # Check market hours
    is_open = scanner.is_market_open()
    print(f"Market open: {is_open}")

    # Determine watchlist
    if len(sys.argv) > 1:
        watchlist = [s.upper() for s in sys.argv[1:]]
    else:
        watchlist = config.get("watchlist", [])
        if not watchlist:
            watchlist = scanner.discover_symbols()
            print(f"Auto-discovered watchlist: {watchlist}")

    print(f"Watchlist: {watchlist}")
    print(f"Strategies: {[s.get('name') for s in config.get('strategies', [])]}")
    print()

    # Scan each symbol
    skip_cols = {"open", "high", "low", "close", "volume", "trade_count", "vwap"}
    for sym in watchlist:
        print(f"=== {sym} ===")
        try:
            df = scanner.scan(sym)
            if df is None or df.empty:
                print("  No data returned")
                continue

            last = df.iloc[-1]
            print(f"  Price: {last['close']:.2f}")
            print(f"  Volume: {int(last['volume'])}")

            # Print all indicator columns dynamically
            for col in sorted(df.columns):
                if col not in skip_cols:
                    val = last[col]
                    if str(val) != "nan":
                        print(f"  {col}: {val:.4f}")
        except Exception as e:
            print(f"  Error: {e}")
        print()


if __name__ == "__main__":
    # Suppress loguru debug output for clean CLI output
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    main()
