"""Unit tests for all 4 trading strategies and the STRATEGY_REGISTRY.

Each test class creates synthetic DataFrames with crafted indicator values to
trigger specific BUY, SELL, and HOLD signals. Tests verify Signal fields:
action, strategy name, atr, stop_price, and reasoning.
"""
import pandas as pd
import numpy as np
import pytest
from zoneinfo import ZoneInfo

from scripts.strategies import STRATEGY_REGISTRY, BaseStrategy
from scripts.strategies.momentum import MomentumStrategy
from scripts.strategies.mean_reversion import MeanReversionStrategy
from scripts.strategies.breakout import BreakoutStrategy
from scripts.strategies.vwap import VWAPStrategy
from scripts.models import Signal

ET = ZoneInfo("America/New_York")

# Default params for all tests
DEFAULT_PARAMS = {
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ema_short": 9,
    "ema_long": 21,
    "atr_period": 14,
    "bb_period": 20,
    "bb_std_dev": 2.0,
    "atr_multiplier": 1.5,
    "max_deviation_pct": 3.0,
    "lookback_period": 20,
    "volume_multiplier": 1.5,
    "deviation_threshold_pct": 1.5,
    "trading_start_hour": 10,
    "trading_end_hour": 15,
}


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def make_datetime_index(n: int, hour: int = 11) -> pd.DatetimeIndex:
    """Create an ET-aware DatetimeIndex with n entries starting at the given hour."""
    base = pd.Timestamp(f"2024-01-15 {hour:02d}:00:00", tz=ET)
    return pd.DatetimeIndex(
        [base + pd.Timedelta(minutes=i) for i in range(n)],
    )


def make_base_df(n: int = 50, base_price: float = 100.0, hour: int = 11) -> pd.DataFrame:
    """Create a base OHLCV DataFrame with n rows."""
    idx = make_datetime_index(n, hour=hour)
    # Slightly random close prices centered around base_price
    rng = np.random.default_rng(42)
    closes = base_price + rng.normal(0, 0.5, n).cumsum()
    closes = np.abs(closes)  # ensure positive
    df = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": closes * 1.002,
            "low": closes * 0.998,
            "close": closes,
            "volume": np.full(n, 100_000.0),
            "trade_count": np.full(n, 500),
            "vwap": closes,
        },
        index=idx,
    )
    return df


def add_momentum_indicators(
    df: pd.DataFrame,
    rsi_last: float = 32.0,
    rsi_prev: float = 28.0,
    macd_h: float = 0.05,
    ema_short: float = 101.0,
    ema_long: float = 100.0,
    atr: float = 1.5,
) -> pd.DataFrame:
    """Add momentum indicator columns with controlled last-row values."""
    n = len(df)
    # Build gradual series, set last two rows explicitly for crossover detection
    rsi_series = np.linspace(25, 35, n)
    rsi_series[-2] = rsi_prev
    rsi_series[-1] = rsi_last

    macd_h_series = np.full(n, macd_h)
    ema_short_series = np.full(n, ema_short)
    ema_long_series = np.full(n, ema_long)
    atr_series = np.full(n, atr)

    df = df.copy()
    df["RSI_14"] = rsi_series
    df["MACDh_12_26_9"] = macd_h_series
    df["MACD_12_26_9"] = macd_h_series * 0.5
    df["MACDs_12_26_9"] = macd_h_series * 0.3
    df["EMA_9"] = ema_short_series
    df["EMA_21"] = ema_long_series
    df["ATRr_14"] = atr_series
    # Add BB and VWAP so they don't interfere
    df["BBL_20_2.0_2.0"] = df["close"] * 0.97
    df["BBM_20_2.0_2.0"] = df["close"]
    df["BBU_20_2.0_2.0"] = df["close"] * 1.03
    df["VWAP_D"] = df["close"]
    return df


# ---------------------------------------------------------------------------
# Fixtures: Momentum
# ---------------------------------------------------------------------------

