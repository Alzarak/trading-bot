"""Tests for scripts/build_generator.py.

Tests the generate_build() function which reads config.json and produces a
standalone trading bot directory with only the user's selected strategies.
"""
import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_config():
    """Minimal valid config for the build generator."""
    return {
        "experience_level": "beginner",
        "paper_trading": True,
        "risk_tolerance": "conservative",
        "autonomy_mode": "fixed_params",
        "max_position_pct": 5.0,
        "max_daily_loss_pct": 2.0,
        "budget_usd": 10000,
        "max_positions": 5,
        "strategies": [
            {"name": "momentum", "weight": 1.0, "params": {}},
        ],
        "market_hours_only": True,
        "watchlist": ["AAPL", "MSFT"],
        "autonomy_level": "notify_only",
        "config_version": "1",
        "scan_interval_seconds": 60,
        "position_size_pct": 5,
    }


@pytest.fixture
def two_strategy_config(base_config):
    """Config selecting only momentum and vwap."""
    cfg = dict(base_config)
    cfg["strategies"] = [
        {"name": "momentum", "weight": 0.5, "params": {}},
        {"name": "vwap", "weight": 0.5, "params": {}},
    ]
    return cfg


@pytest.fixture
def all_strategy_config(base_config):
    """Config selecting all 4 strategies."""
    cfg = dict(base_config)
    cfg["strategies"] = [
        {"name": "momentum", "weight": 0.25, "params": {}},
        {"name": "mean_reversion", "weight": 0.25, "params": {}},
        {"name": "breakout", "weight": 0.25, "params": {}},
        {"name": "vwap", "weight": 0.25, "params": {}},
    ]
    return cfg


# ---------------------------------------------------------------------------
# Test 1: Core files are created
# ---------------------------------------------------------------------------

def test_generate_build_creates_core_files(base_config, tmp_path):
    """generate_build() creates output directory with all required core files."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "trading-bot-standalone"
    result = generate_build(base_config, output_dir)

    assert output_dir.exists(), "Output directory was not created"

    expected_core_files = [
        "bot.py",
        "types.py",
        "market_scanner.py",
        "order_executor.py",
        "risk_manager.py",
        "state_store.py",
        "portfolio_tracker.py",
    ]
    for fname in expected_core_files:
        assert (output_dir / fname).exists(), f"Missing core file: {fname}"


# ---------------------------------------------------------------------------
# Test 2: Strategy filtering — only selected strategies are copied
# ---------------------------------------------------------------------------

def test_generate_build_filters_strategies_to_selected(two_strategy_config, tmp_path):
    """generate_build() with momentum+vwap creates only those strategy files."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(two_strategy_config, output_dir)

    strategies_dir = output_dir / "strategies"
    assert strategies_dir.exists(), "strategies/ directory was not created"

    # Required files
    assert (strategies_dir / "base.py").exists(), "base.py is required"
    assert (strategies_dir / "__init__.py").exists(), "__init__.py is required"
    assert (strategies_dir / "momentum.py").exists(), "momentum.py should be present"
    assert (strategies_dir / "vwap.py").exists(), "vwap.py should be present"

    # Must NOT be present
    assert not (strategies_dir / "mean_reversion.py").exists(), \
        "mean_reversion.py should NOT be present (not selected)"
    assert not (strategies_dir / "breakout.py").exists(), \
        "breakout.py should NOT be present (not selected)"


# ---------------------------------------------------------------------------
# Test 3: All 4 strategies when config includes them
# ---------------------------------------------------------------------------

def test_generate_build_all_strategies(all_strategy_config, tmp_path):
    """generate_build() with all 4 strategies creates all 4 strategy files."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(all_strategy_config, output_dir)

    strategies_dir = output_dir / "strategies"
    for fname in ["momentum.py", "mean_reversion.py", "breakout.py", "vwap.py"]:
        assert (strategies_dir / fname).exists(), f"Missing strategy file: {fname}"


# ---------------------------------------------------------------------------
# Test 4: Generated __init__.py STRATEGY_REGISTRY contains only selected entries
# ---------------------------------------------------------------------------

def test_generated_init_registry_contains_only_selected(two_strategy_config, tmp_path):
    """Generated strategies/__init__.py STRATEGY_REGISTRY has only momentum and vwap."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(two_strategy_config, output_dir)

    init_content = (output_dir / "strategies" / "__init__.py").read_text()

    assert "STRATEGY_REGISTRY" in init_content, "STRATEGY_REGISTRY must appear in __init__.py"
    assert "momentum" in init_content, "'momentum' must be in STRATEGY_REGISTRY"
    assert "vwap" in init_content, "'vwap' must be in STRATEGY_REGISTRY"
    assert "mean_reversion" not in init_content, \
        "'mean_reversion' must NOT appear in filtered __init__.py"
    assert "breakout" not in init_content, \
        "'breakout' must NOT appear in filtered __init__.py"


