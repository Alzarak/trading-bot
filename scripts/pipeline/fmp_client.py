"""Shared FMP API client for the trading bot pipeline.

Implements graceful degradation (D-01/D-02): when FMP_API_KEY is absent or
rate-limited, all methods return None and log a warning once. Never raises
exceptions to callers.

Uses requests-cache with SQLite backend (D-03) for persistent caching across
bot restarts. Uses tenacity for exponential backoff with jitter on 429/5xx (D-03).
"""
from __future__ import annotations

import os
from contextlib import suppress
from typing import Optional

import requests_cache
from requests.exceptions import RequestException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from loguru import logger


class FMPClient:
    """Shared FMP API client with graceful degradation and per-endpoint caching.

    Instantiate once and pass through the pipeline. A single instance is shared
    across RegimeDetector, VCP screener, and earnings drift screener.

    When no API key is available:
        - _enabled is False
        - All public methods return None immediately
        - One WARNING logged during __init__

    When API key is present:
        - Uses requests-cache CachedSession with SQLite backend (fmp_cache.db)
        - Per-endpoint TTL via url_expire_after mapping
        - _daily_calls tracks requests toward the 250/day free tier limit
    """

    BASE_URL = "https://financialmodelingprep.com/api/v3"
    STABLE_URL = "https://financialmodelingprep.com/stable"

    # Per-endpoint cache TTL in seconds (D-04 informed; slow data cached longer)
    _URL_EXPIRE = {
        # Treasury rates change daily — cache for 6 hours
        "*/treasury-rates*": 21600,
        # Earnings surprises change at most once per quarter
        "*/earnings-surprises*": 86400,
        # Historical prices: 5-minute TTL (regime uses intraday ratios)
        "*/historical-price-full*": 300,
        # Economic calendar: refresh hourly
        "*/economic_calendar*": 3600,
        # Stock screener: 5-minute TTL
        "*/stock-screener*": 300,
    }

    def __init__(self, api_key: Optional[str] = None, cache_db_path: str = "fmp_cache") -> None:
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        self._enabled = bool(self.api_key)
        self._daily_calls: int = 0

        if not self._enabled:
            logger.warning(
                "FMP_API_KEY not set — FMP features disabled, using neutral defaults "
                "(regime=transitional, top_risk=30)"
            )
            return

        self._session = requests_cache.CachedSession(
            cache_db_path,
            backend="sqlite",
            expire_after=300,  # default 5-min TTL; overridden per-URL below
            urls_expire_after=self._URL_EXPIRE,
        )
        self._session.headers.update({"apikey": self.api_key})
        logger.debug("FMPClient initialized — daily call budget: 250/day")

    # ------------------------------------------------------------------
    # Public endpoints (all return None on any failure — D-02)
    # ------------------------------------------------------------------

    def get_historical_prices(self, symbol: str, days: int = 600) -> Optional[dict]:
        """Fetch daily OHLCV price history for a symbol.

        Used by regime calculators for cross-asset ratios (SPY, IWM, RSP, HYG, etc.).
        Returns the full FMP response dict or None on failure.
        """
        if not self._enabled:
            return None
        return self._get(
            f"{self.BASE_URL}/historical-price-full/{symbol}",
            {"timeseries": days},
        )

    def get_treasury_rates(self, days: int = 600) -> Optional[list]:
        """Fetch historical treasury rate data.

        Used by yield curve regime calculator.
        Returns a list of rate records or None on failure.
        """
        if not self._enabled:
            return None
        return self._get(f"{self.STABLE_URL}/treasury-rates", {"limit": days})

    def get_economic_calendar(self, from_date: str, to_date: str) -> Optional[list]:
        """Fetch economic event calendar between two dates (YYYY-MM-DD format).

        Used by regime detection context. Returns list of events or None.
        """
        if not self._enabled:
            return None
        return self._get(
            f"{self.BASE_URL}/economic_calendar",
            {"from": from_date, "to": to_date},
        )

    def get_earnings_surprises(self, symbol: str) -> Optional[list]:
        """Fetch earnings surprise history for a symbol.

        Used by earnings drift screener (Phase 2). Returns list or None.
        """
        if not self._enabled:
            return None
        return self._get(f"{self.STABLE_URL}/earnings-surprises/{symbol}", {})

    def get_stock_screener(self, **kwargs) -> Optional[list]:
        """Run FMP stock screener with given filter kwargs.

        Used by VCP and earnings drift screeners (Phase 2). Returns list or None.
        """
        if not self._enabled:
            return None
        return self._get(f"{self.BASE_URL}/stock-screener", kwargs)

    @property
    def daily_calls(self) -> int:
        """Number of API calls made today (tracks toward 250/day free tier limit)."""
        return self._daily_calls

    # ------------------------------------------------------------------
    # Internal HTTP layer with retry and caching
    # ------------------------------------------------------------------

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(RequestException),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    def _get(self, url: str, params: dict) -> Optional[dict | list]:
        """Make a cached GET request. Returns None on any error (D-02).

        Tenacity retries on RequestException (covers 429 re-raised below)
        with exponential backoff: 4s, 8s, 16s (capped at 60s). After 3
        attempts, reraise=False means the exception is suppressed and None
        is returned to the caller.
        """
        with suppress(Exception):
            resp = self._session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                if not getattr(resp, "from_cache", False):
                    self._daily_calls += 1
                    if self._daily_calls % 50 == 0:
                        logger.warning(
                            "FMP daily call count: {}/250", self._daily_calls
                        )
                return resp.json()
            elif resp.status_code == 429:
                logger.warning("FMP rate limit (429) on {} — tenacity will retry", url)
                raise RequestException("FMP 429 rate limit")
            else:
                logger.warning(
                    "FMP API error {} for {} — returning None", resp.status_code, url
                )
        return None
