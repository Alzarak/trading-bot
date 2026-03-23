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
from scripts.models import Signal


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

        # Extract indicator values as local floats
        rsi = float(row[rsi_col])
        prev_rsi = float(prev[rsi_col])
        macd_h = float(row[macd_h_col])
        prev_macd_h = float(prev[macd_h_col]) if not _is_nan(prev[macd_h_col]) else macd_h
        ema_s = float(row[ema_short_col])
        ema_l = float(row[ema_long_col])

        # Volume above 20-bar rolling average
        vol_avg = df["volume"].rolling(20).mean().iloc[-1]
        high_volume = bool(row["volume"] > vol_avg) if not _is_nan(vol_avg) else False

        # --- BUY scoring (weighted) ---
        buy_score = 0.0
        buy_reasons: list[str] = []
        buy_conditions = 0

        # Condition 1: RSI recovering (relaxed from strict cross-above-30)
        if rsi < 45 and rsi > prev_rsi:
            buy_score += 0.25
            buy_conditions += 1
            buy_reasons.append(f"RSI recovering ({rsi:.1f}, rising from {prev_rsi:.1f})")

        # Bonus: classic RSI oversold bounce
        if rsi > 30 and prev_rsi <= 30:
            buy_score += 0.10
            buy_reasons.append(f"RSI crossed above 30 ({prev_rsi:.1f}->{rsi:.1f})")

        # Condition 2: MACD histogram positive (or improving)
        if macd_h > 0:
            buy_score += 0.25
            buy_conditions += 1
            buy_reasons.append(f"MACD histogram positive ({macd_h:.4f})")
        elif macd_h > prev_macd_h:
            buy_score += 0.10
            buy_conditions += 1
            buy_reasons.append(f"MACD histogram improving ({prev_macd_h:.4f}->{macd_h:.4f})")

        # Condition 3: EMA bullish
        if ema_s > ema_l:
            buy_score += 0.25
            buy_conditions += 1
            buy_reasons.append(
                f"EMA{params.get('ema_short', 9)} ({ema_s:.2f}) > "
                f"EMA{params.get('ema_long', 21)} ({ema_l:.2f})"
            )

        # Condition 4: Volume above average
        if high_volume:
            buy_score += 0.15
            buy_conditions += 1
            buy_reasons.append("volume above 20-bar avg")

        buy_score = min(buy_score, 1.0)

        # 2-of-N gate: need at least 2 conditions to produce a BUY
        if buy_conditions >= 2 and buy_score > 0:
            reasoning = (
                "BUY: " + "; ".join(buy_reasons)
                + f" [score={buy_score:.2f}, {buy_conditions} conditions]"
            )
            logger.info("momentum[{}]: {}", symbol, reasoning)
            return Signal(
                action="BUY",
                confidence=buy_score,
                symbol=symbol,
                strategy="momentum",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # --- SELL scoring (weighted, 2-of-3 gate) ---
        sell_score = 0.0
        sell_reasons: list[str] = []
        sell_conditions = 0

        if rsi > 70:
            sell_score += 0.35
            sell_conditions += 1
            sell_reasons.append(f"RSI overbought ({rsi:.1f})")
        if macd_h < 0:
            sell_score += 0.35
            sell_conditions += 1
            sell_reasons.append(f"MACD histogram negative ({macd_h:.4f})")
        if ema_s < ema_l:
            sell_score += 0.30
            sell_conditions += 1
            sell_reasons.append(
                f"EMA{params.get('ema_short', 9)} ({ema_s:.2f}) < "
                f"EMA{params.get('ema_long', 21)} ({ema_l:.2f})"
            )

        sell_score = min(sell_score, 1.0)

        if sell_conditions >= 2 and sell_score > 0:
            reasoning = (
                "SELL: " + "; ".join(sell_reasons)
                + f" [score={sell_score:.2f}]"
            )
            logger.info("momentum[{}]: {}", symbol, reasoning)
            return Signal(
                action="SELL",
                confidence=sell_score,
                symbol=symbol,
                strategy="momentum",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # --- HOLD with partial score for transparency ---
        reasoning = (
            f"HOLD: buy_score={buy_score:.2f} ({buy_conditions} conditions), "
            f"sell_score={sell_score:.2f} ({sell_conditions} conditions). "
            f"RSI={rsi:.1f}, MACDh={macd_h:.4f}, "
            f"EMA_s={ema_s:.2f}, EMA_l={ema_l:.2f}, high_volume={high_volume}"
        )
        logger.debug("momentum[{}]: {}", symbol, reasoning)
        return Signal(
            action="HOLD",
            confidence=buy_score,
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
