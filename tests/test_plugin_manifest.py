"""
Tests for plugin manifest (plugin.json) and marketplace metadata (marketplace.json).

Note on repository URL: marketplace.json uses a placeholder GitHub URL.
Update it to your actual repository URL before publishing to the marketplace.
"""
import json
import re
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent / ".claude-plugin"
PLUGIN_JSON = PLUGIN_DIR / "plugin.json"
MARKETPLACE_JSON = PLUGIN_DIR / "marketplace.json"


def load_plugin_json():
    """Load and parse plugin.json, raising a clear error if it fails."""
    assert PLUGIN_JSON.exists(), f"plugin.json not found at {PLUGIN_JSON}"
    with open(PLUGIN_JSON) as f:
        return json.load(f)


def load_marketplace_json():
    """Load and parse marketplace.json, raising a clear error if it fails."""
    assert MARKETPLACE_JSON.exists(), f"marketplace.json not found at {MARKETPLACE_JSON}"
    with open(MARKETPLACE_JSON) as f:
        return json.load(f)


class TestPluginJsonIsValidJson:
    """plugin.json must be syntactically valid JSON."""

    def test_plugin_json_parses_without_error(self):
        """Loading plugin.json must not raise a json.JSONDecodeError."""
        with open(PLUGIN_JSON) as f:
            data = json.load(f)
        assert isinstance(data, dict)


class TestMarketplaceJsonIsValidJson:
    """marketplace.json must be syntactically valid JSON."""

    def test_marketplace_json_parses_without_error(self):
        """Loading marketplace.json must not raise a json.JSONDecodeError."""
        with open(MARKETPLACE_JSON) as f:
            data = json.load(f)
        assert isinstance(data, dict)


class TestPluginJsonFields:
    """Validate required fields in plugin.json."""

    def test_version_is_semver(self):
        """version must follow X.Y.Z semver format."""
        data = load_plugin_json()
        assert "version" in data, "plugin.json missing 'version' field"
        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, data["version"]), (
            f"version '{data['version']}' is not semver (X.Y.Z)"
        )

    def test_version_is_1_0_0(self):
        """version must be bumped to 1.0.0 for marketplace release."""
        data = load_plugin_json()
        assert data["version"] == "1.0.0", (
            f"Expected version '1.0.0', got '{data['version']}'"
        )

    def test_name_is_trading_bot(self):
        """name must be 'trading-bot'."""
        data = load_plugin_json()
        assert data.get("name") == "trading-bot", (
            f"Expected name 'trading-bot', got '{data.get('name')}'"
        )

    def test_description_is_non_empty_string(self):
        """description must be a non-empty string."""
        data = load_plugin_json()
        assert "description" in data, "plugin.json missing 'description' field"
        assert isinstance(data["description"], str) and len(data["description"]) > 0

    def test_description_contains_keywords(self):
        """description must reference both 'autonomous' and 'trading'."""
        data = load_plugin_json()
        desc = data.get("description", "").lower()
        assert "autonomous" in desc, "description must contain 'autonomous'"
        assert "trading" in desc, "description must contain 'trading'"

    def test_author_has_name_key(self):
        """author must be an object with a 'name' key."""
        data = load_plugin_json()
        assert "author" in data, "plugin.json missing 'author' field"
        assert isinstance(data["author"], dict), "author must be an object"
        assert "name" in data["author"], "author object must have a 'name' key"

    def test_license_is_mit(self):
        """license must be 'MIT'."""
        data = load_plugin_json()
        assert data.get("license") == "MIT", (
            f"Expected license 'MIT', got '{data.get('license')}'"
        )

    def test_keywords_is_non_empty_list(self):
        """keywords must be a non-empty list."""
        data = load_plugin_json()
        assert "keywords" in data, "plugin.json missing 'keywords' field"
        assert isinstance(data["keywords"], list) and len(data["keywords"]) > 0

    def test_keywords_contains_required_terms(self):
        """keywords must include 'trading', 'alpaca', and 'stocks'."""
        data = load_plugin_json()
        keywords = data.get("keywords", [])
        for term in ("trading", "alpaca", "stocks"):
            assert term in keywords, f"keywords missing '{term}'"

    def test_commands_lists_all_slash_commands(self):
        """commands must list 'initialize', 'build', and 'run'."""
        data = load_plugin_json()
        assert "commands" in data, "plugin.json missing 'commands' field"
        commands = data["commands"]
        assert isinstance(commands, list), "commands must be a list"
        for cmd in ("initialize", "build", "run"):
            assert cmd in commands, f"commands missing '{cmd}'"

    def test_dependencies_has_python_key(self):
        """dependencies must be an object with a 'python' key."""
        data = load_plugin_json()
        assert "dependencies" in data, "plugin.json missing 'dependencies' field"
        deps = data["dependencies"]
        assert isinstance(deps, dict), "dependencies must be an object"
        assert "python" in deps, "dependencies must have a 'python' key"


class TestMarketplaceJsonFields:
    """Validate required fields in marketplace.json."""

    def test_source_is_github(self):
        """source must be 'github' for GitHub-hosted plugins."""
        data = load_marketplace_json()
        assert data.get("source") == "github", (
            f"Expected source 'github', got '{data.get('source')}'"
        )

    def test_name_matches_plugin_json(self):
        """name in marketplace.json must match name in plugin.json."""
        plugin = load_plugin_json()
        market = load_marketplace_json()
        assert market.get("name") == plugin.get("name"), (
            f"marketplace name '{market.get('name')}' != plugin name '{plugin.get('name')}'"
        )

    def test_version_matches_plugin_json(self):
        """version in marketplace.json must match version in plugin.json."""
        plugin = load_plugin_json()
        market = load_marketplace_json()
        assert market.get("version") == plugin.get("version"), (
            f"marketplace version '{market.get('version')}' != plugin version '{plugin.get('version')}'"
        )

    def test_repository_is_github_url(self):
        """repository must be a string starting with 'https://github.com'."""
        data = load_marketplace_json()
        assert "repository" in data, "marketplace.json missing 'repository' field"
        repo = data["repository"]
        assert isinstance(repo, str), "repository must be a string"
        assert repo.startswith("https://github.com"), (
            f"repository '{repo}' must start with 'https://github.com'"
        )

    def test_description_is_present(self):
        """description must be present in marketplace.json."""
        data = load_marketplace_json()
        assert "description" in data, "marketplace.json missing 'description' field"
        assert isinstance(data["description"], str) and len(data["description"]) > 0
