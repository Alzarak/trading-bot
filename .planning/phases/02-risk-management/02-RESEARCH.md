# Phase 2: Risk Management - Research

**Researched:** 2026-03-21
**Domain:** Python risk management module, Claude Code plugin PreToolUse hook, Alpaca API error handling
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None — all implementation choices are at Claude's discretion (pure infrastructure phase).

### Claude's Discretion
All implementation choices: module structure, class design, test strategy, file layout.

### Deferred Ideas (OUT OF SCOPE)
None.

### Critical Note from Orchestrator
ALP-04 (Alpaca MCP server) has been DROPPED. No `.mcp.json` exists. All Alpaca access is SDK-only via alpaca-py in Python scripts. The PreToolUse hook matcher must NOT target MCP tool names.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RISK-01 | Bot halts all trading when daily drawdown exceeds configured threshold (circuit breaker) | Circuit breaker formula from risk-rules.md; `get_account().equity` pattern from alpaca-api-patterns.md |
| RISK-02 | Bot tracks day trade count and warns/blocks when approaching PDT limit (4 trades per 5 days under $25K) | PDT logic from risk-rules.md; rolling 5-business-day window tracking; warn at 2, block at 3 |
| RISK-03 | Bot wraps all API calls with exponential backoff and retry logic | Retry pattern from alpaca-api-patterns.md; `APIError` with status_code; skip 422/403 |
| RISK-04 | Bot handles network failures during order submission without creating ghost positions | Ghost position check via `get_open_position(symbol)`; idempotency via `client_order_id=uuid4()` |
| RISK-05 | Claude dynamically adjusts aggression based on market conditions and recent performance | `claude_decides` mode: position size 50%–150% of configured pct, entry tighten only, stop widen only |
| POS-01 | Bot sizes positions as percentage of account equity (configurable) | Formula: `position_value = equity * (max_position_pct / 100)`; `shares = floor(position_value / price)` |
| POS-02 | Bot enforces maximum position count limit | `client.get_all_positions()` count check before entry; `max_positions` default 10 |
| PLUG-03 | Separate agent for risk management validation | `agents/risk-manager.md` with YAML frontmatter; model: sonnet |
| PLUG-07 | PreToolUse hook validates safety constraints before order submission | `hooks/hooks.json` PreToolUse entry; bash script reads stdin JSON, exits 2 to block |
</phase_requirements>

---

## Summary

Phase 2 delivers the safety substrate that all future order execution depends on. The core deliverable is `scripts/risk_manager.py` — a pure Python module that enforces circuit breaker, position sizing, PDT tracking, max position limits, and exponential backoff retry. No execution code exists yet; this phase creates the guardrails that Phase 3 will call into.

The second deliverable is the PreToolUse safety hook. Since there is no MCP server (ALP-04 dropped), the hook targets `Bash` tool calls that invoke order-submission scripts. The hook reads stdin JSON, checks the command string for order-submission patterns, and either exits 0 (allow) or emits a JSON deny decision (exit 0 with `permissionDecision: "deny"` in hookSpecificOutput). A separate `agents/risk-manager.md` agent definition is also created for PLUG-03.

All risk logic is already fully specified in `references/risk-rules.md` — research confirms the existing specification is complete and accurate. No new design decisions are required; the task is pure implementation.

