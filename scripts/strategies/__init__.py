"""Strategy package for the trading bot plugin.

Provides the BaseStrategy ABC and STRATEGY_REGISTRY for pluggable strategy
selection by config name. Each strategy reads an indicator-enriched DataFrame
and returns a Signal dataclass for the order executor.
"""
from abc import ABC, abstractmethod

import pandas as pd

from scripts.types import Signal

# Import all concrete strategy implementations
from scripts.strategies.momentum import MomentumStrategy
from scripts.strategies.mean_reversion import MeanReversionStrategy
from scripts.strategies.breakout import BreakoutStrategy
from scripts.strategies.vwap import VWAPStrategy


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


# Registry mapping config names (from config.json strategies array) to classes.
# Users select strategies by name during /initialize.
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "vwap": VWAPStrategy,
}

__all__ = ["BaseStrategy", "STRATEGY_REGISTRY"]
