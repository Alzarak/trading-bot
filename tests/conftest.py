"""Shared test fixtures for trading-bot plugin tests."""
import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def plugin_root(tmp_path):
    """Create a mock CLAUDE_PLUGIN_ROOT with requirements.txt."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text(
        "alpaca-py==0.43.2\n"
        "pandas-ta==0.4.71b0\n"
        "pandas>=2.0\n"
        "numpy>=1.26\n"
        "APScheduler>=3.10,<4.0\n"
        "pydantic-settings>=2.0\n"
        "loguru>=0.7\n"
        "python-dotenv>=1.0\n"
        "rich>=13.0\n"
    )
    return tmp_path


@pytest.fixture
def plugin_data(tmp_path):
    """Create a mock CLAUDE_PLUGIN_DATA directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_config():
    """Return a valid config.json dict with all required fields."""
    return {
        "experience_level": "beginner",
        "paper_trading": True,
        "risk_tolerance": "conservative",
        "autonomy_mode": "fixed_params",
        "max_position_pct": 5.0,
        "max_daily_loss_pct": 2.0,
        "budget_usd": 10000,
        "max_positions": 10,
        "strategies": [
            {
                "name": "momentum",
                "weight": 1.0,
                "params": {
                    "rsi_period": 14,
                    "macd_fast": 12,
                    "macd_slow": 26,
                    "macd_signal": 9,
                },
            }
        ],
        "market_hours_only": True,
        "watchlist": ["AAPL", "MSFT", "SPY"],
        "autonomy_level": "notify_only",
        "config_version": "1",
    }


@pytest.fixture
def mock_trading_client():
    """Return a MagicMock trading client with sensible defaults."""
    from unittest.mock import MagicMock

    client = MagicMock()
    account = MagicMock()
    account.equity = "10000.00"
    client.get_account.return_value = account
    client.get_all_positions.return_value = []
    client.get_open_position.side_effect = Exception("No position")
    return client


@pytest.fixture
def plugin_data_dir(tmp_path, monkeypatch):
    """Create a temp dir and set CLAUDE_PLUGIN_DATA env var."""
    data_dir = tmp_path / "plugin_data"
    data_dir.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data_dir))
    return data_dir


@pytest.fixture
def env_template():
    """Return expected .env template content."""
    return (
        "ALPACA_API_KEY=your_key_here\n"
        "ALPACA_SECRET_KEY=your_secret_here\n"
        "ALPACA_PAPER=true\n"
    )
