"""Shared type definitions for the trading bot plugin.

All strategy modules and the order executor use these contracts
to communicate trade decisions through the pipeline.
"""
from __future__ import annotations

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


@dataclass
class ClaudeRecommendation:
    """Structured recommendation returned by Claude acting as market analyst.

    This is the output of ClaudeAnalyzer.parse_response() after Claude analyzes
    indicator DataFrames from MarketScanner.  Convert to Signal via to_signal()
    before routing through OrderExecutor.

    Claude operates as analyst only — it never submits orders.  The Python
    RiskManager validates every Signal before any Alpaca order is placed.

    Attributes:
        symbol: Ticker symbol the recommendation applies to (e.g. 'AAPL').
        action: Trade direction — BUY, SELL, or HOLD.
        confidence: Recommendation strength from 0.0 (no confidence) to 1.0 (certain).
        reasoning: Explicit explanation for audit trail — always required.
        strategy: Name of the strategy context used for analysis.
        atr: Current ATR value used to size the stop distance.
        stop_price: Pre-computed stop-loss price for this entry.
    """

    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    reasoning: str
    strategy: str
    atr: float
    stop_price: float

    def to_signal(self) -> Signal:
        """Convert this recommendation to a Signal for OrderExecutor routing.

        Returns:
            Signal with all fields mapped 1-to-1 from this recommendation.
        """
        return Signal(
            action=self.action,
            confidence=self.confidence,
            symbol=self.symbol,
            strategy=self.strategy,
            atr=self.atr,
            stop_price=self.stop_price,
            reasoning=self.reasoning,
        )
