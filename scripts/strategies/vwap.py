"""VWAP reversion trading strategy for the trading bot plugin.

Trades mean reversion relative to intraday VWAP (Volume Weighted Average Price).
Produces BUY signals when price drops > 1.5% below VWAP AND RSI < 40 AND time
is between 10:00-15:00 ET. Produces SELL signals when price returns to VWAP.

Stop-loss uses a percentage-based formula (not ATR * multiplier) because VWAP
reversion trades have a known target (VWAP itself) and a clear invalidation
level (max_deviation_pct further below VWAP).
"""
import math

import pandas as pd
from loguru import logger

from scripts.types import Signal


class VWAPStrategy:
    """VWAP reversion strategy: buy statistical deviations below VWAP.

    Entry (BUY): price > 1.5% below VWAP AND RSI < 40 AND time 10:00-15:00 ET.
    Exit (SELL): price returns to VWAP.
    Stop: percentage-based — close * (1 - max_deviation_pct / 100).
    """

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> Signal:
        """Generate a VWAP reversion trade signal.

        Args:
            df: Indicator-enriched DataFrame with timezone-aware DatetimeIndex
                (America/New_York). Must have VWAP_D and RSI columns.
            symbol: Ticker symbol.
            params: Strategy parameters with keys: rsi_period,
                deviation_threshold_pct, max_deviation_pct, atr_period,
                trading_start_hour, trading_end_hour.

        Returns:
            Signal with action BUY, SELL, or HOLD. Stop is percentage-based.
        """
        rsi_col = f"RSI_{params.get('rsi_period', 14)}"
        atr_col = f"ATRr_{params.get('atr_period', 14)}"
        deviation_threshold_pct = params.get("deviation_threshold_pct", 1.5)
        max_deviation_pct = params.get("max_deviation_pct", 3.0)
        trading_start_hour = params.get("trading_start_hour", 10)
        trading_end_hour = params.get("trading_end_hour", 15)

        # VWAP_D is the anchor column produced by pandas-ta vwap(anchor="D")
        vwap_col = "VWAP_D"

        if len(df) < 1:
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="vwap",
                atr=0.0,
                stop_price=0.0,
                reasoning="Insufficient data: empty DataFrame",
            )

        # Check required columns exist
        required_cols = [rsi_col, vwap_col, atr_col, "close"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.warning(
                "vwap[{}]: missing columns {} — returning HOLD", symbol, missing
            )
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="vwap",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Missing indicator columns: {missing}",
            )

        row = df.iloc[-1]

        # Check NaN on critical values
        critical_values = {
            rsi_col: row[rsi_col],
            vwap_col: row[vwap_col],
            atr_col: row[atr_col],
        }
        nan_keys = [k for k, v in critical_values.items() if _is_nan(v)]
        if nan_keys:
            logger.debug("vwap[{}]: NaN in {} — returning HOLD", symbol, nan_keys)
            return Signal(
                action="HOLD",
                confidence=0.0,
                symbol=symbol,
                strategy="vwap",
                atr=0.0,
                stop_price=0.0,
                reasoning=f"Insufficient data: NaN values in {nan_keys}",
            )

        atr = float(row[atr_col])
        close = float(row["close"])
        vwap = float(row[vwap_col])
        rsi = float(row[rsi_col])

        # Percentage-based stop (not ATR formula — VWAP strategy uses known deviation level)
        stop_price = round(close * (1 - max_deviation_pct / 100), 2)

        # Time check — index must be timezone-aware (America/New_York)
        last_timestamp = df.index[-1]
        try:
            hour = last_timestamp.hour
        except AttributeError:
            # Fallback for non-datetime index
            hour = 12  # assume mid-day if we can't determine

        in_trading_window = trading_start_hour <= hour < trading_end_hour

        # BUY conditions (all must be true)
        below_vwap_pct = (vwap - close) / vwap if vwap > 0 else 0.0
        price_below_vwap = below_vwap_pct > (deviation_threshold_pct / 100)
        rsi_weak = rsi < 40

        if price_below_vwap and rsi_weak and in_trading_window:
            reasoning = (
                f"BUY: price ({close:.2f}) is {below_vwap_pct * 100:.2f}% below "
                f"VWAP ({vwap:.2f}) (threshold {deviation_threshold_pct}%), "
                f"RSI weak ({rsi:.1f} < 40), "
                f"time within window ({hour}:xx ET)"
            )
            logger.info("vwap[{}]: {}", symbol, reasoning)
            return Signal(
                action="BUY",
                confidence=0.7,
                symbol=symbol,
                strategy="vwap",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # SELL condition: price returns to VWAP
        if close >= vwap:
            reasoning = (
                f"SELL: price ({close:.2f}) returned to VWAP ({vwap:.2f}) — target reached"
            )
            logger.info("vwap[{}]: {}", symbol, reasoning)
            return Signal(
                action="SELL",
                confidence=0.7,
                symbol=symbol,
                strategy="vwap",
                atr=atr,
                stop_price=stop_price,
                reasoning=reasoning,
            )

        # HOLD — explain which conditions weren't met
        reasons = []
        if not price_below_vwap:
            reasons.append(
                f"price deviation {below_vwap_pct * 100:.2f}% < {deviation_threshold_pct}% threshold"
            )
        if not rsi_weak:
            reasons.append(f"RSI not weak ({rsi:.1f} >= 40)")
        if not in_trading_window:
            reasons.append(
                f"outside trading window (hour={hour}, window={trading_start_hour}-{trading_end_hour})"
            )
        reasoning = "HOLD: " + "; ".join(reasons) if reasons else "HOLD: conditions not met"
        logger.debug("vwap[{}]: {}", symbol, reasoning)
        return Signal(
            action="HOLD",
            confidence=0.0,
            symbol=symbol,
            strategy="vwap",
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
