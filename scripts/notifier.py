"""Notification dispatch module for autonomous trading bot.

Sends notifications to configured channels (Slack webhook, optional email)
on critical events: circuit breaker, large wins/losses, end-of-day summary.

Uses stdlib urllib.request only — no external requests library required.
Handles missing config and unreachable URLs gracefully (logs, returns False).
"""
import json
import urllib.error
import urllib.request

from loguru import logger


class Notifier:
    """Dispatches notifications to configured channels.

    Args:
        config: Trading configuration dict from config.json.
                Reads from config["notifications"] for channel settings.

    Channel configuration (all optional):
        config["notifications"]["slack_webhook_url"]: Slack incoming webhook URL
        config["notifications"]["email_enabled"]: bool, default False
        config["notifications"]["email_to"]: recipient email address
        config["notifications"]["large_event_threshold_pct"]: float, default 2.0
    """

    def __init__(self, config: dict) -> None:
        notifications = config.get("notifications", {})

        self.slack_webhook_url: str | None = notifications.get("slack_webhook_url")
        self.email_enabled: bool = notifications.get("email_enabled", False)
        self.email_to: str | None = notifications.get("email_to")
        self.large_event_threshold_pct: float = float(
            notifications.get("large_event_threshold_pct", 2.0)
        )

        enabled_channels = []
        if self.slack_webhook_url:
            enabled_channels.append("slack")
        if self.email_enabled:
            enabled_channels.append("email")

        if enabled_channels:
            logger.info("Notifier initialized. Channels: {}", enabled_channels)
        else:
            logger.warning(
                "Notifier initialized with no channels configured. "
                "Set config['notifications']['slack_webhook_url'] to enable Slack alerts."
            )

    # ------------------------------------------------------------------
    # Primary dispatch
    # ------------------------------------------------------------------

    def send(self, subject: str, message: str, level: str = "info") -> bool:
        """Dispatch a notification to all enabled channels.

        Args:
            subject: Short notification subject line.
            message: Full notification body.
            level: Severity level string ('info', 'warning', 'critical').
                   Currently informational — future channels may use this.

        Returns:
            True if at least one channel succeeded. False if no channels
            are configured or all channels failed.
        """
        any_success = False

        if self.slack_webhook_url:
            result = self.send_slack(subject, message)
            if result:
                any_success = True

        # Email is a stub for future implementation
        if self.email_enabled and self.email_to:
            logger.info(
                "Notifier: email channel not yet implemented — "
                "would send '{}' to {}",
                subject, self.email_to,
            )

        if not self.slack_webhook_url and not (self.email_enabled and self.email_to):
            logger.warning(
                "Notifier.send: no channels configured — notification '{}' not sent",
                subject,
            )
            return False

        return any_success

    # ------------------------------------------------------------------
    # Slack channel
    # ------------------------------------------------------------------

    def send_slack(self, subject: str, message: str) -> bool:
        """Post a notification to the configured Slack webhook URL.

        Uses stdlib urllib.request — no external dependencies.

        Args:
            subject: Bold subject line (wrapped in *asterisks* for Slack markdown).
            message: Notification body text.

        Returns:
            True on successful POST. False on URLError or missing webhook URL.
        """
        if not self.slack_webhook_url:
            logger.warning("Notifier.send_slack: no slack_webhook_url configured")
            return False

        payload = {"text": f"*{subject}*\n{message}"}
        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            self.slack_webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request) as response:
                status = response.status
                logger.info(
                    "Slack notification sent: '{}' (HTTP {})",
                    subject, status,
                )
                return True
        except urllib.error.URLError as exc:
            logger.error(
                "Notifier.send_slack failed for '{}': {}",
                subject, exc,
            )
            return False

    # ------------------------------------------------------------------
    # Large event detection
    # ------------------------------------------------------------------

    def is_large_event(self, pnl: float, equity: float) -> bool:
        """Determine whether a P&L amount constitutes a large event.

        Args:
            pnl: Realized profit or loss (can be negative for losses).
            equity: Current account equity for percentage calculation.

        Returns:
            True when abs(pnl) / equity > large_event_threshold_pct / 100.
            False when equity is 0 or the event is below the threshold.
        """
        if equity <= 0:
            return False

        pnl_pct = abs(pnl) / equity
        threshold = self.large_event_threshold_pct / 100

        return pnl_pct > threshold
