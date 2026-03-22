"""Unit tests for AuditLogger.

Tests use tmp_path fixture for isolated file I/O — no LLM or Alpaca API needed.
All ClaudeRecommendation instances are constructed manually.
"""
import json
from pathlib import Path

import pytest

from scripts.audit_logger import AuditLogger
from scripts.types import ClaudeRecommendation


def _make_rec(
    symbol: str = "AAPL",
    action: str = "BUY",
    confidence: float = 0.8,
    reasoning: str = "RSI oversold",
    strategy: str = "momentum",
    atr: float = 1.5,
    stop_price: float = 148.50,
) -> ClaudeRecommendation:
    """Helper to construct a ClaudeRecommendation for tests."""
    return ClaudeRecommendation(
        symbol=symbol,
        action=action,  # type: ignore[arg-type]
        confidence=confidence,
        reasoning=reasoning,
        strategy=strategy,
        atr=atr,
        stop_price=stop_price,
    )


# ---------------------------------------------------------------------------
# Test 1: log_recommendation writes a single NDJSON line with all fields
# ---------------------------------------------------------------------------

def test_log_recommendation_writes_ndjson_line(tmp_path: Path) -> None:
    """log_recommendation() writes one NDJSON line with all ClaudeRecommendation fields plus timestamp."""
    logger = AuditLogger(data_dir=tmp_path)
    rec = _make_rec()

    logger.log_recommendation(rec)

    # Audit file must exist
    assert logger.audit_file.exists()

    lines = logger.audit_file.read_text().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["type"] == "recommendation"
    assert entry["symbol"] == "AAPL"
    assert entry["action"] == "BUY"
    assert entry["confidence"] == 0.8
    assert entry["reasoning"] == "RSI oversold"
    assert entry["strategy"] == "momentum"
    assert entry["atr"] == 1.5
    assert entry["stop_price"] == 148.50
    assert "timestamp" in entry
    assert "session_id" in entry


# ---------------------------------------------------------------------------
# Test 2: log_recommendation appends (does not overwrite) on subsequent calls
# ---------------------------------------------------------------------------

def test_log_recommendation_appends_on_subsequent_calls(tmp_path: Path) -> None:
    """log_recommendation() appends to the audit file — does not overwrite."""
    logger = AuditLogger(data_dir=tmp_path)
    rec1 = _make_rec(symbol="AAPL", action="BUY")
    rec2 = _make_rec(symbol="TSLA", action="SELL")

    logger.log_recommendation(rec1)
    logger.log_recommendation(rec2)

    lines = logger.audit_file.read_text().splitlines()
    assert len(lines) == 2

    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])
    assert entry1["symbol"] == "AAPL"
    assert entry2["symbol"] == "TSLA"


# ---------------------------------------------------------------------------
# Test 3: log_execution_result writes order outcome alongside recommendation
# ---------------------------------------------------------------------------

def test_log_execution_result_writes_outcome(tmp_path: Path) -> None:
    """log_execution_result() writes execution entry with status, order_id, and reason."""
    logger = AuditLogger(data_dir=tmp_path)
    rec = _make_rec(symbol="MSFT", action="BUY", confidence=0.75)

    logger.log_recommendation(rec)
    logger.log_execution_result(rec, status="submitted", order_id="order-abc-123", reason="")

    lines = logger.audit_file.read_text().splitlines()
    assert len(lines) == 2

    exec_entry = json.loads(lines[1])
    assert exec_entry["type"] == "execution"
    assert exec_entry["symbol"] == "MSFT"
    assert exec_entry["action"] == "BUY"
    assert exec_entry["status"] == "submitted"
    assert exec_entry["order_id"] == "order-abc-123"
    assert exec_entry["confidence"] == 0.75
    assert exec_entry["reasoning"] == rec.reasoning
    assert "timestamp" in exec_entry
    assert "session_id" in exec_entry


def test_log_execution_result_blocked_status(tmp_path: Path) -> None:
    """log_execution_result() correctly logs 'blocked' status when risk manager blocks."""
    logger = AuditLogger(data_dir=tmp_path)
    rec = _make_rec(symbol="NVDA", action="BUY")

    logger.log_execution_result(rec, status="blocked", reason="PDT limit reached")

    lines = logger.audit_file.read_text().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["status"] == "blocked"
    assert entry["reason"] == "PDT limit reached"
    assert entry["order_id"] is None


# ---------------------------------------------------------------------------
# Test 4: Audit file is created in the configured data directory
# ---------------------------------------------------------------------------

def test_audit_file_created_in_data_dir(tmp_path: Path) -> None:
    """Audit file is created under {data_dir}/audit/claude_decisions.ndjson."""
    logger = AuditLogger(data_dir=tmp_path)

    # Directory should be created even before writing
    assert logger.audit_dir.exists()
    assert logger.audit_dir == tmp_path / "audit"

    # File path should be correct
    assert logger.audit_file == tmp_path / "audit" / "claude_decisions.ndjson"

    # Write a record and verify placement
    rec = _make_rec()
    logger.log_recommendation(rec)
    assert logger.audit_file.exists()


# ---------------------------------------------------------------------------
# Test 5: get_session_decisions returns all recommendations from current session
# ---------------------------------------------------------------------------

def test_get_session_decisions_returns_current_session(tmp_path: Path) -> None:
    """get_session_decisions() returns all entries for the current session as a list of dicts."""
    logger = AuditLogger(data_dir=tmp_path)
    rec1 = _make_rec(symbol="AAPL")
    rec2 = _make_rec(symbol="GOOG", action="SELL")

    logger.log_recommendation(rec1)
    logger.log_recommendation(rec2)
    logger.log_execution_result(rec1, status="submitted", order_id="ord-1")

    decisions = logger.get_session_decisions()
    assert len(decisions) == 3

    # All decisions should belong to the current session
    for d in decisions:
        assert d["session_id"] == logger.session_id


def test_get_session_decisions_empty_before_any_writes(tmp_path: Path) -> None:
    """get_session_decisions() returns an empty list when no entries have been written."""
    logger = AuditLogger(data_dir=tmp_path)
    assert logger.get_session_decisions() == []


def test_get_session_decisions_filters_by_session(tmp_path: Path) -> None:
    """get_session_decisions() returns only current session entries, not previous sessions."""
    logger1 = AuditLogger(data_dir=tmp_path)
    rec1 = _make_rec(symbol="AAPL")
    logger1.log_recommendation(rec1)

    # Simulate a new session by creating a new AuditLogger with the same data_dir
    # but a different session_id
    logger2 = AuditLogger(data_dir=tmp_path)
    # Manually override session_id to ensure they differ
    logger2.session_id = "99999999T999999"
    rec2 = _make_rec(symbol="GOOG")
    logger2.log_recommendation(rec2)

    # logger2 should only see its own session entry
    decisions = logger2.get_session_decisions()
    assert len(decisions) == 1
    assert decisions[0]["symbol"] == "GOOG"
