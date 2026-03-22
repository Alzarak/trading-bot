"""Tests for Notifier: notification dispatch to configured channels.

Tests cover:
- init with no notifications config
- send() with no channels
- send_slack() with mocked urllib
- send_slack() with URLError
- is_large_event() threshold logic
"""
import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def notifier_no_config():
    """Notifier with no notifications config — no channels configured."""
    from scripts.notifier import Notifier
    return Notifier(config={})


@pytest.fixture
def notifier_with_slack():
    """Notifier configured with a Slack webhook URL."""
    from scripts.notifier import Notifier
    return Notifier(config={
        "notifications": {
            "slack_webhook_url": "https://hooks.slack.com/test/webhook",
            "large_event_threshold_pct": 2.0,
        }
    })


@pytest.fixture
def notifier_custom_threshold():
    """Notifier with custom large_event_threshold_pct."""
    from scripts.notifier import Notifier
    return Notifier(config={
        "notifications": {
            "slack_webhook_url": "https://hooks.slack.com/test/webhook",
            "large_event_threshold_pct": 3.0,
        }
    })


# ---------------------------------------------------------------------------
# TestNotifierInit
# ---------------------------------------------------------------------------


class TestNotifierInit:
    """Verify Notifier initializes correctly from config."""

    def test_init_with_empty_config_does_not_crash(self):
        """Notifier with no config at all does not raise."""
        from scripts.notifier import Notifier
        notifier = Notifier(config={})
        assert notifier is not None

    def test_init_with_no_notifications_key(self, notifier_no_config):
        """Notifier with no 'notifications' key has slack_webhook_url = None."""
        assert notifier_no_config.slack_webhook_url is None

    def test_init_with_slack_webhook(self, notifier_with_slack):
        """Notifier reads slack_webhook_url from config['notifications']."""
        assert notifier_with_slack.slack_webhook_url == "https://hooks.slack.com/test/webhook"

    def test_init_default_threshold(self, notifier_no_config):
        """Notifier defaults large_event_threshold_pct to 2.0."""
        assert notifier_no_config.large_event_threshold_pct == pytest.approx(2.0)

    def test_init_custom_threshold(self, notifier_custom_threshold):
        """Notifier reads large_event_threshold_pct from config."""
        assert notifier_custom_threshold.large_event_threshold_pct == pytest.approx(3.0)

    def test_init_email_disabled_by_default(self, notifier_no_config):
        """email_enabled defaults to False."""
        assert notifier_no_config.email_enabled is False


# ---------------------------------------------------------------------------
# TestNotifierSend
# ---------------------------------------------------------------------------


class TestNotifierSend:
    """Tests for Notifier.send()."""

    def test_send_with_no_channels_returns_false(self, notifier_no_config):
        """send() with no configured channels returns False."""
        result = notifier_no_config.send("Test Subject", "Test message")
        assert result is False

    def test_send_with_no_channels_does_not_crash(self, notifier_no_config):
        """send() with no channels logs warning but does not raise."""
        # Should not raise
        notifier_no_config.send("Test", "Message")

    def test_send_calls_send_slack_when_configured(self, notifier_with_slack):
        """send() delegates to send_slack when slack_webhook_url is set."""
        with patch.object(notifier_with_slack, "send_slack", return_value=True) as mock_slack:
            result = notifier_with_slack.send("Subject", "Message")
            mock_slack.assert_called_once_with("Subject", "Message")
            assert result is True

    def test_send_returns_true_when_slack_succeeds(self, notifier_with_slack):
        """send() returns True when at least one channel succeeds."""
        with patch.object(notifier_with_slack, "send_slack", return_value=True):
            result = notifier_with_slack.send("Subject", "Message")
            assert result is True

    def test_send_returns_false_when_all_channels_fail(self, notifier_with_slack):
        """send() returns False when all channels fail."""
        with patch.object(notifier_with_slack, "send_slack", return_value=False):
            result = notifier_with_slack.send("Subject", "Message")
            assert result is False


# ---------------------------------------------------------------------------
# TestNotifierSendSlack
# ---------------------------------------------------------------------------


