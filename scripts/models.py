"""Shared type definitions for the trading bot plugin.

All strategy modules and the order executor use these contracts
to communicate trade decisions through the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class AssetType(str, Enum):
    """Asset class for routing through the correct data/order pipeline."""

    STOCK = "stock"
    CRYPTO = "crypto"


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
    asset_type: AssetType = field(default=AssetType.STOCK)


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
    asset_type: AssetType = field(default=AssetType.STOCK)

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
            asset_type=self.asset_type,
        )


@dataclass
class RegimeState:
    """Macro market regime and top risk assessment.

    Produced by RegimeDetector.detect() on each scan cycle.
    Cached with split TTL: regime label hourly, top_risk every 15 minutes.
    When FMP unavailable, defaults to regime='transitional', top_risk_score=30.0.

    Attributes:
        regime: Macro regime classification label.
        regime_confidence: Classification confidence 0.0-1.0.
        top_risk_score: Market top risk score 0-100 (intraday refresh).
        risk_zone: Human-readable zone color derived from top_risk_score.
        cached_at: UTC timestamp when this state was last refreshed.
        components: Dict of sub-component scores for auditability.
    """

    regime: Literal["broadening", "concentration", "contraction", "inflationary", "transitional"]
    regime_confidence: float
    top_risk_score: float
    risk_zone: Literal["green", "yellow", "orange", "red", "critical"]
    cached_at: datetime
    components: dict = field(default_factory=dict)


@dataclass
class ExposureDecision:
    """Exposure and sizing decision derived from RegimeState.

    Produced by ExposureCoach.evaluate(). Governs how much of the portfolio
    can be deployed and whether new BUY entries are permitted.

    Attributes:
        max_exposure_pct: Maximum portfolio exposure percentage allowed (0-100).
        bias: Market stance — determines whether new BUYs are permitted.
        position_size_multiplier: Scale factor applied to all position sizes (0.0-1.0).
        reason: Human-readable audit string explaining the decision.
    """

    max_exposure_pct: float
    bias: Literal["risk_on", "neutral", "risk_off", "SELL_ONLY"]
    position_size_multiplier: float
    reason: str


@dataclass
class RawSignal:
    """Unweighted signal from a single screener module.

    Produced by each screener (technical, earnings_drift, vcp) before aggregation.
    The atr field MUST be in absolute dollar units — not a ratio.
    Use: atr_dollars = ATRr_column_value * close_price before populating this field.

    Attributes:
        symbol: Ticker symbol (e.g. 'AAPL').
        action: Trade direction.
        source: Which screener produced this signal.
        score: Raw screener score 0-100.
        confidence: Normalized confidence 0.0-1.0.
        reasoning: Screener-specific explanation for auditability.
        entry_price: Suggested entry price.
        stop_price: Pre-computed stop-loss price.
        atr: ATR in absolute dollar units (NOT a ratio).
        asset_type: Asset class for routing.
        metadata: Screener-specific extra data (e.g. earnings date, VCP pivot).
    """

    symbol: str
    action: Literal["BUY", "SELL"]
    source: Literal["technical", "earnings_drift", "vcp"]
    score: float
    confidence: float
    reasoning: str
    entry_price: float
    stop_price: float
    atr: float
    asset_type: AssetType
    metadata: dict = field(default_factory=dict)


@dataclass
class AggregatedSignal:
    """Weighted conviction signal from signal aggregation across screeners.

    Produced by SignalAggregator. One AggregatedSignal per symbol — multiple
    screeners contributing to the same symbol are merged here.

    Attributes:
        symbol: Ticker symbol.
        action: Dominant trade direction after aggregation.
        conviction: Weighted conviction score 0.0-1.0.
        sources: List of screener names that contributed.
        agreement_count: Number of screeners agreeing on direction.
        contradictions: List of screener names disagreeing on direction.
        top_signal: The highest-scoring RawSignal for this symbol.
        all_signals: All RawSignals contributing to this aggregate.
    """

    symbol: str
    action: Literal["BUY", "SELL"]
    conviction: float
    sources: list[str] = field(default_factory=list)
    agreement_count: int = 0
    contradictions: list[str] = field(default_factory=list)
    top_signal: RawSignal | None = None
    all_signals: list[RawSignal] = field(default_factory=list)
