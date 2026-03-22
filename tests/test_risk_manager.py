"""
Unit tests for scripts/risk_manager.py.

Covers: RISK-01 (circuit breaker), RISK-02 (position sizing), RISK-03 (PDT tracking),
RISK-04 (max positions), RISK-05 (claude_decides clamping), POS-01, POS-02.

All tests use mocked Alpaca clients — no real API calls.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.risk_manager import RiskManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_rm(sample_config, mock_trading_client):
    """Construct a RiskManager with the sample config and mock client."""
    return RiskManager(sample_config, mock_trading_client)


# ---------------------------------------------------------------------------
# TestCircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """RISK-01: Circuit breaker halts trading when daily loss hits threshold."""

    def test_triggers_at_threshold(self, sample_config, mock_trading_client, plugin_data_dir):
        """Exactly at max_daily_loss_pct -> returns True."""
        rm = make_rm(sample_config, mock_trading_client)
        rm.start_equity = 10000.0
        # Equity dropped by exactly 2% (max_daily_loss_pct = 2.0)
        mock_trading_client.get_account.return_value.equity = "9800.00"
        assert rm.check_circuit_breaker() is True

    def test_allows_below_threshold(self, sample_config, mock_trading_client, plugin_data_dir):
        """Below max_daily_loss_pct -> returns False."""
        rm = make_rm(sample_config, mock_trading_client)
        rm.start_equity = 10000.0
        # Equity dropped by 1% — below 2% threshold
        mock_trading_client.get_account.return_value.equity = "9900.00"
        assert rm.check_circuit_breaker() is False

    def test_stays_triggered_after_recovery(self, sample_config, mock_trading_client, plugin_data_dir):
        """Once triggered, stays True even if equity recovers."""
        rm = make_rm(sample_config, mock_trading_client)
        rm.start_equity = 10000.0
        # Trigger
        mock_trading_client.get_account.return_value.equity = "9800.00"
        assert rm.check_circuit_breaker() is True
        # Equity "recovers"
        mock_trading_client.get_account.return_value.equity = "10500.00"
        assert rm.check_circuit_breaker() is True

    def test_persists_flag_file(self, sample_config, mock_trading_client, plugin_data_dir):
        """Triggering the circuit breaker writes circuit_breaker.flag to CLAUDE_PLUGIN_DATA."""
        rm = make_rm(sample_config, mock_trading_client)
        rm.start_equity = 10000.0
        mock_trading_client.get_account.return_value.equity = "9800.00"
        rm.check_circuit_breaker()
        flag_file = plugin_data_dir / "circuit_breaker.flag"
        assert flag_file.exists(), "circuit_breaker.flag must be written when triggered"

    def test_initialize_session_refuses_if_flag_exists(
        self, sample_config, mock_trading_client, plugin_data_dir
    ):
        """initialize_session raises RuntimeError if circuit_breaker.flag is present."""
        flag_file = plugin_data_dir / "circuit_breaker.flag"
        flag_file.write_text("triggered")
        rm = make_rm(sample_config, mock_trading_client)
        with pytest.raises(RuntimeError, match="circuit"):
            rm.initialize_session()


# ---------------------------------------------------------------------------
# TestPositionSizing
# ---------------------------------------------------------------------------


class TestPositionSizing:
    """RISK-02 / POS-01: Position size formula and budget cap enforcement."""

    def test_basic_calculation(self, sample_config, mock_trading_client, plugin_data_dir):
        """equity=10000, max_position_pct=5, price=50 -> 10 shares."""
        rm = make_rm(sample_config, mock_trading_client)
        # equity = 10000, pct = 5% -> value = 500, 500/50 = 10 shares
        shares = rm.calculate_position_size("AAPL", current_price=50.0)
        assert shares == 10

    def test_budget_cap(self, sample_config, mock_trading_client, plugin_data_dir):
        """position_value capped at budget_usd when equity*pct > budget."""
        config = dict(sample_config)
        config["max_position_pct"] = 50.0  # 50% of 10000 = 5000, but budget = 10000 -> no cap
        # Make equity huge so pct*equity > budget_usd
        config["budget_usd"] = 100  # Cap at $100
        mock_trading_client.get_account.return_value.equity = "100000.00"
        rm = RiskManager(config, mock_trading_client)
        # Without cap: 50% of 100000 = 50000 / 10.0 = 5000 shares
        # With budget cap: $100 / 10.0 = 10 shares
        shares = rm.calculate_position_size("AAPL", current_price=10.0)
        assert shares == 10

    def test_rejects_zero_shares(self, sample_config, mock_trading_client, plugin_data_dir):
        """Price too high for allocation -> returns 0."""
        rm = make_rm(sample_config, mock_trading_client)
        # equity=10000, 5% = 500, price = 1000 -> 0.5 shares -> floor to 0
        shares = rm.calculate_position_size("AAPL", current_price=1000.0)
        assert shares == 0


# ---------------------------------------------------------------------------
# TestPositionCount
# ---------------------------------------------------------------------------


class TestPositionCount:
    """POS-02: Block new entries when open positions >= max_positions."""

    def test_allows_under_limit(self, sample_config, mock_trading_client, plugin_data_dir):
        """5 open positions, max 10 -> True (allowed)."""
        mock_trading_client.get_all_positions.return_value = [MagicMock()] * 5
        rm = make_rm(sample_config, mock_trading_client)
        assert rm.check_position_count() is True

    def test_blocks_at_limit(self, sample_config, mock_trading_client, plugin_data_dir):
        """10 open positions, max 10 -> False (blocked)."""
        mock_trading_client.get_all_positions.return_value = [MagicMock()] * 10
        rm = make_rm(sample_config, mock_trading_client)
        assert rm.check_position_count() is False


# ---------------------------------------------------------------------------
# TestPDTTracking
# ---------------------------------------------------------------------------


class TestPDTTracking:
    """RISK-03: PDT limit enforcement over rolling 7-calendar-day window."""

    def test_allow_with_zero_trades(self, sample_config, mock_trading_client, plugin_data_dir):
        """No trades in window -> 'allow'."""
        rm = make_rm(sample_config, mock_trading_client)
        result = rm.check_pdt_limit("AAPL", "2026-03-22")
        assert result == "allow"

    def test_warn_at_two(self, sample_config, mock_trading_client, plugin_data_dir):
        """2 trades in window -> 'warn'."""
        rm = make_rm(sample_config, mock_trading_client)
        rm.record_day_trade("AAPL", "2026-03-22")
        rm.record_day_trade("MSFT", "2026-03-22")
        result = rm.check_pdt_limit("GOOG", "2026-03-22")
        assert result == "warn"

    def test_block_at_three(self, sample_config, mock_trading_client, plugin_data_dir):
        """3 trades in window -> 'block'."""
        rm = make_rm(sample_config, mock_trading_client)
        rm.record_day_trade("AAPL", "2026-03-22")
        rm.record_day_trade("MSFT", "2026-03-22")
        rm.record_day_trade("SPY", "2026-03-22")
        result = rm.check_pdt_limit("GOOG", "2026-03-22")
        assert result == "block"

    def test_rolling_window_expires(self, sample_config, mock_trading_client, plugin_data_dir):
        """Trades older than 7 days are excluded from the count."""
        rm = make_rm(sample_config, mock_trading_client)
        # Record 3 trades 8 days ago — they must be outside the 7-day window
        rm.record_day_trade("AAPL", "2026-03-14")
        rm.record_day_trade("MSFT", "2026-03-14")
        rm.record_day_trade("SPY", "2026-03-14")
        # Today = 2026-03-22 — 8 days later
        result = rm.check_pdt_limit("GOOG", "2026-03-22")
        assert result == "allow"

    def test_persists_to_json(self, sample_config, mock_trading_client, plugin_data_dir):
        """record_day_trade writes to pdt_trades.json in CLAUDE_PLUGIN_DATA."""
        rm = make_rm(sample_config, mock_trading_client)
        rm.record_day_trade("AAPL", "2026-03-22")
        json_file = plugin_data_dir / "pdt_trades.json"
        assert json_file.exists(), "pdt_trades.json must be written by record_day_trade"
        data = json.loads(json_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# TestClaudeDecides
# ---------------------------------------------------------------------------


class TestClaudeDecides:
    """RISK-05: claude_decides mode clamps size_override_pct within [50%, 150%] of max_position_pct."""

    def test_clamps_high_override(self, sample_config, mock_trading_client, plugin_data_dir):
        """Override 200% is clamped to 150% of max_position_pct (5% -> 7.5%)."""
        rm = make_rm(sample_config, mock_trading_client)
        # max_position_pct = 5.0, 200% override -> clamp to 7.5%
        # equity=10000, 7.5% = 750, price=50 -> 15 shares
        shares = rm.calculate_position_size("AAPL", current_price=50.0, size_override_pct=200.0)
        assert shares == 15  # 750 / 50 = 15

    def test_clamps_low_override(self, sample_config, mock_trading_client, plugin_data_dir):
        """Override 1% is clamped up to 50% of max_position_pct (5% -> 2.5%)."""
        rm = make_rm(sample_config, mock_trading_client)
        # max_position_pct = 5.0, lower bound = 2.5%
        # override = 1% -> below lower bound -> clamp to 2.5%
        # equity=10000, 2.5% = 250, price=50 -> 5 shares
        shares = rm.calculate_position_size("AAPL", current_price=50.0, size_override_pct=1.0)
        assert shares == 5  # 250 / 50 = 5

    def test_accepts_valid_override(self, sample_config, mock_trading_client, plugin_data_dir):
        """Override within bounds is used as-is."""
        rm = make_rm(sample_config, mock_trading_client)
        # max_position_pct = 5.0, valid range = [2.5, 7.5]
        # override = 6.0 -> within bounds, use 6%
        # equity=10000, 6% = 600, price=50 -> 12 shares
        shares = rm.calculate_position_size("AAPL", current_price=50.0, size_override_pct=6.0)
        assert shares == 12  # 600 / 50 = 12


# ---------------------------------------------------------------------------
# TestRetryLogic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """RISK-04 / order safety: submit_with_retry exponential backoff behavior."""

    def _make_api_error(self, status_code):
        """Create a mock APIError-like exception with a status_code attribute."""
        err = Exception(f"API error {status_code}")
        err.status_code = status_code
        return err

    def test_succeeds_first_attempt(self, sample_config, mock_trading_client, plugin_data_dir):
        """If first attempt succeeds, return order immediately."""
        mock_order = MagicMock()
        mock_trading_client.submit_order.return_value = mock_order
        rm = make_rm(sample_config, mock_trading_client)
        request = MagicMock()
        result = rm.submit_with_retry(request, symbol="AAPL")
        assert result is mock_order
        assert mock_trading_client.submit_order.call_count == 1

    def test_retries_on_server_error(self, sample_config, mock_trading_client, plugin_data_dir):
        """5xx error on attempt 1 then success on attempt 2."""
        mock_order = MagicMock()
        server_err = self._make_api_error(500)
        mock_trading_client.submit_order.side_effect = [server_err, mock_order]
        # get_open_position raises (no ghost)
        mock_trading_client.get_open_position.side_effect = Exception("No position")
        rm = make_rm(sample_config, mock_trading_client)
        request = MagicMock()
        with patch("scripts.risk_manager.time.sleep"):
            result = rm.submit_with_retry(request, symbol="AAPL")
        assert result is mock_order
        assert mock_trading_client.submit_order.call_count == 2

    def test_skips_retry_on_422(self, sample_config, mock_trading_client, plugin_data_dir):
        """422 validation error returns None immediately without retrying."""
        err = self._make_api_error(422)
        mock_trading_client.submit_order.side_effect = err
        rm = make_rm(sample_config, mock_trading_client)
        request = MagicMock()
        with patch("scripts.risk_manager.time.sleep"):
            result = rm.submit_with_retry(request, symbol="AAPL")
        assert result is None
        assert mock_trading_client.submit_order.call_count == 1

    def test_skips_retry_on_403(self, sample_config, mock_trading_client, plugin_data_dir):
        """403 forbidden returns None immediately without retrying."""
        err = self._make_api_error(403)
        mock_trading_client.submit_order.side_effect = err
        rm = make_rm(sample_config, mock_trading_client)
        request = MagicMock()
        with patch("scripts.risk_manager.time.sleep"):
            result = rm.submit_with_retry(request, symbol="AAPL")
        assert result is None
        assert mock_trading_client.submit_order.call_count == 1


# ---------------------------------------------------------------------------
# TestGhostPosition
# ---------------------------------------------------------------------------


class TestGhostPosition:
    """Order safety: ghost position detection before retry."""

    def _make_api_error(self, status_code):
        err = Exception(f"API error {status_code}")
        err.status_code = status_code
        return err

    def test_detects_ghost_before_retry(self, sample_config, mock_trading_client, plugin_data_dir):
        """If a position already exists after failure, skip retry and return None."""
        server_err = self._make_api_error(500)
        mock_trading_client.submit_order.side_effect = server_err
        # get_open_position returns a position (ghost detected)
        mock_trading_client.get_open_position.return_value = MagicMock()
        mock_trading_client.get_open_position.side_effect = None
        rm = make_rm(sample_config, mock_trading_client)
        request = MagicMock()
        with patch("scripts.risk_manager.time.sleep"):
            result = rm.submit_with_retry(request, symbol="AAPL")
        # Ghost detected — no second submit attempt
        assert mock_trading_client.submit_order.call_count == 1
        # Result is None (did not retry, but ghost was logged)
        assert result is None

    def test_retries_when_no_ghost(self, sample_config, mock_trading_client, plugin_data_dir):
        """If no position exists after failure, continue retry."""
        mock_order = MagicMock()
        server_err = self._make_api_error(500)
        mock_trading_client.submit_order.side_effect = [server_err, mock_order]
        # No position exists — safe to retry
        mock_trading_client.get_open_position.side_effect = Exception("No position")
        rm = make_rm(sample_config, mock_trading_client)
        request = MagicMock()
        with patch("scripts.risk_manager.time.sleep"):
            result = rm.submit_with_retry(request, symbol="AAPL")
        assert result is mock_order
        assert mock_trading_client.submit_order.call_count == 2


# ---------------------------------------------------------------------------
# TestAgentDefinition
# ---------------------------------------------------------------------------


class TestAgentDefinition:
    """PLUG-03: risk-manager agent exists with correct frontmatter."""

    def test_agent_file_exists(self):
        agent_path = Path(__file__).parent.parent / "agents" / "risk-manager.md"
        assert agent_path.exists(), f"Agent file missing: {agent_path}"

    def test_agent_has_model_sonnet(self):
        agent_path = Path(__file__).parent.parent / "agents" / "risk-manager.md"
        content = agent_path.read_text()
        assert "model: sonnet" in content, "Agent must use model: sonnet"

    def test_agent_has_name(self):
        agent_path = Path(__file__).parent.parent / "agents" / "risk-manager.md"
        content = agent_path.read_text()
        assert "name: risk-manager" in content, "Agent must have name: risk-manager"


# ---------------------------------------------------------------------------
# TestPreToolUseHook
# ---------------------------------------------------------------------------


class TestPreToolUseHook:
    """PLUG-07: validate-order.sh exists and is executable."""

    def test_hook_script_exists(self):
        hook_path = Path(__file__).parent.parent / "hooks" / "validate-order.sh"
        assert hook_path.exists(), f"Hook script missing: {hook_path}"

    def test_hook_script_is_executable(self):
        import stat
        hook_path = Path(__file__).parent.parent / "hooks" / "validate-order.sh"
        mode = hook_path.stat().st_mode
        assert mode & stat.S_IXUSR, "Hook script must be executable"

    def test_hook_uses_json_deny_not_exit_code(self):
        hook_path = Path(__file__).parent.parent / "hooks" / "validate-order.sh"
        content = hook_path.read_text()
        assert "permissionDecision" in content, "Hook must use permissionDecision JSON"
        assert 'exit 2' not in content, "Hook must NOT use exit code 2 for denial"

    def test_hook_checks_circuit_breaker_flag(self):
        hook_path = Path(__file__).parent.parent / "hooks" / "validate-order.sh"
        content = hook_path.read_text()
        assert "circuit_breaker.flag" in content, "Hook must check circuit breaker flag"


# ---------------------------------------------------------------------------
# TestHooksJson
# ---------------------------------------------------------------------------


class TestHooksJson:
    """PLUG-07: hooks.json has PreToolUse entry."""

    def test_hooks_json_has_pretooluse(self):
        hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
        import json
        hooks = json.loads(hooks_path.read_text())
        assert "PreToolUse" in hooks["hooks"], "hooks.json must have PreToolUse entry"

    def test_pretooluse_targets_bash(self):
        hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
        import json
        hooks = json.loads(hooks_path.read_text())
        matcher = hooks["hooks"]["PreToolUse"][0]["matcher"]
        assert matcher == "Bash", f"PreToolUse matcher must be 'Bash', got '{matcher}'"

    def test_pretooluse_references_validate_order(self):
        hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
        import json
        hooks = json.loads(hooks_path.read_text())
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert "validate-order.sh" in command, "PreToolUse must reference validate-order.sh"

    def test_session_start_preserved(self):
        hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
        import json
        hooks = json.loads(hooks_path.read_text())
        assert "SessionStart" in hooks["hooks"], "SessionStart hook must be preserved"