**Primary recommendation:** Implement `scripts/risk_manager.py` as a class (`RiskManager`) that accepts a `BotConfig`-like dict/object and exposes methods: `check_circuit_breaker()`, `calculate_position_size()`, `check_pdt_limit()`, `check_position_count()`, and `submit_with_retry()`. Each method is independently testable without Alpaca credentials.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alpaca-py | 0.43.2 | `TradingClient.get_account()`, `get_all_positions()`, `get_open_position()`, `submit_order()` | Only maintained Alpaca SDK; pinned in requirements.txt |
| pydantic-settings | 2.x | Config loading from JSON/env | Already used by project; consistent with alpaca-py pydantic v2 |
| loguru | 0.7+ | Structured logging for circuit breaker events, PDT warnings, retry attempts | Already in requirements.txt; critical for unattended operation audit |
| stdlib: `math`, `uuid`, `time`, `datetime`, `zoneinfo` | stdlib | `floor()` for share calc; `uuid4()` for order idempotency; `time.sleep()` for backoff; `ZoneInfo` for ET | No extra install required |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| alpaca.common.exceptions.APIError | (bundled with alpaca-py) | Catch API errors by `status_code` | In `submit_with_retry()` to skip 422/403 |
| jq | system binary | Parse stdin JSON in PreToolUse bash hook | Already available on Linux; used in hook script |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure class `RiskManager` | `@dataclass` or functional module | Class makes state (circuit_breaker_triggered, pdt_count) encapsulable; cleaner for Phase 3 integration |
| Bash hook script | Python hook script | Bash is simpler for the hook's narrow job (parse JSON, check string, emit decision); Python would require venv activation in hook context |

**Installation:** No new packages required. All dependencies already in `requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure (Phase 2 additions)
```
scripts/
└── risk_manager.py          # Core risk module (RISK-01 through RISK-05, POS-01, POS-02)
hooks/
├── hooks.json               # UPDATED: add PreToolUse entry (PLUG-07)
└── validate-order.sh        # NEW: PreToolUse hook script
agents/
└── risk-manager.md          # NEW: agent definition (PLUG-03)
tests/
├── conftest.py              # EXISTING: add risk_manager fixtures
└── test_risk_manager.py     # NEW: unit tests for all risk module methods
```

### Pattern 1: RiskManager Class
**What:** Stateful class that holds circuit-breaker state and config values, exposes guard methods.
**When to use:** Phase 3 instantiates one `RiskManager` at startup and calls it before every order.
**Example:**
```python
# Source: references/risk-rules.md + alpaca-api-patterns.md
import math
import uuid
import time
from loguru import logger
from alpaca.common.exceptions import APIError

