"""Tests for SessionStart hook and install-deps.sh logic."""
import hashlib
import os
import subprocess
from pathlib import Path

import pytest

INSTALL_SCRIPT = Path(__file__).parent.parent / "scripts" / "install-deps.sh"


class TestInstallDepsScript:
    """Test the install-deps.sh script logic."""

    def test_script_exists_and_is_executable(self):
        """PLUG-06: Script must exist and be executable."""
        assert INSTALL_SCRIPT.exists(), f"Script not found: {INSTALL_SCRIPT}"
        assert os.access(INSTALL_SCRIPT, os.X_OK), f"Script not executable: {INSTALL_SCRIPT}"

    def test_script_contains_hash_comparison(self):
        """PLUG-06: Script must use SHA256 hash to detect requirement changes."""
        content = INSTALL_SCRIPT.read_text()
        assert "sha256sum" in content, "Script must use sha256sum for hash comparison"
        assert "CURRENT_HASH" in content, "Script must compute CURRENT_HASH"
        assert "STORED_HASH" in content, "Script must read STORED_HASH"

    def test_script_uses_plugin_env_vars(self):
        """PLUG-06: Script must reference CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA."""
        content = INSTALL_SCRIPT.read_text()
        assert "CLAUDE_PLUGIN_ROOT" in content, "Script must use CLAUDE_PLUGIN_ROOT"
        assert "CLAUDE_PLUGIN_DATA" in content, "Script must use CLAUDE_PLUGIN_DATA"

    def test_script_uses_uv_not_pip(self):
        """PLUG-06: Script must use uv for installation, not pip."""
        content = INSTALL_SCRIPT.read_text()
        assert "uv pip install" in content, "Script must use 'uv pip install'"
        assert "uv venv" in content, "Script must use 'uv venv' to create virtualenv"

    def test_script_checks_python_version(self):
        """PLUG-06: Script must verify Python 3.12+ before installing."""
        content = INSTALL_SCRIPT.read_text()
        assert "Python 3.12" in content, "Script must check for Python 3.12+"

    def test_script_checks_uv_availability(self):
        """PLUG-06: Script must check if uv command is available."""
        content = INSTALL_SCRIPT.read_text()
        assert "command -v uv" in content, "Script must check for uv command"

    def test_script_stores_hash_after_install(self):
        """PLUG-06: Script must save hash after successful install."""
        content = INSTALL_SCRIPT.read_text()
        assert "requirements.txt.sha256" in content, "Script must write hash to .sha256 file"

    def test_script_expands_path(self):
        """PLUG-06: Script must expand PATH to find uv in user-level dirs."""
        content = INSTALL_SCRIPT.read_text()
        assert ".cargo/bin" in content or ".local/bin" in content, \
            "Script must expand PATH for user-level tool installs"


class TestHooksJson:
    """Test the hooks/hooks.json structure."""

    def test_hooks_json_exists(self):
        hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
        assert hooks_path.exists(), "hooks/hooks.json must exist"

    def test_hooks_json_valid_structure(self):
        import json
        hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        assert "hooks" in data, "Root must have 'hooks' key"
        assert "SessionStart" in data["hooks"], "Must have SessionStart hook"
        hooks_list = data["hooks"]["SessionStart"]
        assert len(hooks_list) > 0, "SessionStart must have at least one entry"
        command = hooks_list[0]["hooks"][0]["command"]
        assert "install-deps.sh" in command, "SessionStart must call install-deps.sh"
        assert "CLAUDE_PLUGIN_ROOT" in command, "Command must use CLAUDE_PLUGIN_ROOT variable"


class TestPluginManifest:
    """Test .claude-plugin/plugin.json."""

    def test_manifest_exists(self):
        manifest = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
        assert manifest.exists(), ".claude-plugin/plugin.json must exist"

    def test_manifest_has_required_fields(self):
        import json
        manifest = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
        data = json.loads(manifest.read_text())
        assert data["name"] == "trading-bot", "Plugin name must be 'trading-bot'"
        assert "version" in data, "Must have version field"
        assert "description" in data, "Must have description field"

    def test_manifest_uses_semver(self):
        import json
        manifest = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
        data = json.loads(manifest.read_text())
        version = data["version"]
        parts = version.split(".")
        assert len(parts) == 3, f"Version must be semver (got: {version})"
        for part in parts:
            assert part.isdigit(), f"Version parts must be numeric (got: {version})"


class TestRequirementsTxt:
    """Test requirements.txt content."""

    def test_requirements_exists(self):
        req = Path(__file__).parent.parent / "requirements.txt"
        assert req.exists(), "requirements.txt must exist"

    def test_requirements_has_alpaca_py(self):
        req = Path(__file__).parent.parent / "requirements.txt"
        content = req.read_text()
        assert "alpaca-py==0.43.2" in content, "Must pin alpaca-py==0.43.2"

    def test_requirements_has_pandas_ta(self):
        req = Path(__file__).parent.parent / "requirements.txt"
        content = req.read_text()
        assert "pandas-ta" in content, "Must include pandas-ta"

    def test_requirements_has_pydantic_settings(self):
        req = Path(__file__).parent.parent / "requirements.txt"
        content = req.read_text()
        assert "pydantic-settings" in content, "Must include pydantic-settings"

    def test_requirements_has_apscheduler_3x(self):
        req = Path(__file__).parent.parent / "requirements.txt"
        content = req.read_text()
        assert "APScheduler" in content, "Must include APScheduler"
        assert "<4.0" in content, "Must cap APScheduler below 4.0"

    def test_requirements_has_loguru(self):
        req = Path(__file__).parent.parent / "requirements.txt"
        content = req.read_text()
        assert "loguru" in content, "Must include loguru"