@pytest.fixture
def buy_momentum_df():
    """BUY: RSI crosses above 30, MACD histogram positive, EMA_9 > EMA_21, high volume."""
    df = make_base_df(n=50, base_price=100.0)
    df = add_momentum_indicators(
        df,
        rsi_last=32.0,   # crosses above 30
        rsi_prev=28.0,   # prev was below 30
        macd_h=0.05,     # positive
        ema_short=101.0, # short > long
        ema_long=100.0,
        atr=1.5,
    )
    # Set prior bars to 100k average, last bar to 300k — clearly above 20-bar avg
    df["volume"] = 100_000.0
    df.iloc[-1, df.columns.get_loc("volume")] = 300_000.0  # 3x average
    return df


@pytest.fixture
def sell_momentum_df():
    """SELL: RSI > 70 and MACD histogram negative."""
    df = make_base_df(n=50, base_price=100.0)
    df = add_momentum_indicators(
        df,
        rsi_last=75.0,   # overbought
        rsi_prev=72.0,   # was already high (no cross above 30)
        macd_h=-0.05,    # negative
        ema_short=101.0,
        ema_long=100.0,
        atr=1.5,
    )
    return df


@pytest.fixture
def hold_momentum_df():
    """HOLD: only 1 condition met (EMA bullish) — below 2-of-N gate."""
    df = make_base_df(n=50, base_price=100.0)
    df = add_momentum_indicators(
        df,
        rsi_last=55.0,   # not < 45 — RSI recovering doesn't fire
        rsi_prev=56.0,   # falling, not rising
        macd_h=-0.10,    # negative — not positive, not improving
        ema_short=101.0, # bullish — 1 condition
        ema_long=100.0,
        atr=1.5,
    )
    return df


@pytest.fixture
def partial_buy_momentum_df():
    """Partial BUY: 2 conditions met (MACD positive + EMA bullish), proportional score."""
    df = make_base_df(n=50, base_price=100.0)
    df = add_momentum_indicators(
        df,
        rsi_last=55.0,   # not < 45 — RSI recovering doesn't fire
        rsi_prev=54.0,
        macd_h=0.05,     # positive — condition met
        ema_short=101.0, # bullish — condition met
        ema_long=100.0,
        atr=1.5,
    )
    df["volume"] = 100_000.0  # not above average (avg == last)
    return df


# ---------------------------------------------------------------------------
# Fixtures: Mean Reversion
# ---------------------------------------------------------------------------

@pytest.fixture
def buy_mean_reversion_df():
    """BUY: price below lower BB, RSI < 30, within 2% of lower band."""
    df = make_base_df(n=50, base_price=100.0)
    n = len(df)
    close = 97.0  # below lower band
    df["close"] = close
    df["open"] = close * 0.999
    df["high"] = close * 1.002
    df["low"] = close * 0.998

    df["RSI_14"] = 28.0          # < 30, oversold
    df["ATRr_14"] = 1.5
    # Lower band slightly above close — within 2%
    lower = 97.5                  # close is 97.0, lower is 97.5 → close < lower_band
    df["BBL_20_2.0_2.0"] = lower
    df["BBM_20_2.0_2.0"] = 100.0
    df["BBU_20_2.0_2.0"] = 103.0
    df["VWAP_D"] = 100.0
    df["MACDh_12_26_9"] = 0.0
    df["MACD_12_26_9"] = 0.0
    df["MACDs_12_26_9"] = 0.0
    df["EMA_9"] = 100.0
    df["EMA_21"] = 100.0
    return df


@pytest.fixture
def sell_mean_reversion_df():
    """SELL: price at or above middle BB."""
    df = make_base_df(n=50, base_price=100.0)
    close = 100.5  # at middle band
    df["close"] = close
    df["open"] = close * 0.999
    df["high"] = close * 1.002
    df["low"] = close * 0.998

    df["RSI_14"] = 50.0          # neutral
    df["ATRr_14"] = 1.5
    df["BBL_20_2.0_2.0"] = 97.0
    df["BBM_20_2.0_2.0"] = 100.0  # close >= middle band → SELL
    df["BBU_20_2.0_2.0"] = 103.0
    df["VWAP_D"] = 100.0
    df["MACDh_12_26_9"] = 0.0
    df["MACD_12_26_9"] = 0.0
    df["MACDs_12_26_9"] = 0.0
    df["EMA_9"] = 100.0
    df["EMA_21"] = 100.0
    return df


