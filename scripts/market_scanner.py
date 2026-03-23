"""Market scanner module for the trading bot plugin.

Fetches OHLCV bars from the Alpaca IEX feed and computes all 6 technical
indicators used by strategy modules: RSI, MACD, EMA (short + long), ATR,
Bollinger Bands, and VWAP.

This is the data pipeline foundation.  Every strategy module and the order
executor depend on indicator-enriched DataFrames produced here.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_ta  # noqa: F401 — registers df.ta accessor on import
from loguru import logger

# Import alpaca-py conditionally so unit tests can run without it installed
try:
    from alpaca.data.historical import StockHistoricalDataClient  # noqa: F401
    from alpaca.data.historical.screener import ScreenerClient
    from alpaca.data.requests import (
        MarketMoversRequest,
        MostActivesRequest,
        StockBarsRequest,
        StockSnapshotRequest,
    )
    from alpaca.data.timeframe import TimeFrame
except ImportError:  # pragma: no cover
    StockHistoricalDataClient = None  # type: ignore[assignment,misc]
    ScreenerClient = None  # type: ignore[assignment,misc]
    MarketMoversRequest = None  # type: ignore[assignment]
    MostActivesRequest = None  # type: ignore[assignment]
    StockBarsRequest = None  # type: ignore[assignment]
    StockSnapshotRequest = None  # type: ignore[assignment]
    TimeFrame = None  # type: ignore[assignment]

ET = ZoneInfo("America/New_York")

# Fallback watchlist for small budgets when screener API is unavailable.
# These are high-volume, exchange-listed stocks typically $1-$15.
# All above $1.00 to avoid Alpaca bracket order minimum increment issues.
_LOW_PRICE_FALLBACK = [
    "SOFI", "PLTR", "NIO", "GRAB", "RIVN",
    "LCID", "SNAP", "PINS", "HOOD", "SIRI",
]

# Default strategy parameters — overridden by config["strategy_params"]
_DEFAULTS: dict = {
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ema_short": 9,
    "ema_long": 21,
    "atr_period": 14,
    "bb_period": 20,
    "bb_std_dev": 2.0,
}


class MarketScanner:
    """Fetches OHLCV bars from Alpaca and computes technical indicators.

    Args:
        trading_client: Alpaca TradingClient (or mock) — used for market clock.
        data_client: Alpaca StockHistoricalDataClient (or mock) — bar fetching.
        config: Trading configuration dict (from config.json).
    """

    def __init__(self, trading_client, data_client, config: dict) -> None:
        self.trading_client = trading_client
        self.data_client = data_client
        self.config = config

        # Extract strategy params with defaults
        params = config.get("strategy_params", {})
        self.rsi_period: int = int(params.get("rsi_period", _DEFAULTS["rsi_period"]))
        self.macd_fast: int = int(params.get("macd_fast", _DEFAULTS["macd_fast"]))
        self.macd_slow: int = int(params.get("macd_slow", _DEFAULTS["macd_slow"]))
        self.macd_signal: int = int(params.get("macd_signal", _DEFAULTS["macd_signal"]))
        self.ema_short: int = int(params.get("ema_short", _DEFAULTS["ema_short"]))
        self.ema_long: int = int(params.get("ema_long", _DEFAULTS["ema_long"]))
        self.atr_period: int = int(params.get("atr_period", _DEFAULTS["atr_period"]))
        self.bb_period: int = int(params.get("bb_period", _DEFAULTS["bb_period"]))
        self.bb_std_dev: float = float(
            params.get("bb_std_dev", _DEFAULTS["bb_std_dev"])
        )

    # ------------------------------------------------------------------
    # Indicator computation
    # ------------------------------------------------------------------

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append all 6 technical indicators to df and drop NaN rows.

        Uses pandas-ta extension methods (df.ta.*) for all computations.
        VWAP requires a timezone-aware DatetimeIndex; this method localizes
        naive indexes to UTC then converts to America/New_York automatically.

        Args:
            df: OHLCV DataFrame.  Must have open, high, low, close, volume columns.

        Returns:
            Indicator-enriched DataFrame with NaN rows removed.
        """
        # VWAP requires a timezone-aware DatetimeIndex
        df = self._ensure_tz_aware(df)

        # 1. RSI
        df.ta.rsi(length=self.rsi_period, append=True)

        # 2. MACD (produces MACD, MACDh, MACDs columns)
        df.ta.macd(
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal=self.macd_signal,
            append=True,
        )

        # 3. EMA (short and long)
        df.ta.ema(length=self.ema_short, append=True)
        df.ta.ema(length=self.ema_long, append=True)

        # 4. ATR — NOTE: pandas-ta names this column ATRr_{period} not ATR_{period}
        df.ta.atr(length=self.atr_period, append=True)

        # 5. Bollinger Bands (lower, middle, upper)
        df.ta.bbands(length=self.bb_period, std=self.bb_std_dev, append=True)

        # 6. VWAP anchored daily — requires timezone-aware DatetimeIndex
        df.ta.vwap(anchor="D", append=True)

        # Drop NaN rows produced by rolling window warmup and IEX feed gaps
        df = df.dropna()

        logger.debug(
            "compute_indicators: {} rows after dropna (indicators: RSI, MACD, EMA, ATR, BBands, VWAP)",
            len(df),
        )
        return df

    def _ensure_tz_aware(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return df with a timezone-aware DatetimeIndex (America/New_York).

        If the index is already tz-aware and in ET, return as-is.
        If UTC, convert to ET.
        If naive (no tz), localize to UTC then convert to ET.
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            return df

        if df.index.tz is None:
            # Naive index — assume UTC, localize then convert
            df = df.copy()
            df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
        elif str(df.index.tz) != "America/New_York":
            # Already tz-aware but not ET — convert
            df = df.copy()
            df.index = df.index.tz_convert("America/New_York")

        return df

    # ------------------------------------------------------------------
    # Column name mapping
    # ------------------------------------------------------------------

    def get_indicator_columns(self) -> dict[str, str]:
        """Return logical name → actual DataFrame column name mapping.

        Uses current strategy params so callers never hard-code column names.
        The ATR column is named ATRr_{period} (true range ratio), NOT ATR_{period}.
        """
        f = self.macd_fast
        sl = self.macd_slow
        sig = self.macd_signal
        bb = self.bb_period
        bb_std = self.bb_std_dev

        # pandas-ta 0.4.71b0 names BBands columns as BBL_{period}_{std}_{std}
        # (the std appears twice — this is a quirk of the beta release)
        bb_suffix = f"{bb}_{bb_std}_{bb_std}"

        return {
            "rsi": f"RSI_{self.rsi_period}",
            "macd": f"MACD_{f}_{sl}_{sig}",
            "macd_histogram": f"MACDh_{f}_{sl}_{sig}",
            "macd_signal": f"MACDs_{f}_{sl}_{sig}",
            "ema_short": f"EMA_{self.ema_short}",
            "ema_long": f"EMA_{self.ema_long}",
            "atr": f"ATRr_{self.atr_period}",
            "bb_lower": f"BBL_{bb_suffix}",
            "bb_middle": f"BBM_{bb_suffix}",
            "bb_upper": f"BBU_{bb_suffix}",
            "vwap": "VWAP_D",
        }

    # ------------------------------------------------------------------
    # Bar fetching
    # ------------------------------------------------------------------

    def fetch_bars(self, symbol: str, days_back: int = 60) -> pd.DataFrame:
        """Fetch OHLCV minute bars from Alpaca IEX feed.

        Args:
            symbol: Ticker symbol (e.g. 'AAPL').
            days_back: Number of calendar days of history to fetch.

        Returns:
            DataFrame with DatetimeIndex in America/New_York timezone.
        """
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=datetime.now(ET) - timedelta(days=days_back),
            end=datetime.now(ET),
            feed="iex",
        )

        logger.info("Fetching {} bars for {} ({} days back)", TimeFrame.Minute, symbol, days_back)
        bars = self.data_client.get_stock_bars(request)
        df = bars.df.reset_index(level=0, drop=True)  # drop symbol from multi-index

        # Ensure timezone-aware index
        df = self._ensure_tz_aware(df)

        logger.debug("fetch_bars: {} rows returned for {}", len(df), symbol)
        return df

    # ------------------------------------------------------------------
    # Combined scan
    # ------------------------------------------------------------------

    def scan(self, symbol: str) -> pd.DataFrame:
        """Fetch bars and compute all indicators for a symbol.

        Returns an empty DataFrame if insufficient bars are available
        (e.g. market closed or new listing with < warmup rows).

        Args:
            symbol: Ticker symbol to scan.

        Returns:
            Indicator-enriched, NaN-free DataFrame, or empty DataFrame on error.
        """
        try:
            df = self.fetch_bars(symbol)
            if df.empty:
                logger.warning("scan: no bars returned for {} — skipping", symbol)
                return pd.DataFrame()

            df = self.compute_indicators(df)

            if df.empty:
                logger.warning(
                    "scan: all rows dropped after dropna for {} "
                    "(insufficient history for indicator warmup)",
                    symbol,
                )
                return pd.DataFrame()

            logger.info("scan: {} indicator rows ready for {}", len(df), symbol)
            return df

        except Exception as exc:
            logger.error("scan: failed for {}: {}", symbol, exc)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Symbol discovery
    # ------------------------------------------------------------------

    def discover_symbols(self, max_symbols: int = 10) -> list[str]:
        """Discover affordable, actively-traded stocks based on budget.

        Uses Alpaca's ScreenerClient to find high-volume stocks, then filters
        by price using a two-tier hybrid approach:
          Tier 1: stocks where price <= budget * max_position_pct / 100 (whole shares)
          Tier 2: stocks where price <= budget (fractional shares)
        Prefers Tier 1, fills remaining slots from Tier 2.

        Falls back to a curated low-price list if the screener API fails.

        Args:
            max_symbols: Maximum number of symbols to return.

        Returns:
            List of ticker symbols sorted by volume within each tier.
        """
        if ScreenerClient is None:
            logger.warning("discover_symbols: ScreenerClient not available — using fallback")
            return _LOW_PRICE_FALLBACK[:max_symbols]

        budget = float(self.config.get("budget_usd", 100))
        max_pct = float(self.config.get("max_position_pct", 5.0))
        whole_share_max = budget * (max_pct / 100)
        fractional_max = budget

        try:
            screener = ScreenerClient(
                api_key=self.data_client._api_key,
                secret_key=self.data_client._secret_key,
            )

            # Fetch most active stocks by volume
            actives = screener.get_most_actives(
                MostActivesRequest(top=100)
            )
            candidates = [s.symbol for s in actives.most_actives]

            # Fetch market movers (gainers have momentum)
            try:
                movers = screener.get_market_movers(
                    MarketMoversRequest(top=50)
                )
                candidates += [s.symbol for s in movers.gainers]
            except Exception as exc:
                logger.debug("discover_symbols: market movers failed: {}", exc)

            # Deduplicate while preserving order
            candidates = list(dict.fromkeys(candidates))

            if not candidates:
                logger.warning("discover_symbols: screener returned no candidates — using fallback")
                return _LOW_PRICE_FALLBACK[:max_symbols]

            # Get snapshots for price filtering
            snapshots = self.data_client.get_stock_snapshot(
                StockSnapshotRequest(symbol_or_symbols=candidates)
            )

            # Two-tier filtering
            tier1: list[tuple[str, float, float]] = []
            tier2: list[tuple[str, float, float]] = []
            for sym, snap in snapshots.items():
                price = snap.latest_trade.price if snap.latest_trade else None
                if not price:
                    continue
                vol = snap.daily_bar.volume if snap.daily_bar else 0
                if price <= whole_share_max:
                    tier1.append((sym, price, vol))
                elif price <= fractional_max:
                    tier2.append((sym, price, vol))

            # Sort each tier by volume (most liquid first)
            tier1.sort(key=lambda x: x[2], reverse=True)
            tier2.sort(key=lambda x: x[2], reverse=True)

            # Prefer Tier 1, fill remaining from Tier 2
            result = [sym for sym, _, _ in tier1[:max_symbols]]
            if len(result) < max_symbols:
                remaining = max_symbols - len(result)
                result += [sym for sym, _, _ in tier2[:remaining]]

            if result:
                logger.info(
                    "discover_symbols: found {} symbols (tier1={}, tier2={}, budget=${}, max_price=${})",
                    len(result), len(tier1), len(tier2), budget, whole_share_max,
                )
                return result

            logger.warning("discover_symbols: no affordable stocks found — using fallback")
            return _LOW_PRICE_FALLBACK[:max_symbols]

        except Exception as exc:
            logger.error("discover_symbols: screener API failed: {} — using fallback", exc)
            return _LOW_PRICE_FALLBACK[:max_symbols]

    # ------------------------------------------------------------------
    # Market clock
    # ------------------------------------------------------------------

    def is_market_open(self) -> bool:
        """Return True if the US stock market is currently open.

        Delegates to the Alpaca market clock endpoint.
        """
        clock = self.trading_client.get_clock()
        return clock.is_open
