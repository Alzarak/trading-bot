"""Centralized data directory resolution for the trading bot.

Lookup order:
1. TRADING_BOT_DIR env var (explicit override)
2. ./trading-bot/ in current working directory (project-level, preferred)
3. ~/.claude/trading-bot/ (install-level fallback)
4. Current working directory (last resort)
"""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """Return the resolved data directory for all bot runtime files."""
    # Explicit override
    if os.environ.get("TRADING_BOT_DIR"):
        return Path(os.environ["TRADING_BOT_DIR"])

    # Project-level (preferred — lives with the project, deleted when project is deleted)
    project_dir = Path.cwd() / "trading-bot"
    if project_dir.is_dir():
        return project_dir

    # Install-level fallback
    install_dir = Path.home() / ".claude" / "trading-bot"
    if install_dir.is_dir():
        return install_dir

    # Last resort
    return Path.cwd()
