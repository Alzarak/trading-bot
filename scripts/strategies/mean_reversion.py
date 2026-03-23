"""Mean reversion trading strategy for the trading bot plugin.

Trades the assumption that price deviates temporarily from its mean and will
revert. Produces BUY signals when price touches the lower Bollinger Band AND
RSI is below 30 AND price is within 2% of the lower band. Produces SELL signals
when price returns to the middle Bollinger Band.
"""
import math

import pandas as pd
from loguru import logger

from scripts.strategies.base import BaseStrategy
from scripts.models import Signal


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy: buy oversold price deviations, sell at mean.

    Entry (BUY): price <= lower BB AND RSI < 30 AND price within 2% of lower band.
    Exit (SELL): price returns to middle BB (the mean).
    """

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> Signal:
        """Generate a mean reversion trade signal.

        Args:
            df: Indicator-enriched DataFrame. Must have at least 1 row.
            symbol: Ticker symbol.
            params: Strategy parameters with keys: rsi_period, bb_period,
                bb_std_dev, atr_period, atr_multiplier.

        Returns:
            Signal with action BUY, SELL, or HOLD.
        """
        # Derive column names programmatically from params
        rsi_col = f"RSI_{params.get('rsi_period', 14)}"
        atr_col = f"ATRr_{params.get('atr_period', 14)}"
        atr_multiplier = params.get("atr_multiplier", 1.5)

        bb_period = params.get("bb_period", 20)
        bb_std = params.get("bb_std_dev", 2.0)
        # pandas-ta 0.4.71b0 BBands columns: BBL_{period}_{std}_{std} — std appears twice
        bb_suffix = f"{bb_period}_{bb_std}_{bb_std}"
        bb_lower_col = f"BBL_{bb_suffix}"
        bb_middle_col = f"BBM_{bb_suffix}"

        if len(df) < 1:
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="mean_reversion",
                atr=0.0,
                stop_price=0.0,
                reasoning="Insufficient data: empty DataFrame",
            )

        row = df.iloc[-1]

        # Check required columns exist
        required_cols = [rsi_col, bb_lower_col, bb_middle_col, atr_col, "close"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.warning(
                "mean_reversion[{}]: missing columns {} — returning HOLD", symbol, missing
            )
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="mean_reversion",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Missing indicator columns: {missing}",
            )

        # Check for NaN on critical values
        critical_values = {
            rsi_col: row[rsi_col],
            bb_lower_col: row[bb_lower_col],
            bb_middle_col: row[bb_middle_col],
            atr_col: row[atr_col],
        }
        nan_keys = [k for k, v in critical_values.items() if _is_nan(v)]
        if nan_keys:
            logger.debug(
                "mean_reversion[{}]: NaN in {} — returning HOLD", symbol, nan_keys
            )
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="mean_reversion",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Insufficient data: NaN values in {nan_keys}",
            )

        atr = float(row[atr_col])
        close = float(row["close"])
        stop_price = round(close - (atr * atr_multiplier), 2)
        bb_lower = float(row[bb_lower_col])
        bb_middle = float(row[bb_middle_col])
        rsi = float(row[rsi_col])

        # --- BUY scoring (weighted) ---
        buy_score = 0.0
        buy_reasons: list[str] = []
        buy_conditions = 0

        # Condition 1: Near lower band (relaxed from "at or below" to within 3%)
        pct_from_lower = abs(close - bb_lower) / bb_lower if bb_lower > 0 else 1.0
        if pct_from_lower <= 0.03:
            buy_score += 0.30
            buy_conditions += 1
            buy_reasons.append(f"price within 3% of lower BB ({pct_from_lower * 100:.2f}%)")

        # Bonus: actually at or below lower band
        if close <= bb_lower:
            buy_score += 0.10
            buy_reasons.append(f"price at/below lower BB ({close:.2f} <= {bb_lower:.2f})")

        # Condition 2: RSI weak (relaxed from < 30 to < 40)
        if rsi < 40:
            buy_score += 0.25
            buy_conditions += 1
            buy_reasons.append(f"RSI weak ({rsi:.1f} < 40)")

        # Bonus: RSI truly oversold
        if rsi < 30:
            buy_score += 0.10
            buy_reasons.append(f"RSI oversold ({rsi:.1f} < 30)")

        # Condition 3: Price below middle band
        if close < bb_middle:
            buy_score += 0.25
            buy_conditions += 1
            buy_reasons.append(f"price below middle BB ({close:.2f} < {bb_middle:.2f})")

        # Condition 4: Volume declining (sellers exhausted, optional)
        if "volume" in df.columns and len(df) >= 20:
            vol_avg = df["volume"].rolling(20).mean().iloc[-1]
            if not _is_nan(vol_avg) and float(row["volume"]) < float(vol_avg):
                buy_score += 0.10
                buy_conditions += 1
                buy_reasons.append("volume declining (sellers may be exhausted)")

        buy_score = min(buy_score, 1.0)

        # 2-of-N gate: need at least 2 conditions to produce a BUY
        if buy_conditions >= 2 and buy_score > 0:
            reasoning = (
                "BUY: " + "; ".join(buy_reasons)
                + f" [score={buy_score:.2f}, {buy_conditions} conditions]"
            )
            logger.info("mean_reversion[{}]: {}", symbol, reasoning)
            return Signal(
                action="BUY",
                confidence=buy_score,
                symbol=symbol,
                strategy="mean_reversion",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # SELL condition: price returns to middle band (binary — target reached)
        if close >= bb_middle:
            reasoning = (
                f"SELL: price ({close:.2f}) returned to middle BB / mean ({bb_middle:.2f})"
                f" [score=0.70]"
            )
            logger.info("mean_reversion[{}]: {}", symbol, reasoning)
            return Signal(
                action="SELL",
                confidence=0.7,
                symbol=symbol,
                strategy="mean_reversion",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # --- HOLD with partial score for transparency ---
        reasoning = (
            f"HOLD: buy_score={buy_score:.2f} ({buy_conditions} conditions). "
            f"RSI={rsi:.1f}, close={close:.2f}, "
            f"lower_BB={bb_lower:.2f}, middle_BB={bb_middle:.2f}"
        )
        logger.debug("mean_reversion[{}]: {}", symbol, reasoning)
        return Signal(
            action="HOLD",
            confidence=buy_score,
            symbol=symbol,
            strategy="mean_reversion",
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