class RiskManager:
    def __init__(self, config: dict, trading_client):
        self.config = config
        self.client = trading_client
        self.circuit_breaker_triggered = False
        self.start_equity: float | None = None
        self._pdt_trades: list[dict] = []  # [{symbol, date}] — Phase 3 upgrades to SQLite

    def initialize_session(self) -> None:
        """Call once at market open to capture start_equity baseline."""
        account = self.client.get_account()
        self.start_equity = float(account.equity)
        logger.info(f"Session started. Start equity: ${self.start_equity:,.2f}")

    def check_circuit_breaker(self) -> bool:
        """Returns True if trading is HALTED. Logs and sets flag when triggered."""
        if self.circuit_breaker_triggered:
            return True
        account = self.client.get_account()
        current_equity = float(account.equity)
        loss_pct = (self.start_equity - current_equity) / self.start_equity * 100
        if loss_pct >= self.config["max_daily_loss_pct"]:
            logger.critical(
                f"CIRCUIT BREAKER TRIGGERED. Loss: {loss_pct:.2f}% "
                f"(limit: {self.config['max_daily_loss_pct']}%). "
                f"Start equity: ${self.start_equity:,.2f}, current: ${current_equity:,.2f}"
            )
            self.circuit_breaker_triggered = True
            return True
        return False

    def calculate_position_size(self, symbol: str, current_price: float,
                                 size_override_pct: float | None = None) -> int:
        """
        Returns share quantity. Returns 0 if position cannot be taken.
        size_override_pct: used by claude_decides mode (50%-150% of max_position_pct).
        """
        account = self.client.get_account()
        equity = float(account.equity)
        pct = size_override_pct if size_override_pct is not None else self.config["max_position_pct"]
        position_value = equity * (pct / 100)
        # Enforce budget cap
        position_value = min(position_value, self.config["budget_usd"])
        shares = math.floor(position_value / current_price)
        if shares < 1:
            logger.warning(f"Position too small for {symbol} at ${current_price:.2f}")
            return 0
        return shares

    def check_position_count(self) -> bool:
        """Returns True if a new position CAN be taken (count < max_positions)."""
        positions = self.client.get_all_positions()
        max_pos = self.config.get("max_positions", 10)
        if len(positions) >= max_pos:
            logger.warning(f"Max positions reached ({len(positions)}/{max_pos})")
            return False
        return True

    def check_pdt_limit(self, symbol: str, date: str) -> str:
        """
        Returns: 'allow' | 'warn' | 'block'.
        date: 'YYYY-MM-DD' string for the proposed trade day.
        NOTE: In-memory tracking only in Phase 2. Phase 3 upgrades to SQLite.
        """
        from datetime import datetime, timedelta
        today = datetime.strptime(date, "%Y-%m-%d").date()
        # Rolling 5-business-day window
        window_start = today - timedelta(days=7)  # 7 calendar days covers 5 business days
        recent = [
            t for t in self._pdt_trades
            if datetime.strptime(t["date"], "%Y-%m-%d").date() >= window_start
        ]
        count = len(recent)
        if count >= 3:
            logger.error(f"PDT LIMIT REACHED ({count}/3). Blocking trade for {symbol}.")
            return "block"
        if count == 2:
            logger.warning(f"PDT WARNING: {count}/3 day trades used. Next will hit limit.")
            return "warn"
        return "allow"

    def record_day_trade(self, symbol: str, date: str) -> None:
        """Call when a position is opened and closed on the same day."""
        self._pdt_trades.append({"symbol": symbol, "date": date})

    def submit_with_retry(self, request, symbol: str) -> object | None:
        """
        Submit an order with exponential backoff. Ghost-position-safe.
        Returns filled Order or None on failure.
        """
        wait_times = [1, 2, 4, 8]
        for attempt in range(5):
            try:
                return self.client.submit_order(request)
            except APIError as e:
                if e.status_code in (422, 403):
                    logger.error(f"Order rejected ({e.status_code}), not retrying: {e}")
                    return None
                if attempt < 4:
                    # Ghost position check before retry
                    try:
                        existing = self.client.get_open_position(symbol)
                        if existing:
                            logger.warning(f"Ghost position detected for {symbol}. Skipping retry.")
                            return existing
                    except Exception:
                        pass
                    wait = wait_times[attempt]
                    logger.warning(f"Order attempt {attempt + 1} failed: {e}. Retrying in {wait}s.")
                    time.sleep(wait)
                else:
                    logger.error(f"Order failed after 5 attempts for {symbol}: {e}")
                    return None
        return None
```

### Pattern 2: PreToolUse Hook — Order Safety Gate
**What:** Bash script that reads the tool invocation JSON from stdin, checks if it's an order-submission command, and emits a JSON deny if safety constraints are not met. Registered in `hooks/hooks.json`.
**When to use:** Every time Claude would invoke `Bash` to run a trading script that submits orders.

**hooks/hooks.json update:**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.sh\""
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/validate-order.sh\"",
            "timeout": 10,
            "statusMessage": "Validating order safety..."
          }
        ]
      }
    ]
  }
}
```

**hooks/validate-order.sh pattern:**
```bash
#!/bin/bash
# PreToolUse hook — intercepts Bash calls that invoke order submission scripts.
# Reads tool_input JSON from stdin, checks command string for order-submission patterns.
# Denies if circuit breaker is flagged OR if called outside market hours check.
set -euo pipefail

INPUT=$(cat /dev/stdin)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only gate commands that invoke our trading scripts
if ! echo "$COMMAND" | grep -qE "(submit_order|risk_manager|bot\.py)"; then
  exit 0  # Not an order command — allow
fi

# Check circuit breaker flag file (written by risk_manager.py on trigger)
CB_FLAG="${CLAUDE_PLUGIN_DATA}/circuit_breaker.flag"
if [ -f "$CB_FLAG" ]; then
  jq -n '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": "Circuit breaker is active. Manual restart required before trading resumes."
    }
  }'
  exit 0
fi

exit 0  # All checks passed — allow
```

**Key design decision:** The hook is a lightweight last-resort gate, not the primary risk enforcer. `RiskManager` in Python is the primary enforcer; the hook catches cases where Claude might try to run scripts directly without going through the risk manager.

