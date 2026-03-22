"""NDJSON audit logger for Claude trade decisions.

Every Claude recommendation and its execution outcome is written as a single
JSON line to {data_dir}/audit/claude_decisions.ndjson. This provides a
persistent, inspectable audit trail for all autonomous trading decisions made
by the Claude analysis pipeline.

Usage:
    from scripts.audit_logger import AuditLogger
    from scripts.types import ClaudeRecommendation

    audit_logger = AuditLogger()
    audit_logger.log_recommendation(rec)
    audit_logger.log_execution_result(rec, status="submitted", order_id="abc123")
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from scripts.types import ClaudeRecommendation


class AuditLogger:
    """NDJSON audit logger for Claude trade decisions.

    Every Claude recommendation and its execution outcome is written
    as a single JSON line to {data_dir}/audit/claude_decisions.ndjson.

    Each session is identified by a session_id derived from the UTC timestamp
    at instantiation. This allows filtering decisions by session when reviewing
    audit history.

    Args:
        data_dir: Base directory for audit files. Defaults to
                  CLAUDE_PLUGIN_DATA environment variable, or the current
                  working directory if not set.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        data_dir = data_dir or Path(os.environ.get("CLAUDE_PLUGIN_DATA", "."))
        self.audit_dir = data_dir / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.audit_dir / "claude_decisions.ndjson"
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    def log_recommendation(self, rec: ClaudeRecommendation) -> None:
        """Write a Claude recommendation to the audit log as an NDJSON line.

        Captures all fields from the recommendation plus a UTC timestamp and
        session identifier for filtering.

        Args:
            rec: ClaudeRecommendation from ClaudeAnalyzer.parse_response().
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "type": "recommendation",
            "symbol": rec.symbol,
            "action": rec.action,
            "confidence": rec.confidence,
            "reasoning": rec.reasoning,
            "strategy": rec.strategy,
            "atr": rec.atr,
            "stop_price": rec.stop_price,
        }
        with open(self.audit_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(
            "Audit: logged recommendation for {} — {} (confidence={:.2f})",
            rec.symbol,
            rec.action,
            rec.confidence,
        )

    def log_execution_result(
        self,
        rec: ClaudeRecommendation,
        status: str,
        order_id: str | None = None,
        reason: str = "",
    ) -> None:
        """Write order execution outcome to the audit log as an NDJSON line.

        Records the outcome alongside the original recommendation fields so
        every execution decision is fully traceable.

        Args:
            rec: The ClaudeRecommendation that was executed.
            status: Execution outcome — "submitted", "blocked", or "failed".
            order_id: Alpaca order ID if submission succeeded, None otherwise.
            reason: Human-readable explanation for blocked or failed outcomes.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "type": "execution",
            "symbol": rec.symbol,
            "action": rec.action,
            "status": status,
            "order_id": order_id,
            "reason": reason,
            "confidence": rec.confidence,
            "reasoning": rec.reasoning,
        }
        with open(self.audit_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(
            "Audit: logged execution result for {} — status={} order_id={}",
            rec.symbol,
            status,
            order_id,
        )

    def get_session_decisions(self) -> list[dict]:
        """Return all logged decisions from the current session.

        Reads the audit file and filters entries by session_id. Lines that
        fail JSON parsing are silently skipped.

        Returns:
            List of dicts — all audit entries (recommendations + executions)
            logged in this session. Returns [] if the audit file does not exist.
        """
        if not self.audit_file.exists():
            return []
        decisions = []
        for line in self.audit_file.read_text().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("session_id") == self.session_id:
                    decisions.append(entry)
            except json.JSONDecodeError:
                continue
        return decisions
