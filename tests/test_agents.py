"""Structural tests for Claude Code agent definition files.

Verifies that agent markdown files exist with correct YAML frontmatter fields.
No mocking required — these are pure file content checks.
"""
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).parent.parent / "agents"


def _read_agent(filename: str) -> str:
    """Read an agent markdown file and return its content."""
    agent_path = AGENTS_DIR / filename
    assert agent_path.exists(), f"Agent file not found: {agent_path}"
    return agent_path.read_text()


class TestMarketAnalyst:
    """Structural tests for agents/market-analyst.md."""

    def test_file_exists(self):
        """agents/market-analyst.md must exist."""
        assert (AGENTS_DIR / "market-analyst.md").exists()

    def test_frontmatter_model_sonnet(self):
        """agents/market-analyst.md must specify model: sonnet."""
        content = _read_agent("market-analyst.md")
        assert "model: sonnet" in content, \
            "market-analyst.md must have 'model: sonnet' in frontmatter"

    def test_frontmatter_name(self):
        """agents/market-analyst.md must have name: market-analyst."""
        content = _read_agent("market-analyst.md")
        assert "name: market-analyst" in content, \
            "market-analyst.md must have 'name: market-analyst' in frontmatter"

    def test_frontmatter_description(self):
        """agents/market-analyst.md must have a description field."""
        content = _read_agent("market-analyst.md")
        assert "description:" in content, \
            "market-analyst.md must have 'description:' in frontmatter"

    def test_frontmatter_tools(self):
        """agents/market-analyst.md must have a tools field."""
        content = _read_agent("market-analyst.md")
        assert "tools:" in content, \
            "market-analyst.md must have 'tools:' in frontmatter"

    def test_has_yaml_delimiters(self):
        """agents/market-analyst.md must use --- YAML frontmatter delimiters."""
        content = _read_agent("market-analyst.md")
        lines = content.strip().splitlines()
        assert lines[0] == "---", "Agent file must start with '---' YAML delimiter"
        assert "---" in lines[1:], "Agent file must have closing '---' YAML delimiter"

    def test_body_references_signal(self):
        """market-analyst.md body should reference Signal or signal output."""
        content = _read_agent("market-analyst.md")
        assert "signal" in content.lower(), \
            "market-analyst.md should reference signal output in body"


class TestTradeExecutor:
    """Structural tests for agents/trade-executor.md."""

    def test_file_exists(self):
        """agents/trade-executor.md must exist."""
        assert (AGENTS_DIR / "trade-executor.md").exists()

    def test_frontmatter_model_sonnet(self):
        """agents/trade-executor.md must specify model: sonnet."""
        content = _read_agent("trade-executor.md")
        assert "model: sonnet" in content, \
            "trade-executor.md must have 'model: sonnet' in frontmatter"

    def test_frontmatter_name(self):
        """agents/trade-executor.md must have name: trade-executor."""
        content = _read_agent("trade-executor.md")
        assert "name: trade-executor" in content, \
            "trade-executor.md must have 'name: trade-executor' in frontmatter"

    def test_frontmatter_description(self):
        """agents/trade-executor.md must have a description field."""
        content = _read_agent("trade-executor.md")
        assert "description:" in content, \
            "trade-executor.md must have 'description:' in frontmatter"

    def test_frontmatter_tools(self):
        """agents/trade-executor.md must have a tools field."""
        content = _read_agent("trade-executor.md")
        assert "tools:" in content, \
            "trade-executor.md must have 'tools:' in frontmatter"

    def test_has_yaml_delimiters(self):
        """agents/trade-executor.md must use --- YAML frontmatter delimiters."""
        content = _read_agent("trade-executor.md")
        lines = content.strip().splitlines()
        assert lines[0] == "---", "Agent file must start with '---' YAML delimiter"
        assert "---" in lines[1:], "Agent file must have closing '---' YAML delimiter"

    def test_body_references_order_executor(self):
        """trade-executor.md body should reference OrderExecutor."""
        content = _read_agent("trade-executor.md")
        assert "OrderExecutor" in content, \
            "trade-executor.md should reference OrderExecutor in body"


class TestRiskManagerAgent:
    """Structural tests for existing agents/risk-manager.md (sanity check)."""

    def test_file_exists(self):
        """agents/risk-manager.md must exist."""
        assert (AGENTS_DIR / "risk-manager.md").exists()

    def test_frontmatter_model_sonnet(self):
        """agents/risk-manager.md must specify model: sonnet."""
        content = _read_agent("risk-manager.md")
        assert "model: sonnet" in content
