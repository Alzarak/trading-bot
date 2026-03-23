"""Breakout trading strategy for the trading bot plugin.

Trades a price break above a significant resistance level (20-bar high)
with volume confirmation. Produces BUY signals when price makes a new 20-bar
high AND volume exceeds 1.5x the 20-bar average. Produces SELL signals when
the breakout fails (price falls back below the breakout level).
"""
import math

import pandas as pd
from loguru import logger

from scripts.strategies.base import BaseStrategy
from scripts.models import Signal


class BreakoutStrategy(BaseStrategy):
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

        # --- BUY scoring (weighted) ---
        buy_score = 0.0
        buy_reasons: list[str] = []
        buy_conditions = 0

        # Condition 1: New 20-bar high (or near high for partial credit)
        if close > prior_20bar_high:
            buy_score += 0.35
            buy_conditions += 1
            buy_reasons.append(f"price ({close:.2f}) breaks 20-bar high ({prior_20bar_high:.2f})")
        elif prior_20bar_high > 0 and (prior_20bar_high - close) / prior_20bar_high <= 0.01:
            buy_score += 0.15
            buy_conditions += 1
            buy_reasons.append(f"price ({close:.2f}) within 1% of 20-bar high ({prior_20bar_high:.2f})")

        # Condition 2: Volume confirmation (strict or partial credit)
        if volume > float(vol_avg) * vol_multiplier:
            buy_score += 0.25
            buy_conditions += 1
            buy_reasons.append(
                f"volume ({volume:.0f}) > {vol_multiplier}x avg ({float(vol_avg):.0f})"
            )
        elif volume > float(vol_avg) * 1.2:
            buy_score += 0.10
            buy_conditions += 1
            buy_reasons.append(f"volume elevated ({volume:.0f}) > 1.2x avg ({float(vol_avg):.0f})")

        # Condition 3: ATR expanding (increasing volatility at breakout)
        prev_atr = float(df[atr_col].iloc[-2]) if not _is_nan(df[atr_col].iloc[-2]) else atr
        if atr > prev_atr:
            buy_score += 0.15
            buy_conditions += 1
            buy_reasons.append(f"ATR expanding ({prev_atr:.4f}->{atr:.4f})")

        # Condition 4: MACD positive (trend confirmation, optional column)
        macd_h_col = (
            f"MACDh_{params.get('macd_fast', 12)}_"
            f"{params.get('macd_slow', 26)}_"
            f"{params.get('macd_signal', 9)}"
        )
        if macd_h_col in df.columns and not _is_nan(row.get(macd_h_col)):
            if float(row[macd_h_col]) > 0:
                buy_score += 0.10
                buy_conditions += 1
                buy_reasons.append(f"MACD histogram positive ({float(row[macd_h_col]):.4f})")

        buy_score = min(buy_score, 1.0)

        # 2-of-N gate: need at least 2 conditions to produce a BUY
        if buy_conditions >= 2 and buy_score > 0:
            reasoning = (
                "BUY: " + "; ".join(buy_reasons)
                + f" [score={buy_score:.2f}, {buy_conditions} conditions]"
            )
            logger.info("breakout[{}]: {}", symbol, reasoning)
            return Signal(
                action="BUY",
                confidence=buy_score,
                symbol=symbol,
                strategy="breakout",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # SELL condition: breakout failure (binary — structural signal)
        if close < current_20bar_high and not _is_nan(current_20bar_high):
            reasoning = (
                f"SELL: price ({close:.2f}) below 20-bar rolling high ({current_20bar_high:.2f})"
                f" — breakout failure [score=0.60]"
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

        # --- HOLD with partial score for transparency ---
        reasoning = (
            f"HOLD: buy_score={buy_score:.2f} ({buy_conditions} conditions). "
            f"close={close:.2f}, 20-bar high={prior_20bar_high:.2f}, "
            f"volume={volume:.0f}, vol_avg={float(vol_avg):.0f}"
        )
        logger.debug("breakout[{}]: {}", symbol, reasoning)
        return Signal(
            action="HOLD",
            confidence=buy_score,
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