### Pattern 3: risk-manager Agent Definition
**What:** Agent markdown file with YAML frontmatter, defining the risk-manager as a specialist.
**File:** `agents/risk-manager.md`

```yaml
---
name: risk-manager
description: Risk management specialist agent. Use when validating trade proposals against configured risk limits, checking circuit breaker status, verifying PDT compliance, or calculating position sizes. Always consult before any order execution.
model: sonnet
---
```

Agent body (in the .md after frontmatter): summarize the risk rules from `references/risk-rules.md` in condensed form so the agent has inline context without requiring the skill to load.

### Anti-Patterns to Avoid
- **Stateless circuit breaker:** If circuit_breaker_triggered is not persisted between calls, the bot can trade again after the check function exits. Use a flag file in `CLAUDE_PLUGIN_DATA` as secondary persistence; the in-memory flag is primary.
- **Retry without ghost check:** Retrying after any network error without checking `get_open_position()` first will create double positions. The ghost check must precede every retry.
- **PDT tracking without rolling window:** A simple "count since Monday" breaks mid-week. Use a rolling 7-calendar-day window (which always covers 5 business days) as specified.
- **PreToolUse hook emitting stdout debug text:** Any non-JSON stdout from the hook script corrupts Claude's hook parsing. All debug output MUST go to stderr (`>&2`).
- **Hook exiting with code 2:** The official pattern for denial is exit 0 with `permissionDecision: "deny"` in JSON output, NOT exit code 2. Exit 2 is a blocking error, not a denial decision. (Source: Claude Code hooks docs — the JSON decision method is the structured approach.)
- **max_positions missing from config:** `tests/test_config.py` REQUIRED_FIELDS does not include `max_positions`. The risk manager must use `config.get("max_positions", 10)` with default fallback. If Phase 2 adds `max_positions` to the schema, the test's REQUIRED_FIELDS must be updated and conftest fixture must include it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API error categorization | Custom exception hierarchy or error code table | `alpaca.common.exceptions.APIError.status_code` | Already provides HTTP status codes; 422 vs 403 vs 5xx distinctions are all you need |
| UUID generation for idempotency | Custom timestamp-based order ID | `str(uuid.uuid4())` | UUIDs are globally unique; timestamp IDs can collide under fast retry |
| Business day calculation for PDT window | Calendar math library | Simple 7-calendar-day window | 7 calendar days always includes exactly 5 business days for the rolling PDT window; no holiday edge cases for this simple check |
| JSON stdin parsing in bash hook | Python script or manual string parsing | `jq` | jq is system-standard on Linux; one-liner parsing, no venv activation needed |

**Key insight:** The risk rules are already fully specified in `references/risk-rules.md`. This phase is implementation of a known spec, not design. Every formula, threshold, and boundary condition is pre-decided.

---

## Runtime State Inventory

Not applicable — this is a greenfield infrastructure phase. No rename/refactor/migration operations.

---

## Common Pitfalls

### Pitfall 1: Circuit Breaker In-Memory Only
**What goes wrong:** `circuit_breaker_triggered = True` lives in the `RiskManager` instance. If the script is restarted or if Claude spawns a new agent, the flag is lost and trading resumes.
**Why it happens:** Python objects don't persist across process restarts.
**How to avoid:** Write a flag file to `${CLAUDE_PLUGIN_DATA}/circuit_breaker.flag` when the circuit breaker fires. On `initialize_session()`, check for this file and refuse to start if found (and not manually cleared).
**Warning signs:** Circuit breaker fires, bot restarts (or agent re-instantiates), trading resumes immediately.

### Pitfall 2: PDT In-Memory List Lost Between Sessions
**What goes wrong:** Phase 2 uses an in-memory list for PDT tracking. If the process restarts mid-day, the PDT count resets to zero and the bot can exceed 3 day trades.
**Why it happens:** No SQLite yet (Phase 3 deliverable).
**How to avoid:** In Phase 2, append to a simple JSON file in `${CLAUDE_PLUGIN_DATA}/pdt_trades.json` as a lightweight interim store. Phase 3 migrates to SQLite. Document this as a known Phase 2 limitation.
**Warning signs:** 4+ day trades in a session after process restart.

