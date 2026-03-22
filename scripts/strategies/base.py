"""BaseStrategy abstract base class for trading strategies.

Defined in a separate module so concrete strategy implementations can inherit
from it without circular import issues with scripts/strategies/__init__.py.
"""
from abc import ABC, abstractmethod

import pandas as pd

from scripts.types import Signal


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies.

    All strategies must implement generate_signal(), which reads the last row
    of an indicator-enriched DataFrame and returns a Signal dataclass.
    """

    @abstractmethod
    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> Signal:
        """Generate a trade signal from indicator-enriched OHLCV data.

        Args:
            df: Indicator-enriched DataFrame produced by MarketScanner.compute_indicators().
                Must contain at least 2 rows for crossover detection.
            symbol: Ticker symbol (e.g. 'AAPL').
            params: Strategy configuration dict with periods and thresholds.

        Returns:
            Signal dataclass with action, confidence, atr, stop_price, reasoning.
        """
        ...
