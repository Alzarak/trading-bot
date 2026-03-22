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


# ---------------------------------------------------------------------------
# Test 11: .env.template is created with placeholder keys (no actual values)
# ---------------------------------------------------------------------------

def test_env_template_created_with_placeholder_keys(base_config, tmp_path):
    """.env.template must exist with ALPACA_API_KEY= and ALPACA_SECRET_KEY= (no values)."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    env_template = output_dir / ".env.template"
    assert env_template.exists(), ".env.template must be created in output_dir"

    content = env_template.read_text()
    # Must have keys with empty values
    assert "ALPACA_API_KEY=" in content, ".env.template must contain ALPACA_API_KEY="
    assert "ALPACA_SECRET_KEY=" in content, ".env.template must contain ALPACA_SECRET_KEY="
    assert "ALPACA_PAPER=true" in content, ".env.template must contain ALPACA_PAPER=true"

    # Must NOT have actual key values (no non-empty value after =)
    import re
    # Check that ALPACA_API_KEY= is followed only by whitespace/newline, not actual key
    assert not re.search(r'ALPACA_API_KEY=\S+', content), \
        ".env.template must NOT contain an actual API key value after ALPACA_API_KEY="
    assert not re.search(r'ALPACA_SECRET_KEY=\S+', content), \
        ".env.template must NOT contain an actual secret key value after ALPACA_SECRET_KEY="


# ---------------------------------------------------------------------------
# Test 12: .env.template contains comment header explaining each variable
# ---------------------------------------------------------------------------

def test_env_template_has_comment_headers(base_config, tmp_path):
    """.env.template must contain explanatory comments for each variable."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    content = (output_dir / ".env.template").read_text()

    # Must have comments explaining what the variables are
    assert content.startswith("#"), ".env.template must start with a comment header"
    # Must have at least some explanation about Alpaca credentials
    assert "Alpaca" in content or "alpaca" in content, \
        ".env.template must mention Alpaca in comments"
    assert "paper" in content.lower(), \
        ".env.template must explain the paper trading variable"


# ---------------------------------------------------------------------------
# Test 13: .gitignore is created with required exclusions
# ---------------------------------------------------------------------------

def test_gitignore_created_with_required_exclusions(base_config, tmp_path):
    """.gitignore must be created with .env, trading.db, __pycache__, *.pyc, logs/ entries."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    gitignore = output_dir / ".gitignore"
    assert gitignore.exists(), ".gitignore must be created in output_dir"

    content = gitignore.read_text()
    assert ".env" in content, ".gitignore must exclude .env"
    assert "trading.db" in content, ".gitignore must exclude trading.db"
    assert "__pycache__" in content, ".gitignore must exclude __pycache__"
    assert "*.pyc" in content, ".gitignore must exclude *.pyc"
    assert "logs/" in content, ".gitignore must exclude logs/"


# ---------------------------------------------------------------------------
# Test 14: requirements.txt is created with runtime deps only (no rich)
# ---------------------------------------------------------------------------

def test_requirements_txt_created_with_runtime_deps(base_config, tmp_path):
    """requirements.txt must contain runtime deps and must NOT include rich."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    req_file = output_dir / "requirements.txt"
    assert req_file.exists(), "requirements.txt must be created in output_dir"

    content = req_file.read_text()
    assert "alpaca-py" in content, "requirements.txt must include alpaca-py"
    assert "pandas-ta" in content, "requirements.txt must include pandas-ta"
    assert "pandas" in content, "requirements.txt must include pandas"
    assert "numpy" in content, "requirements.txt must include numpy"
    assert "APScheduler" in content, "requirements.txt must include APScheduler"
    assert "pydantic-settings" in content, "requirements.txt must include pydantic-settings"
    assert "loguru" in content, "requirements.txt must include loguru"
    assert "python-dotenv" in content, "requirements.txt must include python-dotenv"
    # rich is not needed standalone
    assert "rich" not in content, "requirements.txt must NOT include rich (not needed standalone)"


# ---------------------------------------------------------------------------
# Test 15: DEPLOY.md is created with cron and systemd examples
# ---------------------------------------------------------------------------