@pytest.fixture
def hold_mean_reversion_df():
    """HOLD: only 1 condition met (price below middle BB) — below 2-of-N gate."""
    df = make_base_df(n=50, base_price=100.0)
    close = 99.0  # far from lower band, below middle band
    df["close"] = close
    df["open"] = close * 0.999
    df["high"] = close * 1.002
    df["low"] = close * 0.998

    df["RSI_14"] = 55.0          # NOT < 40
    df["ATRr_14"] = 1.5
    df["BBL_20_2.0_2.0"] = 95.0  # |99-95|/95 = 4.2% > 3% — near_lower_band NOT met
    df["BBM_20_2.0_2.0"] = 100.0  # close < middle → 1 condition
    df["BBU_20_2.0_2.0"] = 105.0
    df["VWAP_D"] = 100.0
    df["MACDh_12_26_9"] = 0.0
    df["MACD_12_26_9"] = 0.0
    df["MACDs_12_26_9"] = 0.0
    df["EMA_9"] = 100.0
    df["EMA_21"] = 100.0
    return df


# ---------------------------------------------------------------------------
# Fixtures: Breakout
# ---------------------------------------------------------------------------

def make_breakout_df(n: int = 50, close_last: float = 105.0, volume_last: float = 200_000.0) -> pd.DataFrame:
    """Create a DataFrame crafted for breakout strategy testing."""
    idx = make_datetime_index(n)
    # Previous 49 bars have close around 100
    closes = np.full(n, 100.0, dtype=float)
    volumes = np.full(n, 100_000.0, dtype=float)
    highs = closes * 1.002
    # Last bar is the breakout bar
    closes[-1] = close_last
    highs[-1] = close_last * 1.001
    volumes[-1] = volume_last

    df = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": highs,
            "low": closes * 0.998,
            "close": closes,
            "volume": volumes,
            "trade_count": np.full(n, 500),
            "vwap": closes,
        },
        index=idx,
    )
    df["ATRr_14"] = 1.5
    df["RSI_14"] = 55.0
    df["MACDh_12_26_9"] = 0.05
    df["MACD_12_26_9"] = 0.1
    df["MACDs_12_26_9"] = 0.05
    df["EMA_9"] = 100.5
    df["EMA_21"] = 100.0
    df["BBL_20_2.0_2.0"] = 97.0
    df["BBM_20_2.0_2.0"] = 100.0
    df["BBU_20_2.0_2.0"] = 103.0
    df["VWAP_D"] = 100.0
    return df


@pytest.fixture
def buy_breakout_df():
    """BUY: price makes new 20-bar high, volume > 1.5x average."""
    # 20-bar prior high is ~100.2 (100 * 1.002), last close is 105
    # volume average is 100k, last bar volume is 200k (2x > 1.5x)
    return make_breakout_df(close_last=105.0, volume_last=200_000.0)


@pytest.fixture
def no_buy_breakout_df():
    """No BUY: price below high, normal volume → SELL (breakout failure) not BUY."""
    df = make_breakout_df(close_last=98.0, volume_last=100_000.0)
    # close=98.0 < 20-bar high 100.2 → breakout failure → SELL (binary)
    # BUY conditions: no new high, not near high (2.2%), no elevated volume → no BUY
    return df


# ---------------------------------------------------------------------------
# Fixtures: VWAP
# ---------------------------------------------------------------------------

def make_vwap_df(
    n: int = 50,
    close: float = 98.0,
    vwap: float = 100.0,
    rsi: float = 35.0,
    hour: int = 11,
) -> pd.DataFrame:
    """Create a DataFrame crafted for VWAP strategy testing."""
    idx = make_datetime_index(n, hour=hour)
    closes = np.full(n, close)

    df = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": closes * 1.002,
            "low": closes * 0.998,
            "close": closes,
            "volume": np.full(n, 100_000.0),
            "trade_count": np.full(n, 500),
        },
        index=idx,
    )
    df["VWAP_D"] = vwap
    df["RSI_14"] = rsi
    df["ATRr_14"] = 1.5
    df["MACDh_12_26_9"] = 0.0
    df["MACD_12_26_9"] = 0.0
    df["MACDs_12_26_9"] = 0.0
    df["EMA_9"] = vwap
    df["EMA_21"] = vwap
    df["BBL_20_2.0_2.0"] = vwap * 0.97
    df["BBM_20_2.0_2.0"] = vwap
    df["BBU_20_2.0_2.0"] = vwap * 1.03
    return df


