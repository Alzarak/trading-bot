"""Thin FMP price adapter for MAE/MFE calculation.

Single-purpose: fetch daily close prices.  Does not reuse existing
fmp_client modules (which vary in return shape across skills).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


class FMPPriceAdapter:
    """Fetch daily adjusted close prices from FMP API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        if not self.api_key:
            raise ValueError("FMP API key required. Set FMP_API_KEY env var or pass api_key.")

    def get_daily_closes(self, ticker: str, from_date: str, to_date: str) -> list[dict]:
        """Return daily close prices, oldest first.

        Args:
            ticker: Stock symbol (e.g., "AAPL").
            from_date: Start date "YYYY-MM-DD".
            to_date: End date "YYYY-MM-DD".

        Returns:
            List of {"date": "YYYY-MM-DD", "close": float}, oldest first.

        Raises:
            urllib.error.URLError: On network/API errors.
            ValueError: On invalid response.
        """
        url = f"{FMP_BASE_URL}/historical-price-full/{ticker}?from={from_date}&to={to_date}"
        req = urllib.request.Request(url, headers={"apikey": self.api_key})

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.error("FMP API error for %s: %s", ticker, e)
            raise

        historical = data.get("historical", [])
        if not historical:
            logger.warning("No price data returned for %s (%s to %s)", ticker, from_date, to_date)
            return []

        # FMP returns newest first; reverse to oldest first
        result = [
            {"date": item["date"], "close": item["adjClose"]}
            for item in reversed(historical)
            if "date" in item and "adjClose" in item
        ]
        return result
