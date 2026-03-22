"""Momentum trading strategy for the trading bot plugin.

Trades in the direction of an existing trend by identifying when short-term
momentum aligns with medium-term direction. Produces BUY signals when RSI
recovers from oversold AND MACD histogram turns positive AND EMA short crosses
above EMA long AND volume exceeds the 20-bar average.
"""
import math

import pandas as pd
from loguru import logger

from scripts.strategies.base import BaseStrategy
from scripts.types import Signal


class MomentumStrategy(BaseStrategy):
    """Momentum strategy: trend-following via RSI, MACD, EMA crossover, and volume.

    Entry (BUY): RSI crosses above 30 AND MACD histogram positive AND EMA_short >
    EMA_long AND volume > 20-bar average.

    Exit (SELL): RSI > 70 OR MACD histogram negative, OR EMA_short < EMA_long.
    """

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> Signal:
        """Generate a momentum trade signal.

        Args:
            df: Indicator-enriched DataFrame. Must have at least 2 rows.
            symbol: Ticker symbol.
            params: Strategy parameters with keys: rsi_period, macd_fast,
                macd_slow, macd_signal, ema_short, ema_long, atr_period,
                atr_multiplier.

        Returns:
            Signal with action BUY, SELL, or HOLD.
        """
        # Derive column names programmatically from params
        rsi_col = f"RSI_{params.get('rsi_period', 14)}"
        macd_h_col = (
            f"MACDh_{params.get('macd_fast', 12)}_"
            f"{params.get('macd_slow', 26)}_"
            f"{params.get('macd_signal', 9)}"
        )
        ema_short_col = f"EMA_{params.get('ema_short', 9)}"
        ema_long_col = f"EMA_{params.get('ema_long', 21)}"
        atr_col = f"ATRr_{params.get('atr_period', 14)}"
        atr_multiplier = params.get("atr_multiplier", 1.5)

        # Need at least 2 rows for crossover detection
        if len(df) < 2:
            logger.debug(
                "momentum[{}]: insufficient rows ({}) — returning HOLD", symbol, len(df)
            )
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="momentum",
                atr=0.0,
                stop_price=0.0,
                reasoning="Insufficient data: need at least 2 rows for crossover detection",
            )

        row = df.iloc[-1]
        prev = df.iloc[-2]

        # Check required columns exist
        required_cols = [rsi_col, macd_h_col, ema_short_col, ema_long_col, atr_col, "close", "volume"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.warning("momentum[{}]: missing columns {} — returning HOLD", symbol, missing)
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="momentum",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Missing indicator columns: {missing}",
            )

        # Check for NaN on critical values
        critical_values = {
            rsi_col: row[rsi_col],
            f"prev_{rsi_col}": prev[rsi_col],
            macd_h_col: row[macd_h_col],
            ema_short_col: row[ema_short_col],
            ema_long_col: row[ema_long_col],
            atr_col: row[atr_col],
        }
        nan_keys = [k for k, v in critical_values.items() if _is_nan(v)]
        if nan_keys:
            logger.debug("momentum[{}]: NaN in {} — returning HOLD", symbol, nan_keys)
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="momentum",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Insufficient data: NaN values in {nan_keys}",
            )

        atr = float(row[atr_col])
        close = float(row["close"])
        stop_price = round(close - (atr * atr_multiplier), 2)

        # Volume above 20-bar rolling average
        vol_avg = df["volume"].rolling(20).mean().iloc[-1]
        high_volume = bool(row["volume"] > vol_avg) if not _is_nan(vol_avg) else False

        # BUY conditions (all must be true)
        rsi_cross_above_30 = float(row[rsi_col]) > 30 and float(prev[rsi_col]) <= 30
        macd_h_positive = float(row[macd_h_col]) > 0
        ema_bullish = float(row[ema_short_col]) > float(row[ema_long_col])

        buy_signal = rsi_cross_above_30 and macd_h_positive and ema_bullish and high_volume

        if buy_signal:
            reasoning = (
                f"BUY: RSI crossed above 30 ({float(prev[rsi_col]):.1f} -> {float(row[rsi_col]):.1f}), "
                f"MACD histogram positive ({float(row[macd_h_col]):.4f}), "
                f"EMA{params.get('ema_short', 9)} ({float(row[ema_short_col]):.2f}) > "
                f"EMA{params.get('ema_long', 21)} ({float(row[ema_long_col]):.2f}), "
                f"volume above 20-bar avg"
            )
            logger.info("momentum[{}]: {}", symbol, reasoning)
            return Signal(
                action="BUY",
                confidence=0.8,
                symbol=symbol,
                strategy="momentum",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # SELL conditions (any is sufficient)
        rsi_overbought = float(row[rsi_col]) > 70
        macd_h_negative = float(row[macd_h_col]) < 0
        ema_bearish = float(row[ema_short_col]) < float(row[ema_long_col])

        sell_signal = (rsi_overbought or macd_h_negative) or ema_bearish

        if sell_signal:
            reasons = []
            if rsi_overbought:
                reasons.append(f"RSI overbought ({float(row[rsi_col]):.1f} > 70)")
            if macd_h_negative:
                reasons.append(f"MACD histogram negative ({float(row[macd_h_col]):.4f})")
            if ema_bearish:
                reasons.append(
                    f"EMA{params.get('ema_short', 9)} ({float(row[ema_short_col]):.2f}) < "
                    f"EMA{params.get('ema_long', 21)} ({float(row[ema_long_col]):.2f})"
                )
            reasoning = "SELL: " + "; ".join(reasons)
            logger.info("momentum[{}]: {}", symbol, reasoning)
            return Signal(
                action="SELL",
                confidence=0.6,
                symbol=symbol,
                strategy="momentum",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # HOLD — conditions not met
        reasoning = (
            f"HOLD: RSI={float(row[rsi_col]):.1f}, "
            f"MACDh={float(row[macd_h_col]):.4f}, "
            f"EMA{params.get('ema_short', 9)}={float(row[ema_short_col]):.2f}, "
            f"EMA{params.get('ema_long', 21)}={float(row[ema_long_col]):.2f}, "
            f"high_volume={high_volume}"
        )
        logger.debug("momentum[{}]: {}", symbol, reasoning)
        return Signal(
            action="HOLD",
            confidence=0.0,
            symbol=symbol,
            strategy="momentum",
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