@pytest.fixture
def buy_vwap_df():
    """BUY: price 2% below VWAP, RSI 35, hour 11."""
    # close=98, vwap=100 → deviation = (100-98)/100 = 2% > 1.5% threshold
    return make_vwap_df(close=98.0, vwap=100.0, rsi=35.0, hour=11)


@pytest.fixture
def hold_vwap_wrong_time_df():
    """HOLD: only 1 condition met (below VWAP) — RSI neutral, outside window."""
    return make_vwap_df(close=98.0, vwap=100.0, rsi=50.0, hour=16)


@pytest.fixture
def buy_vwap_df_for_stop_check():
    """BUY signal used to verify stop_price uses percentage formula."""
    return make_vwap_df(close=98.0, vwap=100.0, rsi=35.0, hour=11)


# ---------------------------------------------------------------------------
# Tests: Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_four_strategies_registered(self):
        assert len(STRATEGY_REGISTRY) == 4

    def test_load_by_config_name(self):
        cls = STRATEGY_REGISTRY["momentum"]
        strategy = cls()
        assert isinstance(strategy, MomentumStrategy)

    def test_all_subclass_base(self):
        for name, cls in STRATEGY_REGISTRY.items():
            assert issubclass(cls, BaseStrategy), (
                f"STRATEGY_REGISTRY['{name}'] ({cls}) is not a subclass of BaseStrategy"
            )

    def test_registry_keys(self):
        assert set(STRATEGY_REGISTRY.keys()) == {
            "momentum", "mean_reversion", "breakout", "vwap"
        }

    def test_each_strategy_instantiates(self):
        for name, cls in STRATEGY_REGISTRY.items():
            instance = cls()
            assert hasattr(instance, "generate_signal"), (
                f"{name} strategy missing generate_signal method"
            )


# ---------------------------------------------------------------------------
# Tests: Momentum
# ---------------------------------------------------------------------------

