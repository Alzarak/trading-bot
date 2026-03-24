"""Claude analysis prompt builder and response parser for the trading bot plugin.

ClaudeAnalyzer converts indicator-enriched DataFrames from MarketScanner into
structured prompts for Claude and parses the resulting JSON recommendations.

IMPORTANT: This module does NOT call Claude.  It builds prompts and parses
responses.  The /run command (or bot.py agent mode) is responsible for sending
the prompt to Claude and receiving the response.  This separation keeps
ClaudeAnalyzer fully testable without mocking LLM calls.
"""
from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd
from loguru import logger

from scripts.models import ClaudeRecommendation

# Required fields that every Claude JSON response must contain
_REQUIRED_FIELDS = frozenset(
    {"symbol", "action", "confidence", "reasoning", "strategy", "atr", "stop_price"}
)

# Valid action values
_VALID_ACTIONS = frozenset({"BUY", "SELL", "HOLD"})

# Default strategy params used when config lacks strategy_params
_DEFAULTS: dict = {
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


class ClaudeAnalyzer:
    """Builds analysis prompts from MarketScanner DataFrames and parses JSON responses.

    This class has two responsibilities:
      1. build_analysis_prompt() — formats indicator data into a structured prompt
         that instructs Claude to act as a market analyst and return a JSON
         recommendation.
      2. parse_response() — extracts and validates the JSON object from Claude's
         response text, filtering by confidence threshold.

    Claude is explicitly instructed to act as an analyst only and to never
    submit orders directly.  All recommendations produced here must pass through
    the deterministic Python RiskManager before any Alpaca order is placed.

    Args:
        config: Trading configuration dict (from config.json).  Used to derive
            indicator column names that match the MarketScanner output.
        confidence_threshold: Minimum confidence required to include a
            recommendation in the parsed output.  Defaults to 0.6.
    """

    def __init__(self, config: dict, confidence_threshold: float = 0.6) -> None:
        self.config = config
        self.confidence_threshold = confidence_threshold

        # Derive strategy params for column name generation
        params = config.get("strategy_params", {})
        self._rsi_period: int = int(params.get("rsi_period", _DEFAULTS["rsi_period"]))
        self._macd_fast: int = int(params.get("macd_fast", _DEFAULTS["macd_fast"]))
        self._macd_slow: int = int(params.get("macd_slow", _DEFAULTS["macd_slow"]))
        self._macd_signal: int = int(params.get("macd_signal", _DEFAULTS["macd_signal"]))
        self._ema_short: int = int(params.get("ema_short", _DEFAULTS["ema_short"]))
        self._ema_long: int = int(params.get("ema_long", _DEFAULTS["ema_long"]))
        self._atr_period: int = int(params.get("atr_period", _DEFAULTS["atr_period"]))
        self._bb_period: int = int(params.get("bb_period", _DEFAULTS["bb_period"]))
        self._bb_std_dev: float = float(params.get("bb_std_dev", _DEFAULTS["bb_std_dev"]))

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def build_analysis_prompt(
        self,
        symbol: str,
        df: pd.DataFrame,
        strategy_name: str,
        indicator_columns: dict[str, str] | None = None,
        crypto: bool = False,
    ) -> str:
        """Build a structured analysis prompt from an indicator-enriched DataFrame.

        The prompt includes:
          - Symbol and strategy context
          - A text table of the last 5 OHLCV + indicator rows
          - The JSON response schema Claude must follow
          - Explicit analyst-only instruction

        Args:
            symbol: Ticker symbol being analyzed (e.g. 'AAPL' or 'BTC/USD').
            df: Indicator-enriched DataFrame from MarketScanner.scan().
                Must contain OHLCV columns plus all indicator columns.
            strategy_name: Name of the active strategy (e.g. 'momentum').
            indicator_columns: Optional dict from MarketScanner.get_indicator_columns()
                mapping logical names to actual column names.  If None, derived
                from config strategy_params.
            crypto: If True, add crypto-specific context to the prompt.

        Returns:
            Formatted prompt string ready to send to Claude.
        """
        if indicator_columns is None:
            indicator_columns = self._derive_indicator_columns()

        # Limit to last 5 rows to stay within prompt token limits
        tail = df.tail(5)

        # Build the indicator summary table
        table_lines = self._build_indicator_table(tail, indicator_columns)

        # Crypto context block
        crypto_context = ""
        if crypto:
            crypto_context = """
## Asset Context

Asset type: cryptocurrency (24/7 market, no PDT rules, higher volatility expected, no shorting allowed).
Crypto markets are more volatile than equities — adjust confidence accordingly.
"""

        # Compose the prompt
        prompt = f"""You are analyzing market data for {symbol} using the {strategy_name} strategy.

You are an analyst only. Return a recommendation. Do NOT execute trades.
{crypto_context}

## Recent Market Data (last 5 bars)

{table_lines}

## Your Task

Analyze the indicator values above and determine whether to BUY, SELL, or HOLD {symbol}.

Return a single JSON object with this exact schema:

```json
{{
  "symbol": "{symbol}",
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<explicit explanation of indicator signals and decision rationale>",
  "strategy": "{strategy_name}",
  "atr": <current ATR value from last bar>,
  "stop_price": <pre-computed stop-loss price>
}}
```

## Rules

- Return EXACTLY ONE JSON object — no arrays, no extra text outside the object.
- `confidence` must reflect actual signal strength — do not inflate.
- `reasoning` must explain which indicators triggered the recommendation.
- `stop_price` for BUY: entry_price - (atr * 2.0). For SELL: entry_price + (atr * 2.0). For HOLD: 0.0.
- You are an analyst only. Return a recommendation. Do NOT execute trades.
- You must NEVER call Alpaca order APIs directly. All recommendations route through the Python risk manager.

## Calibration

Minimum confidence threshold for execution: {self.confidence_threshold}
Only recommend BUY/SELL if your confidence meets this threshold.
Scores below this threshold will be filtered out automatically.
"""
        return prompt

    def _derive_indicator_columns(self) -> dict[str, str]:
        """Derive indicator column names from strategy params.

        Mirrors the logic in MarketScanner.get_indicator_columns().
        """
        f = self._macd_fast
        sl = self._macd_slow
        sig = self._macd_signal
        bb = self._bb_period
        bb_std = self._bb_std_dev
        bb_suffix = f"{bb}_{bb_std}_{bb_std}"

        return {
            "rsi": f"RSI_{self._rsi_period}",
            "macd": f"MACD_{f}_{sl}_{sig}",
            "macd_histogram": f"MACDh_{f}_{sl}_{sig}",
            "macd_signal": f"MACDs_{f}_{sl}_{sig}",
            "ema_short": f"EMA_{self._ema_short}",
            "ema_long": f"EMA_{self._ema_long}",
            "atr": f"ATRr_{self._atr_period}",
            "bb_lower": f"BBL_{bb_suffix}",
            "bb_middle": f"BBM_{bb_suffix}",
            "bb_upper": f"BBU_{bb_suffix}",
            "vwap": "VWAP_D",
        }

    def _build_indicator_table(
        self, tail: pd.DataFrame, indicator_columns: dict[str, str]
    ) -> str:
        """Format the last-N rows as a readable text table.

        Only includes OHLCV columns and indicator columns present in the DataFrame.
        Missing columns are silently skipped.

        Args:
            tail: Last N rows of the indicator-enriched DataFrame.
            indicator_columns: Mapping from logical name to actual column name.

        Returns:
            Multi-line string with one bar per row.
        """
        rows = []

        # OHLCV base columns
        base_cols = ["open", "high", "low", "close", "volume"]

        # Indicator columns ordered by logical name
        indicator_order = [
            "rsi", "macd", "macd_histogram", "macd_signal",
            "ema_short", "ema_long", "atr",
            "bb_lower", "bb_middle", "bb_upper", "vwap",
        ]

        # Build header from available columns
        available_indicators = {
            name: col for name, col in indicator_columns.items()
            if col in tail.columns
        }

        header_parts = ["timestamp"] + base_cols + list(available_indicators.keys())
        rows.append(" | ".join(header_parts))
        rows.append("-" * (len(rows[0])))

        for ts, row in tail.iterrows():
            values = [str(ts)]
            for col in base_cols:
                val = row.get(col, "n/a")
                values.append(f"{val:.4f}" if isinstance(val, float) else str(val))
            for logical_name, col_name in available_indicators.items():
                val = row.get(col_name, "n/a")
                values.append(f"{val:.4f}" if isinstance(val, float) else str(val))
            rows.append(" | ".join(values))

        return "\n".join(rows)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def parse_response(self, response_text: str) -> list[ClaudeRecommendation]:
        """Extract and validate a ClaudeRecommendation from Claude's response text.

        Handles:
          - Raw JSON objects
          - JSON wrapped in ```json ... ``` code blocks
          - JSON embedded in surrounding prose text
          - Arrays of recommendations (takes first item)

        Args:
            response_text: Raw text response from Claude.

        Returns:
            List of ClaudeRecommendation objects that pass the confidence
            threshold.  Typically 0 or 1 items.  Returns [] on parse failure.
        """
        if not response_text or not response_text.strip():
            return []

        raw = self._extract_json_text(response_text)
        if raw is None:
            logger.warning("parse_response: no JSON object found in response")
            return []

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("parse_response: JSON decode error — {}", exc)
            return []

        # Normalise arrays to single item (take first)
        if isinstance(parsed, list):
            if not parsed:
                return []
            parsed = parsed[0]

        if not isinstance(parsed, dict):
            logger.warning("parse_response: unexpected JSON type — expected object")
            return []

        # Validate all required fields are present
        missing = _REQUIRED_FIELDS - parsed.keys()
        if missing:
            logger.warning("parse_response: missing required fields — {}", missing)
            return []

        # Validate confidence is a number
        try:
            confidence = float(parsed["confidence"])
        except (ValueError, TypeError) as exc:
            logger.warning("parse_response: invalid confidence value — {}", exc)
            return []

        # Apply threshold filter
        if confidence < self.confidence_threshold:
            logger.debug(
                "parse_response: confidence {:.2f} below threshold {:.2f} — filtered",
                confidence,
                self.confidence_threshold,
            )
            return []

        # Validate action
        action = str(parsed.get("action", "")).upper()
        if action not in _VALID_ACTIONS:
            logger.warning("parse_response: invalid action '{}' — must be BUY/SELL/HOLD", action)
            return []

        try:
            rec = ClaudeRecommendation(
                symbol=str(parsed["symbol"]),
                action=action,  # type: ignore[arg-type]
                confidence=confidence,
                reasoning=str(parsed["reasoning"]),
                strategy=str(parsed["strategy"]),
                atr=float(parsed["atr"]),
                stop_price=float(parsed["stop_price"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("parse_response: failed to construct ClaudeRecommendation — {}", exc)
            return []

        return [rec]

    def _extract_json_text(self, text: str) -> str | None:
        """Extract the first JSON object string from text.

        Tries in order:
          1. Code block: ```json ... ```
          2. Code block: ``` ... ```
          3. First { ... } object found in the text

        Args:
            text: Raw response text that may contain embedded JSON.

        Returns:
            JSON string if found, None otherwise.
        """
        # 1. Try ```json ... ``` code block
        code_block = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block:
            return code_block.group(1)

        # 2. Try ``` ... ``` code block (any language)
        code_block = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block:
            return code_block.group(1)

        # 3. Find the first { ... } block in plain text
        # Use a simple brace-balance tracker to find the complete JSON object
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None