# ---------------------------------------------------------------------------
# Test 5: Generated bot.py uses relative imports (not from scripts.)
# ---------------------------------------------------------------------------

def test_generated_bot_uses_relative_imports(base_config, tmp_path):
    """Generated bot.py must use relative imports, not 'from scripts.X'."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    bot_content = (output_dir / "bot.py").read_text()

    assert "from scripts." not in bot_content, \
        "Generated bot.py must not contain 'from scripts.' (use relative imports)"
    # Check that relative imports are present
    assert "from market_scanner import" in bot_content or \
           "from strategies import" in bot_content or \
           "import market_scanner" in bot_content, \
        "Generated bot.py should use relative imports"


# ---------------------------------------------------------------------------
# Test 6: Generated bot.py reads config.json from current directory only
# ---------------------------------------------------------------------------

def test_generated_bot_reads_config_from_cwd(base_config, tmp_path):
    """Generated bot.py reads config.json from current directory (not CLAUDE_PLUGIN_DATA)."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    bot_content = (output_dir / "bot.py").read_text()

    # Must use simple cwd-only path
    assert 'Path("config.json")' in bot_content or \
           "Path('config.json')" in bot_content, \
        "Generated bot.py should read config.json from cwd"


# ---------------------------------------------------------------------------
# Test 7: Generated bot.py does NOT contain hardcoded API keys
# ---------------------------------------------------------------------------

def test_generated_bot_no_hardcoded_api_keys(base_config, tmp_path):
    """Generated bot.py must not contain hardcoded API key values."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    bot_content = (output_dir / "bot.py").read_text()

    # Should not have patterns like ALPACA_API_KEY="actual_key_value"
    import re
    hardcoded_pattern = re.compile(
        r'ALPACA_API_KEY\s*=\s*["\'][A-Za-z0-9]{10,}["\']'
    )
    assert not hardcoded_pattern.search(bot_content), \
        "Generated bot.py must not contain hardcoded API key values"

    hardcoded_secret = re.compile(
        r'ALPACA_SECRET_KEY\s*=\s*["\'][A-Za-z0-9]{10,}["\']'
    )
    assert not hardcoded_secret.search(bot_content), \
        "Generated bot.py must not contain hardcoded secret key values"


# ---------------------------------------------------------------------------
# Test 8: generate_build() returns required dict structure
# ---------------------------------------------------------------------------

def test_generate_build_returns_summary_dict(base_config, tmp_path):
    """generate_build() returns dict with output_dir, files_generated, strategies_included."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    result = generate_build(base_config, output_dir)

    assert isinstance(result, dict), "generate_build() must return a dict"
    assert "output_dir" in result, "Result must have 'output_dir' key"
    assert "files_generated" in result, "Result must have 'files_generated' key"
    assert "strategies_included" in result, "Result must have 'strategies_included' key"

    assert isinstance(result["files_generated"], list), \
        "'files_generated' must be a list"
    assert isinstance(result["strategies_included"], list), \
        "'strategies_included' must be a list"

    assert "momentum" in result["strategies_included"], \
        "Result strategies_included must list selected strategy names"

    # output_dir must be a string path
    assert isinstance(result["output_dir"], str), "'output_dir' must be a string"


# ---------------------------------------------------------------------------
# Test 9: config.json is written to output directory
# ---------------------------------------------------------------------------

def test_generate_build_writes_config_json(base_config, tmp_path):
    """generate_build() writes config.json to the output directory."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    config_path = output_dir / "config.json"
    assert config_path.exists(), "config.json must be written to output directory"

    written_config = json.loads(config_path.read_text())
    assert written_config["paper_trading"] == base_config["paper_trading"]
    assert written_config["watchlist"] == base_config["watchlist"]


# ---------------------------------------------------------------------------
# Test 10: strategies_included in result matches config
# ---------------------------------------------------------------------------

def test_strategies_included_matches_config(two_strategy_config, tmp_path):
    """strategies_included in result matches exactly the strategies from config."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    result = generate_build(two_strategy_config, output_dir)

    assert set(result["strategies_included"]) == {"momentum", "vwap"}, \
        f"Expected {{'momentum', 'vwap'}}, got {result['strategies_included']}"