class TestMomentum:
    def test_buy_signal(self, buy_momentum_df):
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(buy_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.action == "BUY"
        assert 0.5 <= signal.confidence <= 1.0
        assert signal.strategy == "momentum"
        assert signal.symbol == "AAPL"
        assert isinstance(signal.reasoning, str) and len(signal.reasoning) > 0

    def test_all_conditions_high_confidence(self, buy_momentum_df):
        """All conditions met should produce high confidence (>= 0.7)."""
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(buy_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.action == "BUY"
        assert signal.confidence >= 0.7

    def test_sell_signal(self, sell_momentum_df):
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(sell_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.action == "SELL"
        assert 0.3 <= signal.confidence <= 1.0
        assert signal.strategy == "momentum"

    def test_hold_single_condition(self, hold_momentum_df):
        """Only 1 condition met — below 2-of-N gate, should be HOLD."""
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(hold_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.action == "HOLD"
        assert signal.strategy == "momentum"

    def test_partial_conditions_buy(self, partial_buy_momentum_df):
        """2 conditions met should produce BUY with proportional score."""
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(partial_buy_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.action == "BUY"
        assert 0.3 <= signal.confidence <= 0.6

    def test_hold_has_partial_confidence(self, hold_momentum_df):
        """HOLD signals carry partial score for transparency."""
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(hold_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.action == "HOLD"
        assert signal.confidence >= 0.0

    def test_confidence_capped_at_one(self, buy_momentum_df):
        """Confidence should never exceed 1.0."""
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(buy_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.confidence <= 1.0

    def test_signal_has_atr(self, buy_momentum_df):
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(buy_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.atr > 0, "BUY signal must have atr > 0"
        assert signal.stop_price > 0, "BUY signal must have valid stop_price"
        close = float(buy_momentum_df["close"].iloc[-1])
        assert signal.stop_price < close

    def test_signal_reasoning_not_empty(self, buy_momentum_df):
        strategy = MomentumStrategy()
        signal = strategy.generate_signal(buy_momentum_df, "AAPL", DEFAULT_PARAMS)
        assert signal.reasoning != ""

    def test_insufficient_data_returns_hold(self):
        strategy = MomentumStrategy()
        df = make_base_df(n=1)
        signal = strategy.generate_signal(df, "AAPL", DEFAULT_PARAMS)
        assert signal.action == "HOLD"
        assert "insufficient" in signal.reasoning.lower()


# ---------------------------------------------------------------------------
# Tests: Mean Reversion
# ---------------------------------------------------------------------------

class TestMeanReversion:
    def test_buy_oversold(self, buy_mean_reversion_df):
        strategy = MeanReversionStrategy()
        signal = strategy.generate_signal(buy_mean_reversion_df, "MSFT", DEFAULT_PARAMS)
        assert signal.action == "BUY"
        assert 0.5 <= signal.confidence <= 1.0
        assert signal.strategy == "mean_reversion"
        assert signal.symbol == "MSFT"

    def test_sell_return_to_mean(self, sell_mean_reversion_df):
        strategy = MeanReversionStrategy()
        signal = strategy.generate_signal(sell_mean_reversion_df, "MSFT", DEFAULT_PARAMS)
        assert signal.action == "SELL"
        assert signal.confidence == 0.7
        assert signal.strategy == "mean_reversion"

    def test_hold_single_condition(self, hold_mean_reversion_df):
        """Only 1 condition met — below 2-of-N gate, should be HOLD."""
        strategy = MeanReversionStrategy()
        signal = strategy.generate_signal(hold_mean_reversion_df, "MSFT", DEFAULT_PARAMS)
        assert signal.action == "HOLD"
        assert signal.strategy == "mean_reversion"

    def test_hold_has_partial_confidence(self, hold_mean_reversion_df):
        """HOLD carries partial score for transparency."""
        strategy = MeanReversionStrategy()
        signal = strategy.generate_signal(hold_mean_reversion_df, "MSFT", DEFAULT_PARAMS)
        assert signal.action == "HOLD"
        assert signal.confidence >= 0.0

    def test_confidence_capped_at_one(self, buy_mean_reversion_df):
        strategy = MeanReversionStrategy()
        signal = strategy.generate_signal(buy_mean_reversion_df, "MSFT", DEFAULT_PARAMS)
        assert signal.confidence <= 1.0

    def test_signal_has_atr(self, buy_mean_reversion_df):
        strategy = MeanReversionStrategy()
        signal = strategy.generate_signal(buy_mean_reversion_df, "MSFT", DEFAULT_PARAMS)
        assert signal.atr > 0
        assert signal.stop_price > 0

    def test_signal_reasoning_not_empty(self, buy_mean_reversion_df):
        strategy = MeanReversionStrategy()
        signal = strategy.generate_signal(buy_mean_reversion_df, "MSFT", DEFAULT_PARAMS)
        assert signal.reasoning != ""


# ---------------------------------------------------------------------------
# Tests: Breakout
# ---------------------------------------------------------------------------

class TestBreakout:
    def test_buy_new_high(self, buy_breakout_df):
        strategy = BreakoutStrategy()
        signal = strategy.generate_signal(buy_breakout_df, "SPY", DEFAULT_PARAMS)
        assert signal.action == "BUY"
        assert 0.4 <= signal.confidence <= 1.0
        assert signal.strategy == "breakout"
        assert signal.symbol == "SPY"

    def test_no_buy_below_high(self, no_buy_breakout_df):
        """Price below 20-bar high with normal volume should NOT produce BUY."""
        strategy = BreakoutStrategy()
        signal = strategy.generate_signal(no_buy_breakout_df, "SPY", DEFAULT_PARAMS)
        assert signal.action != "BUY"

    def test_confidence_capped_at_one(self, buy_breakout_df):
        strategy = BreakoutStrategy()
        signal = strategy.generate_signal(buy_breakout_df, "SPY", DEFAULT_PARAMS)
        assert signal.confidence <= 1.0

    def test_signal_has_atr(self, buy_breakout_df):
        strategy = BreakoutStrategy()
        signal = strategy.generate_signal(buy_breakout_df, "SPY", DEFAULT_PARAMS)
        assert signal.atr > 0
        assert signal.stop_price > 0

    def test_signal_reasoning_not_empty(self, buy_breakout_df):
        strategy = BreakoutStrategy()
        signal = strategy.generate_signal(buy_breakout_df, "SPY", DEFAULT_PARAMS)
        assert signal.reasoning != ""

    def test_insufficient_data_returns_hold(self):
        strategy = BreakoutStrategy()
        df = make_base_df(n=5)  # fewer than lookback_period + 1 = 21
        df["ATRr_14"] = 1.5
        signal = strategy.generate_signal(df, "SPY", DEFAULT_PARAMS)
        assert signal.action == "HOLD"


# ---------------------------------------------------------------------------
# Tests: VWAP
# ---------------------------------------------------------------------------

class TestVWAP:
    def test_buy_below_vwap(self, buy_vwap_df):
        strategy = VWAPStrategy()
        signal = strategy.generate_signal(buy_vwap_df, "QQQ", DEFAULT_PARAMS)
        assert signal.action == "BUY"
        assert 0.5 <= signal.confidence <= 1.0
        assert signal.strategy == "vwap"
        assert signal.symbol == "QQQ"

    def test_hold_wrong_time(self, hold_vwap_wrong_time_df):
        """Only 1 condition met (below VWAP) — RSI neutral, outside window → HOLD."""
        strategy = VWAPStrategy()
        signal = strategy.generate_signal(hold_vwap_wrong_time_df, "QQQ", DEFAULT_PARAMS)
        assert signal.action == "HOLD"

    def test_stop_is_percentage_based(self, buy_vwap_df_for_stop_check):
        """VWAP stop_price should use percentage formula, not ATR * multiplier."""
        strategy = VWAPStrategy()
        signal = strategy.generate_signal(buy_vwap_df_for_stop_check, "QQQ", DEFAULT_PARAMS)
        assert signal.action == "BUY"

        close = float(buy_vwap_df_for_stop_check["close"].iloc[-1])  # 98.0
        max_dev_pct = DEFAULT_PARAMS["max_deviation_pct"]  # 3.0
        expected_stop = round(close * (1 - max_dev_pct / 100), 2)

        # Percentage-based: 98.0 * (1 - 0.03) = 95.06
        assert signal.stop_price == expected_stop, (
            f"VWAP stop should be percentage-based: {expected_stop}, got {signal.stop_price}"
        )

        # Verify it's NOT the ATR formula: close - atr * multiplier
        atr = signal.atr
        atr_multiplier = DEFAULT_PARAMS["atr_multiplier"]
        atr_stop = round(close - atr * atr_multiplier, 2)
        if atr_stop != expected_stop:
            # The stops differ — confirm we're using the percentage formula
            assert signal.stop_price == expected_stop

    def test_signal_has_atr(self, buy_vwap_df):
        strategy = VWAPStrategy()
        signal = strategy.generate_signal(buy_vwap_df, "QQQ", DEFAULT_PARAMS)
        assert signal.atr > 0, "ATR field must be populated even for percentage-stop strategy"

    def test_signal_reasoning_not_empty(self, buy_vwap_df):
        strategy = VWAPStrategy()
        signal = strategy.generate_signal(buy_vwap_df, "QQQ", DEFAULT_PARAMS)
        assert signal.reasoning != ""

    def test_sell_when_price_returns_to_vwap(self):
        """SELL when price reaches or exceeds VWAP."""
        strategy = VWAPStrategy()
        # price = vwap → price returned to VWAP
        df = make_vwap_df(close=100.0, vwap=100.0, rsi=50.0, hour=11)
        signal = strategy.generate_signal(df, "QQQ", DEFAULT_PARAMS)
        assert signal.action == "SELL"
