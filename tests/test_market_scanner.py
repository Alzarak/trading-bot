"""Tests for MarketScanner and all 6 technical indicators.

Tests use mocked Alpaca clients — no real API calls are made.
"""
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ET = ZoneInfo("America/New_York")


@pytest.fixture
def synthetic_ohlcv():
    """100-row minute OHLCV DataFrame with a timezone-aware (ET) DatetimeIndex.

    Prices are a random walk starting at 150.0. Volume and trade_count are
    constant. The vwap column is included because pandas-ta vwap() reads it
    from the DataFrame when present.
    """
    rng = np.random.default_rng(seed=42)
    n = 100

    # Build a timezone-aware DatetimeIndex at 1-minute intervals
    start = pd.Timestamp("2024-01-15 09:30:00", tz="America/New_York")
    index = pd.date_range(start=start, periods=n, freq="1min", tz="America/New_York")

    # Random-walk close prices
    returns = rng.normal(loc=0, scale=0.002, size=n)
    close = np.cumprod(1 + returns) * 150.0

    # OHLCV with realistic spread
    high = close * (1 + rng.uniform(0, 0.005, size=n))
    low = close * (1 - rng.uniform(0, 0.005, size=n))
    open_ = low + rng.uniform(0, 1, size=n) * (high - low)
    volume = rng.integers(1000, 10000, size=n).astype(float)
    trade_count = rng.integers(50, 500, size=n).astype(float)
    vwap = (open_ + high + low + close) / 4  # typical price proxy

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "trade_count": trade_count,
            "vwap": vwap,
        },
        index=index,
    )


@pytest.fixture
def scanner_with_defaults(sample_config):
    """MarketScanner with default params from sample_config fixture."""
    from scripts.market_scanner import MarketScanner

    trading_client = MagicMock()
    data_client = MagicMock()
    return MarketScanner(trading_client, data_client, sample_config)


@pytest.fixture
def scanner_custom_params():
    """MarketScanner with custom strategy_params to verify column name mapping."""
    from scripts.market_scanner import MarketScanner

    config = {
        "strategy_params": {
            "rsi_period": 7,
            "macd_fast": 8,
            "macd_slow": 17,
            "macd_signal": 5,
            "ema_short": 5,
            "ema_long": 10,
            "atr_period": 7,
            "bb_period": 10,
            "bb_std_dev": 1.5,
        }
    }
    return MarketScanner(MagicMock(), MagicMock(), config)


# ---------------------------------------------------------------------------
# TestIndicators
# ---------------------------------------------------------------------------


