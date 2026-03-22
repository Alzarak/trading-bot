"""Strategy package for the trading bot plugin.

Provides the BaseStrategy ABC and STRATEGY_REGISTRY for pluggable strategy
selection by config name. Each strategy reads an indicator-enriched DataFrame
and returns a Signal dataclass for the order executor.
"""
# BaseStrategy is defined in base.py to avoid circular imports.
# Concrete strategies inherit from base.BaseStrategy directly.
from scripts.strategies.base import BaseStrategy

# Import all concrete strategy implementations
from scripts.strategies.momentum import MomentumStrategy
from scripts.strategies.mean_reversion import MeanReversionStrategy
from scripts.strategies.breakout import BreakoutStrategy
from scripts.strategies.vwap import VWAPStrategy


# Registry mapping config names (from config.json strategies array) to classes.
# Users select strategies by name during /initialize.
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "vwap": VWAPStrategy,
}

__all__ = ["BaseStrategy", "STRATEGY_REGISTRY"]