### Pitfall 3: Ghost Position on First Retry
**What goes wrong:** Order submission times out, retry logic runs, second order is submitted — but the first order was actually filled. Result: double position.
**Why it happens:** Network timeout does not mean the order failed; it means we didn't hear the response.
**How to avoid:** Call `client.get_open_position(symbol)` before EVERY retry attempt (not just after all retries fail). If a position exists, treat it as filled and skip retry.
**Warning signs:** Position size twice the calculated amount in Alpaca dashboard.

### Pitfall 4: PreToolUse Hook JSON Contamination
**What goes wrong:** Hook script emits non-JSON to stdout (debug prints, `echo` statements), Claude Code fails to parse the hook output, hook is silently ignored or errors.
**Why it happens:** Shell scripts default all output to stdout.
**How to avoid:** Every `echo` in the hook script must use `>&2`. Only the final `jq -n '...'` output goes to stdout.
**Warning signs:** Hook doesn't block orders it should block; Claude Code shows hook parse warnings.

### Pitfall 5: config["max_positions"] KeyError
**What goes wrong:** `max_positions` is not in REQUIRED_FIELDS in `tests/test_config.py` and not in the `conftest.py` sample fixture. Code that does `config["max_positions"]` raises `KeyError`.
**Why it happens:** Phase 1 defined the config schema without `max_positions`.
**How to avoid:** Use `config.get("max_positions", 10)` in risk manager. Either update the config schema (and tests/conftest) in Phase 2, or document the default fallback clearly.
**Warning signs:** `KeyError: 'max_positions'` in risk manager unit tests.

### Pitfall 6: size_override_pct Bounds Not Enforced
**What goes wrong:** In `claude_decides` mode, Claude can send any `size_override_pct`. If the risk manager doesn't clamp it, Claude can exceed configured limits.
**Why it happens:** Trust boundary between Claude's JSON output and Python execution.
**How to avoid:** Always clamp: `pct = min(max(size_override_pct, config["max_position_pct"] * 0.5), config["max_position_pct"] * 1.5)`. The risk manager enforces bounds regardless of what Claude recommends.
**Warning signs:** Positions larger than `max_position_pct * 1.5` in paper account.

---

## Code Examples

### Check Circuit Breaker Before Any Action
```python
# Source: references/risk-rules.md, references/alpaca-api-patterns.md
def pre_trade_check(risk_manager: RiskManager, symbol: str, price: float) -> dict:
    """Returns {'allowed': bool, 'reason': str, 'shares': int}"""
    if risk_manager.check_circuit_breaker():
        return {"allowed": False, "reason": "circuit_breaker_active", "shares": 0}
    if not risk_manager.check_position_count():
        return {"allowed": False, "reason": "max_positions_reached", "shares": 0}
    pdt_result = risk_manager.check_pdt_limit(symbol, date_today_str())
    if pdt_result == "block":
        return {"allowed": False, "reason": "pdt_limit_reached", "shares": 0}
    shares = risk_manager.calculate_position_size(symbol, price)
    if shares == 0:
        return {"allowed": False, "reason": "position_too_small", "shares": 0}
    return {"allowed": True, "reason": "ok", "shares": shares}
```

### Persist Circuit Breaker State
```python
# Source: architecture decision — Phase 2 pattern
import os
from pathlib import Path

def _persist_circuit_breaker(self) -> None:
    flag_path = Path(os.environ["CLAUDE_PLUGIN_DATA"]) / "circuit_breaker.flag"
    flag_path.write_text("triggered")
    logger.critical(f"Circuit breaker flag written to {flag_path}")

def initialize_session(self) -> None:
    flag_path = Path(os.environ["CLAUDE_PLUGIN_DATA"]) / "circuit_breaker.flag"
    if flag_path.exists():
        raise RuntimeError(
            "Circuit breaker flag found. Manual intervention required: "
            f"delete {flag_path} to resume trading."
        )
    account = self.client.get_account()
    self.start_equity = float(account.equity)
```