class TestIndicators:
    """Verify that compute_indicators() appends all 6 indicator groups."""

    def test_rsi(self, scanner_with_defaults, synthetic_ohlcv):
        result = scanner_with_defaults.compute_indicators(synthetic_ohlcv.copy())
        assert "RSI_14" in result.columns, "RSI_14 column missing"
        assert result["RSI_14"].between(0, 100).all(), "RSI values must be in [0, 100]"

    def test_macd(self, scanner_with_defaults, synthetic_ohlcv):
        result = scanner_with_defaults.compute_indicators(synthetic_ohlcv.copy())
        assert "MACD_12_26_9" in result.columns, "MACD_12_26_9 column missing"
        assert "MACDh_12_26_9" in result.columns, "MACDh_12_26_9 column missing"
        assert "MACDs_12_26_9" in result.columns, "MACDs_12_26_9 column missing"

    def test_ema(self, scanner_with_defaults, synthetic_ohlcv):
        result = scanner_with_defaults.compute_indicators(synthetic_ohlcv.copy())
        assert "EMA_9" in result.columns, "EMA_9 column missing"
        assert "EMA_21" in result.columns, "EMA_21 column missing"
        # EMA values should be positive and within price range
        assert (result["EMA_9"] > 0).all()
        assert (result["EMA_21"] > 0).all()

    def test_atr(self, scanner_with_defaults, synthetic_ohlcv):
        result = scanner_with_defaults.compute_indicators(synthetic_ohlcv.copy())
        # ATR column must be ATRr_14, NOT ATR_14
        assert "ATRr_14" in result.columns, "ATRr_14 column missing (not ATR_14)"
        assert "ATR_14" not in result.columns, "ATR_14 column should not exist — use ATRr_14"
        assert (result["ATRr_14"] > 0).all(), "ATR values must be positive"

    def test_bbands(self, scanner_with_defaults, synthetic_ohlcv):
        result = scanner_with_defaults.compute_indicators(synthetic_ohlcv.copy())
        # pandas-ta 0.4.71b0 names BBands columns BBL_{period}_{std}_{std}
        assert "BBL_20_2.0_2.0" in result.columns, "BBL_20_2.0_2.0 column missing"
        assert "BBM_20_2.0_2.0" in result.columns, "BBM_20_2.0_2.0 column missing"
        assert "BBU_20_2.0_2.0" in result.columns, "BBU_20_2.0_2.0 column missing"
        # Band ordering: lower < middle < upper
        assert (result["BBL_20_2.0_2.0"] < result["BBM_20_2.0_2.0"]).all(), "BBL must be < BBM"
        assert (result["BBM_20_2.0_2.0"] < result["BBU_20_2.0_2.0"]).all(), "BBM must be < BBU"

    def test_vwap(self, scanner_with_defaults, synthetic_ohlcv):
        """VWAP column exists when DatetimeIndex is already timezone-aware."""
        result = scanner_with_defaults.compute_indicators(synthetic_ohlcv.copy())
        assert "VWAP_D" in result.columns, "VWAP_D column missing"
        assert (result["VWAP_D"] > 0).all(), "VWAP values must be positive"

    def test_vwap_requires_tz(self, scanner_with_defaults, synthetic_ohlcv):
        """compute_indicators handles naive DatetimeIndex without crashing."""
        # Strip timezone from the index
        naive_df = synthetic_ohlcv.copy()
        naive_df.index = naive_df.index.tz_localize(None)  # make naive
        assert naive_df.index.tz is None, "Index should be naive before test"

        # Should not raise — scanner localizes naive index automatically
        result = scanner_with_defaults.compute_indicators(naive_df)
        assert "VWAP_D" in result.columns, "VWAP_D column missing for naive-index input"
        assert result.index.tz is not None, "Index should be tz-aware after compute_indicators"

    def test_nan_dropped(self, scanner_with_defaults, synthetic_ohlcv):
        """No NaN values remain in the result after compute_indicators."""
        result = scanner_with_defaults.compute_indicators(synthetic_ohlcv.copy())
        assert not result.isnull().any().any(), "NaN values found — dropna() must remove all"


# ---------------------------------------------------------------------------
# TestMarketClock
# ---------------------------------------------------------------------------


class TestMarketClock:
    def test_market_open(self, scanner_with_defaults):
        clock = MagicMock()
        clock.is_open = True
        scanner_with_defaults.trading_client.get_clock.return_value = clock

        assert scanner_with_defaults.is_market_open() is True

    def test_market_closed(self, scanner_with_defaults):
        clock = MagicMock()
        clock.is_open = False
        scanner_with_defaults.trading_client.get_clock.return_value = clock

        assert scanner_with_defaults.is_market_open() is False


# ---------------------------------------------------------------------------
# TestGetIndicatorColumns
# ---------------------------------------------------------------------------


class TestGetIndicatorColumns:
    def test_default_columns(self, scanner_with_defaults):
        cols = scanner_with_defaults.get_indicator_columns()
        assert cols["rsi"] == "RSI_14"
        assert cols["macd"] == "MACD_12_26_9"
        assert cols["macd_histogram"] == "MACDh_12_26_9"
        assert cols["macd_signal"] == "MACDs_12_26_9"
        assert cols["ema_short"] == "EMA_9"
        assert cols["ema_long"] == "EMA_21"
        assert cols["atr"] == "ATRr_14"  # NOTE: ATRr, not ATR
        # pandas-ta 0.4.71b0: BBands columns include std twice in name
        assert cols["bb_lower"] == "BBL_20_2.0_2.0"
        assert cols["bb_middle"] == "BBM_20_2.0_2.0"
        assert cols["bb_upper"] == "BBU_20_2.0_2.0"
        assert cols["vwap"] == "VWAP_D"

    def test_custom_params(self, scanner_custom_params):
        cols = scanner_custom_params.get_indicator_columns()
        assert cols["rsi"] == "RSI_7"
        assert cols["macd"] == "MACD_8_17_5"
        assert cols["macd_histogram"] == "MACDh_8_17_5"
        assert cols["macd_signal"] == "MACDs_8_17_5"
        assert cols["ema_short"] == "EMA_5"
        assert cols["ema_long"] == "EMA_10"
        assert cols["atr"] == "ATRr_7"
        # pandas-ta 0.4.71b0: BBands columns include std twice in name
        assert cols["bb_lower"] == "BBL_10_1.5_1.5"
        assert cols["bb_middle"] == "BBM_10_1.5_1.5"
        assert cols["bb_upper"] == "BBU_10_1.5_1.5"
