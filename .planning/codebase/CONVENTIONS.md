# Coding Conventions

**Analysis Date:** 2026-03-22

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules: `risk_manager.py`, `order_executor.py`, `state_store.py`
- `kebab-case.sh` for shell scripts: `validate-order.sh`, `check-session.sh`, `install-deps.sh`
- `snake_case` for test files, prefixed with `test_`: `test_risk_manager.py`, `test_order_executor.py`

**Classes:**
- `PascalCase` for all classes: `RiskManager`, `OrderExecutor`, `MarketScanner`, `StateStore`, `AuditLogger`
- Strategy classes follow `{Name}Strategy` pattern: `MomentumStrategy`, `MeanReversionStrategy`, `BreakoutStrategy`, `VWAPStrategy`

**Functions and Methods:**
- `snake_case` for all public methods: `calculate_position_size()`, `check_circuit_breaker()`, `submit_with_retry()`
- `_snake_case` prefix for private helpers: `_persist_circuit_breaker()`, `_load_pdt_trades()`, `_has_open_position()`, `_create_tables()`

**Variables:**
- `snake_case` for all locals and instance vars: `start_equity`, `circuit_breaker_triggered`, `atr_multiplier`
- `UPPER_CASE` for module-level constants and registries: `STRATEGY_REGISTRY`, `_DEFAULTS`, `ET`
- Boolean flags use descriptive past-tense or state names: `circuit_breaker_triggered`, `_shutdown_requested`

**Types:**
- `dataclass` for shared contract types in `scripts/types.py`
- String literals for enum-like values: `Literal["BUY", "SELL", "HOLD"]`
- `str | Path` union syntax (Python 3.10+ style) throughout, not `Union[str, Path]`
- `float | None` preferred over `Optional[float]`

## Code Style

**Formatting:**
- No formatter config detected (no `pyproject.toml`, `ruff.toml`, `.prettierrc`). Style is enforced by convention.
- 4-space indentation throughout
- 88-character line length implied by line wrapping in practice
- Trailing commas in multi-line argument lists (e.g., `Signal(...)` in `types.py`)

**Linting:**
- No ESLint/ruff config detected; `type: ignore[assignment]` comments used pragmatically for conditional imports
- `# pragma: no cover` marks unreachable branches in conditional imports

**Section Delimiters:**
- Long methods are grouped with dashed comment separators:
  ```python
  # ------------------------------------------------------------------
  # Circuit breaker
  # ------------------------------------------------------------------
  ```

## Import Organization

**Order (observed in practice):**
1. Standard library (`json`, `math`, `os`, `time`, `pathlib`, `datetime`)
2. Third-party packages (`loguru`, `pandas`, `numpy`, `apscheduler`)
3. Conditional third-party inside `try/except ImportError` blocks (alpaca-py)
4. Local project imports (`from scripts.types import Signal`)

**Conditional Imports (key pattern):**
Alpaca-py is always imported conditionally to allow tests without the library installed:
```python
try:
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
except ImportError:
    OrderClass = None  # type: ignore[assignment]
    OrderSide = None  # type: ignore[assignment]
```

**Path Aliases:**
- No path aliases; all local imports use full `scripts.` prefix: `from scripts.types import Signal`, `from scripts.risk_manager import RiskManager`
- Test files add project root to `sys.path` explicitly when needed: `sys.path.insert(0, str(PROJECT_ROOT))`

## Error Handling

**Strategy: Catch-and-log at pipeline boundaries, let exceptions propagate internally**

- Inner methods raise `RuntimeError` for unrecoverable states:
  ```python
  raise RuntimeError(
      f"circuit breaker flag present at {flag_file}. "
      "Remove it manually to restart trading."
  )
  ```
- Outer pipeline loops catch `Exception` broadly and continue:
  ```python
  except Exception as exc:
      logger.error("scan_and_trade: error processing {}: {}", symbol, exc)
  ```
- File I/O operations use targeted catches: `except (json.JSONDecodeError, OSError) as exc`
- HTTP status codes checked via `getattr(exc, "status_code", None)` — no custom exception types
- Non-retryable codes (422, 403) return `None` immediately from `submit_with_retry()`
- Return `None` (not raise) to signal blocked/failed operations from public methods