class TestNotifierSendSlack:
    """Tests for Notifier.send_slack()."""

    def test_send_slack_posts_json_payload(self, notifier_with_slack):
        """send_slack() POSTs JSON with text field to the webhook URL."""
        mock_response = MagicMock()
        mock_response.status = 200

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            notifier_with_slack.send_slack("Test Subject", "Test Message")

            # Verify urlopen was called
            mock_urlopen.assert_called_once()

    def test_send_slack_payload_contains_subject_and_message(self, notifier_with_slack):
        """send_slack() encodes subject and message in the JSON payload."""
        captured_request = {}

        def capture_request(request, *args, **kwargs):
            captured_request["data"] = request.data
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            return mock_ctx

        with patch("urllib.request.urlopen", side_effect=capture_request):
            notifier_with_slack.send_slack("My Subject", "My Message")

        if "data" in captured_request:
            payload = json.loads(captured_request["data"])
            assert "My Subject" in payload["text"]
            assert "My Message" in payload["text"]

    def test_send_slack_returns_true_on_success(self, notifier_with_slack):
        """send_slack() returns True when urlopen succeeds."""
        mock_response = MagicMock()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            result = notifier_with_slack.send_slack("Subject", "Message")

        assert result is True

    def test_send_slack_returns_false_on_url_error(self, notifier_with_slack):
        """send_slack() catches URLError and returns False without raising."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            result = notifier_with_slack.send_slack("Subject", "Message")

        assert result is False

    def test_send_slack_does_not_crash_on_url_error(self, notifier_with_slack):
        """send_slack() handles URLError silently — logs error but does not raise."""
        import urllib.error
        # Should not raise
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            notifier_with_slack.send_slack("Subject", "Message")

    def test_send_slack_uses_urllib_not_requests(self, notifier_with_slack):
        """send_slack() uses urllib.request — no requests dependency."""
        import importlib
        import scripts.notifier as notifier_module
        source = open(notifier_module.__file__).read()
        assert "import requests" not in source
        assert "urllib.request" in source

    def test_send_slack_with_no_webhook_url_returns_false(self, notifier_no_config):
        """send_slack() returns False (or skips) when no webhook URL configured."""
        result = notifier_no_config.send_slack("Subject", "Message")
        assert result is False


# ---------------------------------------------------------------------------
# TestNotifierIsLargeEvent
# ---------------------------------------------------------------------------


class TestNotifierIsLargeEvent:
    """Tests for Notifier.is_large_event()."""

    def test_large_event_true_when_above_threshold(self, notifier_with_slack):
        """is_large_event returns True when abs(pnl)/equity > threshold_pct/100."""
        # threshold = 2.0%, equity = 10000, pnl = 300 -> 3% > 2% -> True
        result = notifier_with_slack.is_large_event(pnl=300.0, equity=10000.0)
        assert result is True

    def test_large_event_false_when_below_threshold(self, notifier_with_slack):
        """is_large_event returns False when abs(pnl)/equity <= threshold_pct/100."""
        # threshold = 2.0%, equity = 10000, pnl = 100 -> 1% < 2% -> False
        result = notifier_with_slack.is_large_event(pnl=100.0, equity=10000.0)
        assert result is False

    def test_large_event_true_for_losses(self, notifier_with_slack):
        """is_large_event uses abs(pnl) — large losses also trigger."""
        # threshold = 2.0%, equity = 10000, pnl = -300 -> 3% > 2% -> True
        result = notifier_with_slack.is_large_event(pnl=-300.0, equity=10000.0)
        assert result is True

    def test_large_event_false_for_small_loss(self, notifier_with_slack):
        """is_large_event returns False for small losses below threshold."""
        # threshold = 2.0%, equity = 10000, pnl = -100 -> 1% < 2% -> False
        result = notifier_with_slack.is_large_event(pnl=-100.0, equity=10000.0)
        assert result is False

    def test_large_event_with_custom_threshold(self, notifier_custom_threshold):
        """is_large_event uses large_event_threshold_pct from config."""
        # threshold = 3.0%, equity = 10000, pnl = 250 -> 2.5% < 3% -> False
        result = notifier_custom_threshold.is_large_event(pnl=250.0, equity=10000.0)
        assert result is False

    def test_large_event_above_custom_threshold(self, notifier_custom_threshold):
        """is_large_event returns True when above custom threshold."""
        # threshold = 3.0%, equity = 10000, pnl = 350 -> 3.5% > 3% -> True
        result = notifier_custom_threshold.is_large_event(pnl=350.0, equity=10000.0)
        assert result is True

    def test_large_event_zero_equity_returns_false(self, notifier_with_slack):
        """is_large_event returns False when equity is 0 (avoid division by zero)."""
        result = notifier_with_slack.is_large_event(pnl=100.0, equity=0.0)
        assert result is False

    def test_large_event_exactly_at_threshold(self, notifier_with_slack):
        """is_large_event at exactly threshold percentage returns False (not strictly greater)."""
        # threshold = 2.0%, equity = 10000, pnl = 200 -> exactly 2% -> not strictly greater
        result = notifier_with_slack.is_large_event(pnl=200.0, equity=10000.0)
        assert result is False
