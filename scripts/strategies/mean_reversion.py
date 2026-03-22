"""Mean reversion trading strategy for the trading bot plugin.

Trades the assumption that price deviates temporarily from its mean and will
revert. Produces BUY signals when price touches the lower Bollinger Band AND
RSI is below 30 AND price is within 2% of the lower band. Produces SELL signals
when price returns to the middle Bollinger Band.
"""
import math

import pandas as pd
from loguru import logger

from scripts.types import Signal


class MeanReversionStrategy:
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

        # BUY conditions (all must be true)
        at_or_below_lower_band = close <= bb_lower
        rsi_oversold = rsi < 30
        within_2pct_of_lower = abs(close - bb_lower) / bb_lower <= 0.02

        if at_or_below_lower_band and rsi_oversold and within_2pct_of_lower:
            reasoning = (
                f"BUY: price ({close:.2f}) at/below lower BB ({bb_lower:.2f}), "
                f"RSI oversold ({rsi:.1f} < 30), "
                f"within 2% of lower band ({abs(close - bb_lower) / bb_lower * 100:.2f}%)"
            )
            logger.info("mean_reversion[{}]: {}", symbol, reasoning)
            return Signal(
                action="BUY",
                confidence=0.75,
                symbol=symbol,
                strategy="mean_reversion",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # SELL condition: price returns to middle band
        if close >= bb_middle:
            reasoning = (
                f"SELL: price ({close:.2f}) returned to middle BB / mean ({bb_middle:.2f})"
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

        # HOLD
        reasons = []
        if not at_or_below_lower_band:
            reasons.append(f"price ({close:.2f}) above lower BB ({bb_lower:.2f})")
        if not rsi_oversold:
            reasons.append(f"RSI not oversold ({rsi:.1f} >= 30)")
        if not within_2pct_of_lower:
            reasons.append(
                f"price too far from lower band ({abs(close - bb_lower) / bb_lower * 100:.2f}% > 2%)"
            )
        reasoning = "HOLD: " + "; ".join(reasons) if reasons else "HOLD: conditions not met"
        logger.debug("mean_reversion[{}]: {}", symbol, reasoning)
        return Signal(
            action="HOLD",
            confidence=0.0,
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
