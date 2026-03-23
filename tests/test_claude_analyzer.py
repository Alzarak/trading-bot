"""Unit tests for ClaudeAnalyzer and ClaudeRecommendation.

Tests cover:
  - build_analysis_prompt() output contents and constraints
  - parse_response() with valid JSON, malformed JSON, and wrapped code blocks
  - confidence threshold filtering
  - ClaudeRecommendation.to_signal() conversion
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from scripts.models import ClaudeRecommendation, Signal
from scripts.claude_analyzer import ClaudeAnalyzer

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def indicator_columns():
    """Return the same column names that MarketScanner.get_indicator_columns() produces."""
    return {
        "rsi": "RSI_14",
        "macd": "MACD_12_26_9",
        "macd_histogram": "MACDh_12_26_9",
        "macd_signal": "MACDs_12_26_9",
        "ema_short": "EMA_9",
        "ema_long": "EMA_21",
        "atr": "ATRr_14",
        "bb_lower": "BBL_20_2.0_2.0",
        "bb_middle": "BBM_20_2.0_2.0",
        "bb_upper": "BBU_20_2.0_2.0",
        "vwap": "VWAP_D",
    }


@pytest.fixture
def sample_df(indicator_columns):
    """Build a 10-row indicator-enriched DataFrame matching MarketScanner output.

    Uses timezone-aware DatetimeIndex in America/New_York, which VWAP requires.
    """
    base = datetime(2024, 1, 15, 10, 0, tzinfo=ET)
    index = [base + timedelta(minutes=i) for i in range(10)]

    data = {
        "open": [150.0 + i * 0.1 for i in range(10)],
        "high": [151.0 + i * 0.1 for i in range(10)],
        "low": [149.0 + i * 0.1 for i in range(10)],
        "close": [150.5 + i * 0.1 for i in range(10)],
        "volume": [100_000 + i * 1000 for i in range(10)],
        "RSI_14": [45.0 + i for i in range(10)],
        "MACD_12_26_9": [0.1 * i for i in range(10)],
        "MACDh_12_26_9": [0.05 * i for i in range(10)],
        "MACDs_12_26_9": [0.08 * i for i in range(10)],
        "EMA_9": [149.5 + i * 0.15 for i in range(10)],
        "EMA_21": [148.0 + i * 0.1 for i in range(10)],
        "ATRr_14": [1.2 + i * 0.01 for i in range(10)],
        "BBL_20_2.0_2.0": [147.0 + i * 0.05 for i in range(10)],
        "BBM_20_2.0_2.0": [150.0 + i * 0.05 for i in range(10)],
        "BBU_20_2.0_2.0": [153.0 + i * 0.05 for i in range(10)],
        "VWAP_D": [150.2 + i * 0.02 for i in range(10)],
    }

    return pd.DataFrame(data, index=pd.DatetimeIndex(index, name="timestamp"))


@pytest.fixture
def analyzer(sample_config_dict):
    """Return a default ClaudeAnalyzer instance."""
    return ClaudeAnalyzer(config=sample_config_dict)


@pytest.fixture
def sample_config_dict():
    """Minimal config dict to satisfy ClaudeAnalyzer.__init__."""
    return {
        "strategy_params": {
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "ema_short": 9,
            "ema_long": 21,
            "atr_period": 14,
            "bb_period": 20,
            "bb_std_dev": 2.0,
        }
    }


# ---------------------------------------------------------------------------
# Test 1: build_analysis_prompt() content
# ---------------------------------------------------------------------------


def test_build_analysis_prompt_contains_symbol(analyzer, sample_df, indicator_columns):
    """Prompt must include the symbol name so Claude knows which ticker it analyzes."""
    prompt = analyzer.build_analysis_prompt("AAPL", sample_df, "momentum", indicator_columns)
    assert "AAPL" in prompt


def test_build_analysis_prompt_contains_strategy(analyzer, sample_df, indicator_columns):
    """Prompt must include the strategy name for context-aware analysis."""
    prompt = analyzer.build_analysis_prompt("AAPL", sample_df, "momentum", indicator_columns)
    assert "momentum" in prompt


def test_build_analysis_prompt_contains_json_schema(analyzer, sample_df, indicator_columns):
    """Prompt must include the expected JSON response schema."""
    prompt = analyzer.build_analysis_prompt("AAPL", sample_df, "momentum", indicator_columns)
    # All required fields from ClaudeRecommendation schema
    for field in ("action", "confidence", "reasoning", "strategy", "atr", "stop_price"):
        assert field in prompt, f"Schema field '{field}' missing from prompt"


def test_build_analysis_prompt_analyst_only_instruction(analyzer, sample_df, indicator_columns):
    """Prompt must contain the analyst-only safety instruction."""
    prompt = analyzer.build_analysis_prompt("AAPL", sample_df, "momentum", indicator_columns)
    assert "You are an analyst only" in prompt


def test_build_analysis_prompt_includes_threshold(analyzer, sample_df, indicator_columns):
    """Prompt must include the confidence threshold for Claude calibration."""
    prompt = analyzer.build_analysis_prompt("AAPL", sample_df, "momentum", indicator_columns)
    assert "0.6" in prompt  # default threshold
    assert "confidence threshold" in prompt.lower()


def test_build_analysis_prompt_custom_threshold(sample_config_dict, sample_df, indicator_columns):
    """Prompt with custom threshold should include that threshold value."""
    analyzer = ClaudeAnalyzer(config=sample_config_dict, confidence_threshold=0.45)
    prompt = analyzer.build_analysis_prompt("AAPL", sample_df, "momentum", indicator_columns)
    assert "0.45" in prompt


def test_build_analysis_prompt_indicator_values_present(analyzer, sample_df, indicator_columns):
    """Prompt must include indicator values from the DataFrame."""
    prompt = analyzer.build_analysis_prompt("AAPL", sample_df, "momentum", indicator_columns)
    # RSI value from the last row should appear
    last_rsi = sample_df["RSI_14"].iloc[-1]
    assert str(round(last_rsi, 2)) in prompt or str(last_rsi) in prompt


# ---------------------------------------------------------------------------
# Test 5: build_analysis_prompt() uses only last 5 rows
# ---------------------------------------------------------------------------


def test_build_analysis_prompt_uses_last_5_rows(sample_config_dict, indicator_columns):
    """Prompt must include data from the last 5 rows only, not earlier rows.

    We set row 0 RSI to a distinctive value (999.0) and verify it is NOT in
    the prompt while the last row's RSI IS present.
    """
    base = datetime(2024, 1, 15, 10, 0, tzinfo=ET)
    index = [base + timedelta(minutes=i) for i in range(10)]

    data = {
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.5] * 10,
        "volume": [100_000] * 10,
        "RSI_14": [999.0] + [55.0] * 9,  # row 0 has distinctive marker
        "MACD_12_26_9": [0.1] * 10,
        "MACDh_12_26_9": [0.05] * 10,
        "MACDs_12_26_9": [0.08] * 10,
        "EMA_9": [149.5] * 10,
        "EMA_21": [148.0] * 10,
        "ATRr_14": [1.2] * 10,
        "BBL_20_2.0_2.0": [147.0] * 10,
        "BBM_20_2.0_2.0": [150.0] * 10,
        "BBU_20_2.0_2.0": [153.0] * 10,
        "VWAP_D": [150.2] * 10,
    }
    df = pd.DataFrame(data, index=pd.DatetimeIndex(index, name="timestamp"))
    analyzer = ClaudeAnalyzer(config=sample_config_dict)
    prompt = analyzer.build_analysis_prompt("TSLA", df, "breakout", indicator_columns)
    assert "999" not in prompt, "Prompt should NOT include data from early rows (before last 5)"
    assert "55" in prompt, "Prompt SHOULD include data from recent rows"


# ---------------------------------------------------------------------------
# Test 2: parse_response() with valid JSON
# ---------------------------------------------------------------------------


def test_parse_response_valid_json(analyzer):
    """parse_response returns list with one ClaudeRecommendation on valid JSON."""
    payload = {
        "symbol": "AAPL",
        "action": "BUY",
        "confidence": 0.82,
        "reasoning": "RSI oversold, MACD crossing up",
        "strategy": "momentum",
        "atr": 1.45,
        "stop_price": 148.55,
    }
    result = analyzer.parse_response(json.dumps(payload))
    assert len(result) == 1
    rec = result[0]
    assert isinstance(rec, ClaudeRecommendation)
    assert rec.symbol == "AAPL"
    assert rec.action == "BUY"
    assert rec.confidence == 0.82
    assert rec.reasoning == "RSI oversold, MACD crossing up"
    assert rec.strategy == "momentum"
    assert rec.atr == 1.45
    assert rec.stop_price == 148.55


def test_parse_response_wrapped_in_code_block(analyzer):
    """parse_response handles ```json ... ``` code-fenced responses."""
    payload = {
        "symbol": "MSFT",
        "action": "SELL",
        "confidence": 0.75,
        "reasoning": "BB upper breach, RSI overbought",
        "strategy": "mean_reversion",
        "atr": 2.1,
        "stop_price": 380.5,
    }
    response = f"```json\n{json.dumps(payload)}\n```"
    result = analyzer.parse_response(response)
    assert len(result) == 1
    assert result[0].action == "SELL"


def test_parse_response_with_surrounding_text(analyzer):
    """parse_response handles JSON embedded in prose text."""
    payload = {
        "symbol": "SPY",
        "action": "HOLD",
        "confidence": 0.65,
        "reasoning": "No clear signal",
        "strategy": "momentum",
        "atr": 3.0,
        "stop_price": 450.0,
    }
    response = (
        "Based on the indicator data, here is my recommendation:\n\n"
        f"{json.dumps(payload)}\n\n"
        "Please route this through risk management."
    )
    result = analyzer.parse_response(response)
    assert len(result) == 1
    assert result[0].symbol == "SPY"


# ---------------------------------------------------------------------------
# Test 3: parse_response() with malformed JSON
# ---------------------------------------------------------------------------


def test_parse_response_malformed_json_returns_empty(analyzer):
    """parse_response returns empty list on malformed JSON — does not raise."""
    result = analyzer.parse_response("this is not valid json {broken")
    assert result == []


def test_parse_response_empty_string_returns_empty(analyzer):
    """parse_response returns empty list for empty string input."""
    result = analyzer.parse_response("")
    assert result == []


# ---------------------------------------------------------------------------
# Test 4: parse_response() confidence threshold filtering
# ---------------------------------------------------------------------------


def test_parse_response_filters_below_threshold(analyzer):
    """parse_response excludes recommendations with confidence < threshold (default 0.6)."""
    payload = {
        "symbol": "AAPL",
        "action": "BUY",
        "confidence": 0.45,  # below default threshold of 0.6
        "reasoning": "Weak signal",
        "strategy": "momentum",
        "atr": 1.2,
        "stop_price": 148.0,
    }
    result = analyzer.parse_response(json.dumps(payload))
    assert result == []


def test_parse_response_includes_at_threshold(analyzer):
    """parse_response includes recommendations with confidence == threshold."""
    payload = {
        "symbol": "AAPL",
        "action": "BUY",
        "confidence": 0.6,  # exactly at the default threshold
        "reasoning": "Threshold signal",
        "strategy": "momentum",
        "atr": 1.2,
        "stop_price": 148.0,
    }
    result = analyzer.parse_response(json.dumps(payload))
    assert len(result) == 1


def test_parse_response_custom_threshold(sample_config_dict):
    """Custom threshold is respected by ClaudeAnalyzer."""
    analyzer = ClaudeAnalyzer(config=sample_config_dict, confidence_threshold=0.8)
    payload = {
        "symbol": "AAPL",
        "action": "BUY",
        "confidence": 0.75,  # above default 0.6 but below custom 0.8
        "reasoning": "Mid signal",
        "strategy": "momentum",
        "atr": 1.2,
        "stop_price": 148.0,
    }
    result = analyzer.parse_response(json.dumps(payload))
    assert result == []


# ---------------------------------------------------------------------------
# Test 6: ClaudeRecommendation.to_signal()
# ---------------------------------------------------------------------------


def test_claude_recommendation_to_signal():
    """to_signal() converts ClaudeRecommendation to a Signal with matching fields."""
    rec = ClaudeRecommendation(
        symbol="AAPL",
        action="BUY",
        confidence=0.82,
        reasoning="RSI oversold",
        strategy="momentum",
        atr=1.45,
        stop_price=148.55,
    )
    signal = rec.to_signal()

    assert isinstance(signal, Signal)
    assert signal.symbol == rec.symbol
    assert signal.action == rec.action
    assert signal.confidence == rec.confidence
    assert signal.reasoning == rec.reasoning
    assert signal.strategy == rec.strategy
    assert signal.atr == rec.atr
    assert signal.stop_price == rec.stop_price


def test_claude_recommendation_to_signal_sell():
    """to_signal() works for SELL recommendations too."""
    rec = ClaudeRecommendation(
        symbol="MSFT",
        action="SELL",
        confidence=0.71,
        reasoning="Overbought",
        strategy="mean_reversion",
        atr=2.1,
        stop_price=382.0,
    )
    signal = rec.to_signal()
    assert signal.action == "SELL"
    assert signal.symbol == "MSFT"


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


def test_parse_response_missing_required_field_returns_empty(analyzer):
    """parse_response returns empty list when a required field is missing."""
    payload = {
        "symbol": "AAPL",
        "action": "BUY",
        # confidence missing — required field
        "reasoning": "Strong signal",
        "strategy": "momentum",
        "atr": 1.2,
        "stop_price": 148.0,
    }
    result = analyzer.parse_response(json.dumps(payload))
    assert result == []
