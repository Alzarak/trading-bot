"""Shared type definitions for the trading bot plugin.

All strategy modules and the order executor use these contracts
to communicate trade decisions through the pipeline.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass
class Signal:
    """Trade signal produced by any strategy module.

    Attributes:
        action: Trade direction — BUY, SELL, or HOLD.
        confidence: Signal strength from 0.0 (no confidence) to 1.0 (certain).
        symbol: Ticker symbol the signal applies to (e.g. 'AAPL').
        strategy: Name of the strategy that produced this signal.
        atr: Current ATR value used to size the stop distance.
        stop_price: Pre-computed stop-loss price for this entry.
        reasoning: Human-readable audit trail explaining the signal.
    """

    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    symbol: str
    strategy: str
    atr: float
    stop_price: float
    reasoning: str