**Exception Pattern for External Calls:**
```python
try:
    self.client.get_open_position(symbol)
    return True
except Exception:
    return False
```

## Logging

**Framework:** `loguru` — imported as `from loguru import logger`

**Log Levels (by severity):**
- `logger.debug(...)` — non-actionable diagnostic detail (HOLD signals, prompt prep)
- `logger.info(...)` — normal operational events (orders submitted, session started, scans)
- `logger.warning(...)` — risk check blocks, parse failures, recoverable issues
- `logger.error(...)` — failed operations that skip a trade but continue the bot
- `logger.critical(...)` — circuit breaker triggers, flag file found on startup

**Message Format:**
- Always use loguru's `{}` placeholder style, never f-strings in logger calls:
  ```python
  logger.info("Position size for {}: {} shares @ ${:.2f}", symbol, shares, current_price)
  ```
- Messages are prefixed with the function name when context is ambiguous: `"scan_and_trade: error processing {}: {}"`
- Financial values formatted with `${:.2f}` or `{:.2f}%`

## Comments

**Module Docstrings:**
Every module has a top-level docstring explaining:
1. What the module does (1 sentence)
2. What it wraps or depends on
3. One key invariant or safety rule
Example: `scripts/order_executor.py` docstring establishes the "every order routes through RiskManager" invariant.

**Class Docstrings:**
```python
class RiskManager:
    """Enforces all risk rules for the trading bot.

    Args:
        config: Trading configuration dict (from config.json).
        trading_client: Alpaca TradingClient instance (or mock).
    """
```

**Method Docstrings:**
Full Google-style docstrings with Args, Returns, and Raises sections on all public methods.
Private helpers (`_*`) have single-line docstrings only.

**Inline Comments:**
Used to explain non-obvious math or safety decisions:
```python
# Clamp to [50%, 150%] of configured max_position_pct
lower_bound = max_pct * 0.5
```

## Function Design

**Size:** Functions stay focused — no method in any script exceeds ~60 lines. `bot.py:main()` is the largest at ~100 lines but is organized with numbered steps matching the docstring.

**Parameters:**
- `config: dict` passed through the pipeline (not a global)
- Optional parameters default to `None`, not mutable defaults
- `side: "OrderSide | None" = None` with explicit `if side is None: side = OrderSide.BUY` inside body

**Return Values:**
- Public methods return `None` on failure, never raise for expected failures
- Boolean return for guard checks: `check_circuit_breaker() -> bool`, `check_position_count() -> bool`
- String return for multi-outcome checks: `check_pdt_limit() -> str` returning `"allow"`, `"warn"`, or `"block"`
- `-> object | None` for Alpaca order types (avoids importing at module level)

## Module Design

**Exports:**
- No `__all__` used; all public names are simply not prefixed with `_`
- Strategy modules export a `STRATEGY_REGISTRY` dict at `scripts/strategies/__init__.py`

**Class Construction:**
All classes accept clients/dependencies as constructor arguments — never import global singletons. This enables clean test mocking:
```python
def __init__(self, risk_manager, config: dict) -> None:
    self.risk_manager = risk_manager
    self.config = config
```

**Env Vars:**
All environment variables accessed via `os.environ.get("VAR_NAME", "fallback")` — never `os.environ["VAR_NAME"]`. Key vars: `CLAUDE_PLUGIN_DATA`, `CLAUDE_PLUGIN_ROOT`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`.

## Bash Script Conventions

**Header:**
```bash
#!/bin/bash          # or #!/usr/bin/env bash
# Description comment
set -euo pipefail    # validate-order.sh
set -e               # install-deps.sh (less strict)
```

**Env Var Resolution (dual-mode pattern):**
Both hooks use the same fallback pattern for plugin vs dev mode:
```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-${PLUGIN_ROOT}/.plugin-data}"
```

**Debug Output:**
All diagnostic output goes to stderr: `echo "Intercepted order command: $COMMAND" >&2`
Only JSON decisions go to stdout (Claude Code hook protocol).

**Hook Deny Pattern:**
Hooks output JSON `permissionDecision` and `exit 0` (never `exit 2`):
```bash
jq -n '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "..."
  }
}'
exit 0
```

---

*Convention analysis: 2026-03-22*
