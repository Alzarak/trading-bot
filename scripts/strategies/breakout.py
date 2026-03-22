"""Breakout trading strategy for the trading bot plugin.

Trades a price break above a significant resistance level (20-bar high)
with volume confirmation. Produces BUY signals when price makes a new 20-bar
high AND volume exceeds 1.5x the 20-bar average. Produces SELL signals when
the breakout fails (price falls back below the breakout level).
"""
import math

import pandas as pd
from loguru import logger

from scripts.types import Signal


class BreakoutStrategy:
    """Breakout strategy: buy resistance breaks with volume confirmation.

    Entry (BUY): price > 20-bar high (prior bar's rolling max) AND volume > 1.5x 20-bar avg.
    Exit (SELL): price falls below the 20-bar high (breakout failure).
    """

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> Signal:
        """Generate a breakout trade signal.

        Args:
            df: Indicator-enriched DataFrame. Must have at least 21 rows for
                rolling 20-bar calculations.
            symbol: Ticker symbol.
            params: Strategy parameters with keys: lookback_period,
                volume_multiplier, atr_period, atr_multiplier.

        Returns:
            Signal with action BUY, SELL, or HOLD.
        """
        lookback = params.get("lookback_period", 20)
        vol_multiplier = params.get("volume_multiplier", 1.5)
        atr_col = f"ATRr_{params.get('atr_period', 14)}"
        atr_multiplier = params.get("atr_multiplier", 1.5)

        # Need at least lookback + 1 rows for prior bar's rolling max
        if len(df) < lookback + 1:
            logger.debug(
                "breakout[{}]: insufficient rows ({}) for {}-bar lookback — returning HOLD",
                symbol, len(df), lookback,
            )
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="breakout",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Insufficient data: need at least {lookback + 1} rows",
            )

        # Check required columns exist
        required_cols = [atr_col, "close", "high", "volume"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.warning(
                "breakout[{}]: missing columns {} — returning HOLD", symbol, missing
            )
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="breakout",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Missing indicator columns: {missing}",
            )

        row = df.iloc[-1]

        # Check NaN on ATR
        if _is_nan(row[atr_col]):
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="breakout",
                atr=0.0,
                stop_price=0.0,
                reasoning="Insufficient data: ATR is NaN",
            )

        atr = float(row[atr_col])
        close = float(row["close"])
        stop_price = round(close - (atr * atr_multiplier), 2)

        # 20-bar rolling max of high — use prior bar's max to confirm breakout
        # (compare against the max BEFORE the current bar)
        rolling_high_max = df["high"].rolling(lookback).max()
        prior_20bar_high = float(rolling_high_max.iloc[-2])

        # 20-bar rolling average of volume
        vol_avg = df["volume"].rolling(lookback).mean().iloc[-1]

        if _is_nan(prior_20bar_high) or _is_nan(vol_avg):
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="breakout",
                atr=atr,
                stop_price=stop_price,
                reasoning="Insufficient data: rolling high or volume average is NaN",
            )

        current_20bar_high = float(rolling_high_max.iloc[-1])
        volume = float(row["volume"])

        # BUY conditions (all must be true)
        new_high = close > prior_20bar_high
        high_volume = volume > float(vol_avg) * vol_multiplier

        if new_high and high_volume:
            reasoning = (
                f"BUY: price ({close:.2f}) breaks 20-bar high ({prior_20bar_high:.2f}), "
                f"volume ({volume:.0f}) > {vol_multiplier}x 20-bar avg ({float(vol_avg):.0f})"
            )
            logger.info("breakout[{}]: {}", symbol, reasoning)
            return Signal(
                action="BUY",
                confidence=0.7,
                symbol=symbol,
                strategy="breakout",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # SELL condition: price falls below the current 20-bar rolling high (breakout failure)
        if close < current_20bar_high and not _is_nan(current_20bar_high):
            # Only SELL if price had previously broken out (it's below the rolling high)
            # and volume is falling — acts as a failed continuation signal
            reasoning = (
                f"SELL: price ({close:.2f}) below 20-bar rolling high ({current_20bar_high:.2f}) "
                f"— breakout failure"
            )
            logger.info("breakout[{}]: {}", symbol, reasoning)
            return Signal(
                action="SELL",
                confidence=0.6,
                symbol=symbol,
                strategy="breakout",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # HOLD
        reasons = []
        if not new_high:
            reasons.append(f"no new 20-bar high (close {close:.2f} <= prior high {prior_20bar_high:.2f})")
        if not high_volume:
            reasons.append(
                f"volume ({volume:.0f}) < {vol_multiplier}x avg ({float(vol_avg) * vol_multiplier:.0f})"
            )
        reasoning = "HOLD: " + "; ".join(reasons) if reasons else "HOLD: conditions not met"
        logger.debug("breakout[{}]: {}", symbol, reasoning)
        return Signal(
            action="HOLD",
            confidence=0.0,
            symbol=symbol,
            strategy="breakout",
            atr=atr,
            stop_price=stop_price,
            reasoning=reasoning,
        )


def _is_nan(value) -> bool:
    """Return True if value is NaN or None."""
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True