### Interim PDT File Persistence (Phase 2 stopgap)
```python
# Source: architecture decision — replaces SQLite until Phase 3
import json
from pathlib import Path

def _load_pdt_trades(self) -> list[dict]:
    pdt_file = Path(os.environ["CLAUDE_PLUGIN_DATA"]) / "pdt_trades.json"
    if pdt_file.exists():
        return json.loads(pdt_file.read_text())
    return []

def record_day_trade(self, symbol: str, date: str) -> None:
    self._pdt_trades.append({"symbol": symbol, "date": date})
    pdt_file = Path(os.environ["CLAUDE_PLUGIN_DATA"]) / "pdt_trades.json"
    pdt_file.write_text(json.dumps(self._pdt_trades))
```

### Test Without Alpaca Credentials (Mock Pattern)
```python
# Source: pattern for unit testing RiskManager in isolation
from unittest.mock import MagicMock

def make_mock_client(equity=10000.0, position_count=0):
    client = MagicMock()
    account = MagicMock()
    account.equity = str(equity)
    client.get_account.return_value = account
    client.get_all_positions.return_value = [MagicMock()] * position_count
    client.get_open_position.side_effect = Exception("No position")
    return client

def test_circuit_breaker_triggers_at_threshold():
    client = make_mock_client(equity=9700.0)  # 3% loss from 10000 start
    config = {"max_daily_loss_pct": 3.0, "max_position_pct": 10.0,
               "budget_usd": 10000, "max_positions": 10}
    rm = RiskManager(config, client)
    rm.start_equity = 10000.0
    assert rm.check_circuit_breaker() is True
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| alpaca-trade-api (deprecated) | alpaca-py 0.43.2 | 2023 (Alpaca decision) | alpaca-trade-api must never be used; all patterns use alpaca-py classes |
| Fixed dollar position sizes | Percentage of equity | Best practice | Config uses `max_position_pct`, not fixed dollar amounts; `POS-01` enforces this |
| Simple `time.sleep()` retry loop | Exponential backoff with ghost position check | Standard practice | Prevents double positions and respects API rate limits |

**Deprecated/outdated:**
- `alpaca-trade-api` WebSocket streaming: replaced by `alpaca-py` `StockDataStream`. Do not import.
- APScheduler 4.x: API rewrite still in alpha. Stick to 3.x.

---

## Open Questions

1. **`max_positions` config field — add to schema or use default?**
   - What we know: `references/risk-rules.md` and `skills/trading-rules/SKILL.md` both reference `max_positions` as a configurable field, but `tests/test_config.py` REQUIRED_FIELDS does not include it, and `conftest.py` `sample_config` fixture lacks it.
   - What's unclear: Should Phase 2 extend the config schema to include `max_positions`, or should risk manager silently default to 10?
   - Recommendation: Add `max_positions` to REQUIRED_FIELDS in `test_config.py` and add it to the `sample_config` fixture with value `10`. Update the test as part of Plan 02-01. This closes a gap from Phase 1 and makes the schema complete before Phase 3 needs it.

2. **PDT tracking — rolling window precision**
   - What we know: PDT is "5 business days", which the risk-rules.md spec implements as a 7-calendar-day lookback.
   - What's unclear: Edge case at week boundaries (Friday to Monday spans 3 calendar days but 1 business day gap). The 7-calendar-day approximation is acceptable for v1 but may overcounting or undercounting in rare edge cases.
   - Recommendation: Implement 7-calendar-day window for Phase 2 as documented. Note in code comments that Phase 3 can refine to exact business day calculation when SQLite tracking is in place.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `uv run --with pytest`) |
| Config file | none — pytest auto-discovers `tests/` directory |
| Quick run command | `uv run --with pytest pytest tests/test_risk_manager.py -q` |
| Full suite command | `uv run --with pytest pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RISK-01 | Circuit breaker triggers at threshold, blocks subsequent calls | unit | `uv run --with pytest pytest tests/test_risk_manager.py::TestCircuitBreaker -x -q` | Wave 0 |
| RISK-02 | PDT warn at 2, block at 3, rolling window tracked | unit | `uv run --with pytest pytest tests/test_risk_manager.py::TestPDTTracking -x -q` | Wave 0 |
| RISK-03 | Retry 5 times with 1/2/4/8s backoff, skips on 422/403 | unit | `uv run --with pytest pytest tests/test_risk_manager.py::TestRetryLogic -x -q` | Wave 0 |
| RISK-04 | Ghost position detected before retry, no double submission | unit | `uv run --with pytest pytest tests/test_risk_manager.py::TestGhostPosition -x -q` | Wave 0 |
| RISK-05 | claude_decides mode clamps override_pct to 50%–150% of configured value | unit | `uv run --with pytest pytest tests/test_risk_manager.py::TestClaudeDecides -x -q` | Wave 0 |
| POS-01 | Position size = equity * (pct/100), floor division, rejects < 1 share | unit | `uv run --with pytest pytest tests/test_risk_manager.py::TestPositionSizing -x -q` | Wave 0 |
| POS-02 | New entry blocked when positions >= max_positions | unit | `uv run --with pytest pytest tests/test_risk_manager.py::TestPositionCount -x -q` | Wave 0 |
| PLUG-03 | risk-manager.md agent exists with correct YAML frontmatter | structural | `uv run --with pytest pytest tests/test_risk_manager.py::TestAgentDefinition -x -q` | Wave 0 |
| PLUG-07 | validate-order.sh exists, is executable, reads stdin JSON, writes deny JSON | structural | `uv run --with pytest pytest tests/test_risk_manager.py::TestPreToolUseHook -x -q` | Wave 0 |
| PLUG-07 | hooks.json PreToolUse entry references validate-order.sh | structural | `uv run --with pytest pytest tests/test_risk_manager.py::TestHooksJson -x -q` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --with pytest pytest tests/test_risk_manager.py -q`
- **Per wave merge:** `uv run --with pytest pytest tests/ -q`
- **Phase gate:** Full suite green (all 45 existing + all new Phase 2 tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_risk_manager.py` — covers all RISK-01 through RISK-05, POS-01, POS-02, PLUG-03, PLUG-07
- [ ] Additional fixtures in `tests/conftest.py` — `mock_trading_client`, `sample_risk_config` (with `max_positions` field)

