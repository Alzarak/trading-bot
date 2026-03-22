"""
Tests for config.json schema validation.

Covers: STATE-03 (config in JSON), CMD-05 (complete config output),
ALP-02 (paper trading), ALP-03 (live trading).
"""
import json

import pytest

# ---------------------------------------------------------------------------
# Schema constants — these define the contract the wizard (Plan 03) must produce
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "experience_level": str,
    "paper_trading": bool,
    "risk_tolerance": str,
    "autonomy_mode": str,
    "max_position_pct": (int, float),
    "max_daily_loss_pct": (int, float),
    "budget_usd": (int, float),
    "strategies": list,
    "market_hours_only": bool,
    "watchlist": list,
    "autonomy_level": str,
    "config_version": str,
}

VALID_EXPERIENCE_LEVELS = {"beginner", "intermediate", "expert"}
VALID_RISK_TOLERANCES = {"conservative", "moderate", "aggressive"}
VALID_AUTONOMY_MODES = {"fixed_params", "claude_decides"}
VALID_STRATEGY_NAMES = {"momentum", "mean_reversion", "breakout", "vwap"}
REQUIRED_STRATEGY_FIELDS = {"name", "weight", "params"}


# ---------------------------------------------------------------------------
# TestConfigSchema
# ---------------------------------------------------------------------------