def test_deploy_md_created_with_cron_and_systemd(base_config, tmp_path):
    """DEPLOY.md must be created with cron and systemd deployment examples."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    deploy_md = output_dir / "DEPLOY.md"
    assert deploy_md.exists(), "DEPLOY.md must be created in output_dir"

    content = deploy_md.read_text()
    assert "cron" in content.lower(), "DEPLOY.md must include cron example"
    assert "systemd" in content.lower(), "DEPLOY.md must include systemd example"


# ---------------------------------------------------------------------------
# Test 16: DEPLOY.md cron example contains weekday-only pattern reference
# ---------------------------------------------------------------------------

def test_deploy_md_cron_contains_weekday_pattern(base_config, tmp_path):
    """DEPLOY.md cron section must reference the weekdays-only pattern (1-5)."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    content = (output_dir / "DEPLOY.md").read_text()
    assert "1-5" in content, \
        "DEPLOY.md cron example must contain '1-5' (weekdays-only cron pattern)"


# ---------------------------------------------------------------------------
# Test 17: DEPLOY.md systemd example contains [Unit], [Service], [Install]
# ---------------------------------------------------------------------------

def test_deploy_md_systemd_has_required_sections(base_config, tmp_path):
    """DEPLOY.md systemd example must contain [Unit], [Service], [Install] sections."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    content = (output_dir / "DEPLOY.md").read_text()
    assert "[Unit]" in content, "DEPLOY.md must have [Unit] systemd section"
    assert "[Service]" in content, "DEPLOY.md must have [Service] systemd section"
    assert "[Install]" in content, "DEPLOY.md must have [Install] systemd section"


# ---------------------------------------------------------------------------
# Test 18: run.sh is created as a bash launcher script
# ---------------------------------------------------------------------------

def test_run_sh_created_as_bash_launcher(base_config, tmp_path):
    """run.sh must be created with shebang and 'python bot.py' command."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    run_sh = output_dir / "run.sh"
    assert run_sh.exists(), "run.sh must be created in output_dir"

    content = run_sh.read_text()
    assert content.startswith("#!/bin/bash"), "run.sh must start with #!/bin/bash shebang"
    assert "python bot.py" in content, "run.sh must contain 'python bot.py'"


# ---------------------------------------------------------------------------
# Test 19: run.sh loads .env before running bot
# ---------------------------------------------------------------------------

def test_run_sh_loads_env_file(base_config, tmp_path):
    """run.sh must source .env to load environment variables."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    content = (output_dir / "run.sh").read_text()
    assert "source .env" in content or ". .env" in content, \
        "run.sh must source .env to load environment variables"


# ---------------------------------------------------------------------------
# Test 20: No generated file contains hardcoded API key values
# ---------------------------------------------------------------------------

def test_no_generated_file_contains_hardcoded_api_keys(base_config, tmp_path):
    """No generated file may contain a real API key pattern (ALPACA_API_KEY=PKxxx...)."""
    from scripts.build_generator import generate_build
    import re

    output_dir = tmp_path / "standalone"
    generate_build(base_config, output_dir)

    # Pattern: ALPACA_API_KEY or ALPACA_SECRET_KEY with a non-empty value after =
    hardcoded_pattern = re.compile(
        r'ALPACA_(API|SECRET)_KEY=\S+'
    )

    for fpath in output_dir.rglob("*"):
        if not fpath.is_file():
            continue
        try:
            content = fpath.read_text()
        except (UnicodeDecodeError, PermissionError):
            continue
        match = hardcoded_pattern.search(content)
        assert match is None, \
            f"File {fpath.name} contains hardcoded API key: {match.group()}"


# ---------------------------------------------------------------------------
# Test 21: files_generated list includes all new deployment artifact files
# ---------------------------------------------------------------------------

def test_files_generated_includes_deployment_artifacts(base_config, tmp_path):
    """files_generated return value must include .env.template, .gitignore, requirements.txt, DEPLOY.md, run.sh."""
    from scripts.build_generator import generate_build

    output_dir = tmp_path / "standalone"
    result = generate_build(base_config, output_dir)

    files = result["files_generated"]
    assert ".env.template" in files, "files_generated must include .env.template"
    assert ".gitignore" in files, "files_generated must include .gitignore"
    assert "requirements.txt" in files, "files_generated must include requirements.txt"
    assert "DEPLOY.md" in files, "files_generated must include DEPLOY.md"
    assert "run.sh" in files, "files_generated must include run.sh"