---

## Sources

### Primary (HIGH confidence)
- `references/risk-rules.md` — complete risk specification: circuit breaker formula, position sizing formula, PDT rules, retry logic, ghost position prevention
- `references/alpaca-api-patterns.md` — alpaca-py SDK patterns: `get_account()`, `get_all_positions()`, `get_open_position()`, `APIError.status_code`, `submit_order()` with `client_order_id`
- `tests/test_config.py` + `tests/conftest.py` — config schema contract, established test patterns
- `hooks/hooks.json` — existing SessionStart hook structure; PreToolUse follows same schema
- Claude Code Hooks reference (https://code.claude.com/docs/en/hooks) — PreToolUse stdin schema, exit codes, `permissionDecision` JSON structure

### Secondary (MEDIUM confidence)
- `skills/trading-rules/SKILL.md` — confirms max_positions default=10, PDT rolling 5-day, position sizing formula
- WebFetch of https://code.claude.com/docs/en/hooks — `hookSpecificOutput.permissionDecision: "deny"` is the correct block mechanism (not exit code 2)

### Tertiary (LOW confidence)
- None. All critical claims verified via project reference files and official docs.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in requirements.txt; versions pinned from Phase 1
- Architecture (RiskManager class): HIGH — specification is complete in risk-rules.md; patterns confirmed in alpaca-api-patterns.md
- PreToolUse hook schema: HIGH — verified against official Claude Code hooks docs
- Pitfalls: HIGH — circuit breaker persistence and ghost position are documented explicitly in risk-rules.md; others derived from direct reading of spec and hook docs

**Research date:** 2026-03-21
**Valid until:** 2026-06-21 (stable stack; alpaca-py and Claude Code plugin APIs change slowly)
