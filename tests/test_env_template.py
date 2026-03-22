"""
Tests for .env template structure.

Covers: ALP-01 (Alpaca auth via env vars), ALP-02 (paper trading default).
"""

# Required environment variable names that /initialize must include in .env
REQUIRED_ENV_VARS = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_PAPER"]


class TestEnvTemplate:
    """Validate the .env template produced by the /initialize wizard."""

    def test_env_template_has_all_vars(self, env_template):
        """ALP-01: All required environment variable names must appear in the template."""
        for var in REQUIRED_ENV_VARS:
            assert var in env_template, (
                f"Required env var '{var}' is missing from .env template"
            )

    def test_env_template_has_alpaca_api_key(self, env_template):
        """ALP-01: Template must include ALPACA_API_KEY= assignment line."""
        assert "ALPACA_API_KEY=" in env_template, (
            "ALPACA_API_KEY= must appear as an assignment in the .env template"
        )

    def test_env_template_has_alpaca_secret_key(self, env_template):
        """ALP-01: Template must include ALPACA_SECRET_KEY= assignment line."""
        assert "ALPACA_SECRET_KEY=" in env_template, (
            "ALPACA_SECRET_KEY= must appear as an assignment in the .env template"
        )

    def test_env_template_has_paper_flag(self, env_template):
        """ALP-02: Template must include ALPACA_PAPER= assignment line."""
        assert "ALPACA_PAPER=" in env_template, (
            "ALPACA_PAPER= must appear as an assignment in the .env template"
        )

    def test_env_template_defaults_to_paper(self, env_template):
        """ALP-02: Default value for ALPACA_PAPER must be 'true' (safe default)."""
        assert "ALPACA_PAPER=true" in env_template, (
            "ALPACA_PAPER must default to 'true' — live trading requires explicit opt-in"
        )

    def test_env_template_no_real_keys(self, env_template):
        """ALP-01: Template must not contain real API keys.

        A real Alpaca key is typically 20+ random characters. Placeholder values
        like 'your_key_here' or 'your_api_key_here' are short or contain 'your_'.
        This test ensures no real credentials are committed in the template.
        """
        for line in env_template.splitlines():
            # Skip comment lines and blank lines
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Placeholder values are short OR contain recognisable placeholder patterns
            is_placeholder = (
                len(value) < 30
                or "your_" in value.lower()
                or "here" in value.lower()
                or value == ""
                or value.lower() in {"true", "false"}
            )
            assert is_placeholder, (
                f"Variable '{key}' in .env template appears to have a real value "
                f"(length {len(value)}). Use a placeholder like 'your_{key.lower()}_here'."
            )