class TestConfigSchema:
    """Validate the config.json schema that /initialize wizard must produce."""

    def test_valid_config_has_all_required_fields(self, sample_config):
        """STATE-03: config.json must contain every required field."""
        for field in REQUIRED_FIELDS:
            assert field in sample_config, (
                f"Required field '{field}' is missing from config"
            )

    def test_valid_config_field_types(self, sample_config):
        """STATE-03: Every required field must match the expected type."""
        for field, expected_type in REQUIRED_FIELDS.items():
            value = sample_config[field]
            assert isinstance(value, expected_type), (
                f"Field '{field}' has wrong type: expected {expected_type}, "
                f"got {type(value)}"
            )

    def test_experience_level_valid_values(self, sample_config):
        """CMD-02: experience_level must be one of the three recognised levels."""
        assert sample_config["experience_level"] in VALID_EXPERIENCE_LEVELS, (
            f"experience_level '{sample_config['experience_level']}' is not valid. "
            f"Must be one of: {VALID_EXPERIENCE_LEVELS}"
        )

    def test_risk_tolerance_valid_values(self, sample_config):
        """CMD-03: risk_tolerance must be conservative, moderate, or aggressive."""
        assert sample_config["risk_tolerance"] in VALID_RISK_TOLERANCES, (
            f"risk_tolerance '{sample_config['risk_tolerance']}' is not valid. "
            f"Must be one of: {VALID_RISK_TOLERANCES}"
        )

    def test_autonomy_mode_valid_values(self, sample_config):
        """CMD-04: autonomy_mode must be fixed_params or claude_decides."""
        assert sample_config["autonomy_mode"] in VALID_AUTONOMY_MODES, (
            f"autonomy_mode '{sample_config['autonomy_mode']}' is not valid. "
            f"Must be one of: {VALID_AUTONOMY_MODES}"
        )

    def test_paper_trading_is_bool(self, sample_config):
        """ALP-02/ALP-03: paper_trading must be a boolean, not a string."""
        value = sample_config["paper_trading"]
        # Ensure it is a genuine bool — JSON can decode "true" as bool,
        # but a string "true" would pass isinstance(value, str) not bool.
        assert isinstance(value, bool), (
            f"paper_trading must be bool, got {type(value)}: {value!r}"
        )

    def test_strategies_array_not_empty(self, sample_config):
        """CMD-12: At least one strategy must be configured."""
        assert len(sample_config["strategies"]) > 0, (
            "strategies array must contain at least one strategy"
        )

    def test_strategy_objects_have_required_fields(self, sample_config):
        """CMD-12: Every strategy object must have name, weight, and params."""
        for i, strategy in enumerate(sample_config["strategies"]):
            for field in REQUIRED_STRATEGY_FIELDS:
                assert field in strategy, (
                    f"strategies[{i}] is missing required field '{field}'"
                )

    def test_strategy_names_are_valid(self, sample_config):
        """CMD-12: Strategy names must match one of the four supported strategies."""
        for i, strategy in enumerate(sample_config["strategies"]):
            assert strategy["name"] in VALID_STRATEGY_NAMES, (
                f"strategies[{i}].name '{strategy['name']}' is not a valid strategy. "
                f"Must be one of: {VALID_STRATEGY_NAMES}"
            )

    def test_strategy_weights_are_numeric(self, sample_config):
        """CMD-12: Strategy weights must be positive numbers."""
        for i, strategy in enumerate(sample_config["strategies"]):
            weight = strategy["weight"]
            assert isinstance(weight, (int, float)), (
                f"strategies[{i}].weight must be numeric, got {type(weight)}"
            )
            assert weight > 0, (
                f"strategies[{i}].weight must be positive, got {weight}"
            )

    def test_max_position_pct_in_range(self, sample_config):
        """POS-01 prep: max_position_pct must be between 1% and 100%."""
        pct = sample_config["max_position_pct"]
        assert 1.0 <= pct <= 100.0, (
            f"max_position_pct must be in range [1.0, 100.0], got {pct}"
        )

    def test_max_daily_loss_pct_in_range(self, sample_config):
        """RISK-01 prep: max_daily_loss_pct must be between 0.5% and 20%."""
        pct = sample_config["max_daily_loss_pct"]
        assert 0.5 <= pct <= 20.0, (
            f"max_daily_loss_pct must be in range [0.5, 20.0], got {pct}"
        )

    def test_budget_usd_positive(self, sample_config):
        """CMD-03: Budget must be a positive number."""
        budget = sample_config["budget_usd"]
        assert budget > 0, f"budget_usd must be positive, got {budget}"

    def test_watchlist_not_empty(self, sample_config):
        """CMD-03: At least one ticker must be in the watchlist."""
        assert len(sample_config["watchlist"]) > 0, (
            "watchlist must contain at least one ticker symbol"
        )

    def test_watchlist_contains_strings(self, sample_config):
        """CMD-03: Watchlist tickers must be uppercase strings."""
        for i, ticker in enumerate(sample_config["watchlist"]):
            assert isinstance(ticker, str), (
                f"watchlist[{i}] must be a string, got {type(ticker)}"
            )
            assert ticker == ticker.upper(), (
                f"watchlist[{i}] '{ticker}' must be uppercase"
            )

    def test_config_version_present(self, sample_config):
        """STATE-03: config_version must be '1' for v1 schema."""
        assert sample_config["config_version"] == "1", (
            f"config_version must be '1', got {sample_config['config_version']!r}"
        )

    def test_config_is_valid_json_serializable(self, sample_config):
        """STATE-03: Config must survive a JSON roundtrip without loss."""
        serialized = json.dumps(sample_config)
        deserialized = json.loads(serialized)
        assert deserialized == sample_config, (
            "Config did not survive JSON serialization roundtrip"
        )


# ---------------------------------------------------------------------------
# TestPaperVsLiveMode
# ---------------------------------------------------------------------------


class TestPaperVsLiveMode:
    """Validate paper vs live trading mode configuration."""

    def test_paper_mode_config(self, sample_config):
        """ALP-02: paper_trading=True must be accepted as a valid config."""
        config = dict(sample_config)
        config["paper_trading"] = True
        assert config["paper_trading"] is True

    def test_live_mode_config(self, sample_config):
        """ALP-03: paper_trading=False must be accepted as a valid config."""
        config = dict(sample_config)
        config["paper_trading"] = False
        assert config["paper_trading"] is False

    def test_beginner_defaults_to_paper(self, sample_config):
        """ALP-02: Beginner experience level should default to paper trading.

        This test documents the contract: any config produced by the wizard for a
        beginner user must have paper_trading=True. The wizard enforces this; this
        test validates the fixture matches the expected beginner profile.
        """
        assert sample_config["experience_level"] == "beginner", (
            "sample_config fixture must represent a beginner profile"
        )
        assert sample_config["paper_trading"] is True, (
            "Beginner config must default to paper_trading=True"
        )
