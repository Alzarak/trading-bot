# Testing Patterns

**Analysis Date:** 2026-03-22

## Test Framework

**Runner:**
- `pytest` (version not pinned in `requirements.txt` — installed as a dev dependency)
- Config: `pytest.ini` (project root)

**Configuration (`pytest.ini`):**
```ini
[pytest]
pythonpath = .
testpaths = tests
```
`pythonpath = .` allows `from scripts.X import Y` without installing the package.

**Assertion Library:**
- pytest's built-in `assert` statements (no extra assertion library)
- `pytest.raises` for expected exceptions

**Run Commands:**
```bash
pytest                          # Run all tests
pytest tests/test_risk_manager.py  # Run single test file
pytest -k "TestCircuitBreaker"  # Run single test class
pytest -v                       # Verbose output
```
No coverage flags configured in `pytest.ini` — coverage is not enforced.

## Test File Organization

**Location:**
- All tests in `tests/` directory (not co-located with source)
- One test file per source module, named `test_{module}.py`

**Naming:**
- Test files: `test_{module_name}.py` — e.g., `test_risk_manager.py` for `scripts/risk_manager.py`
- Test classes: `Test{Feature}` — e.g., `TestCircuitBreaker`, `TestPositionSizing`, `TestPDTTracking`
- Test methods: `test_{what_it_verifies}` — e.g., `test_triggers_at_threshold`, `test_allows_below_threshold`

**Structure:**
```
tests/
├── conftest.py              # Shared fixtures (6 fixtures used across all tests)
├── test_agents.py           # Agent frontmatter validation
├── test_audit_logger.py     # AuditLogger NDJSON output
├── test_bot.py              # Graceful shutdown and pipeline integration
├── test_build_generator.py  # Build generator output validation
├── test_claude_analyzer.py  # Claude JSON parsing and prompt building
├── test_config.py           # config.json schema validation
├── test_env_template.py     # .env template content checks
├── test_eod_report.py       # End-of-day report generation
├── test_hook.py             # Bash hook script content validation
├── test_market_scanner.py   # MarketScanner and indicator computation
├── test_notifier.py         # Notification dispatch
├── test_order_executor.py   # OrderExecutor all 4 order types
├── test_plugin_manifest.py  # Plugin manifest structure
├── test_portfolio_tracker.py# P&L tracking
├── test_risk_manager.py     # All risk rules (most comprehensive)
├── test_state_store.py      # SQLite persistence
└── test_strategies.py       # All 4 trading strategies
```

## Test Structure

**Suite Organization:**
```python
"""Module-level docstring: what the test file covers and which spec IDs.

Covers: RISK-01 (circuit breaker), RISK-02 (position sizing), RISK-03 (PDT tracking)
"""
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
        mock_trading_client.get_account.return_value.equity = "9800.00"
        assert rm.check_circuit_breaker() is True
```

**Patterns:**
- Each test class maps to one feature area with a spec ID comment in the docstring
- Each test method has a one-line docstring describing the scenario using `->` for the expected outcome
- Helper constructors (e.g., `make_rm()`) reduce boilerplate in test methods
- Tests use `is True` / `is False` (not `== True`) for boolean assertions

## Mocking

**Framework:** `unittest.mock` — `MagicMock` and `patch`

**Alpaca Client Mock (from `conftest.py`):**
```python
@pytest.fixture
def mock_trading_client():
    """Return a MagicMock trading client with sensible defaults."""
    from unittest.mock import MagicMock

    client = MagicMock()
    account = MagicMock()
    account.equity = "10000.00"
    client.get_account.return_value = account
    client.get_all_positions.return_value = []
    client.get_open_position.side_effect = Exception("No position")
    return client
```
Note: Alpaca returns equity as a string (`"10000.00"`), which the production code casts with `float()`. Mocks replicate this.

**Patching `time.sleep` (retry tests):**
```python
with patch("scripts.risk_manager.time.sleep"):
    result = rm.submit_with_retry(request, symbol="AAPL")
```
Always patch at the import location (`scripts.risk_manager.time.sleep`), not `time.sleep`.

**Patching Alpaca Request Classes:**
```python
with patch("scripts.order_executor.MarketOrderRequest") as MockRequest:
    mock_request_instance = MagicMock()
    MockRequest.return_value = mock_request_instance
    result = order_executor.submit_market_order("AAPL", 10, OrderSide.BUY)
    MockRequest.assert_called_once()
    kwargs = MockRequest.call_args.kwargs
    assert kwargs["symbol"] == "AAPL"
```

**Multiple Patches (context manager stacking):**
```python
with (
    patch("scripts.order_executor.LimitOrderRequest") as MockLimit,
    patch("scripts.order_executor.TakeProfitRequest") as MockTP,
    patch("scripts.order_executor.StopLossRequest") as MockSL,
):
```

**What to Mock:**
- All Alpaca API clients (`TradingClient`, `StockHistoricalDataClient`)
- External I/O that writes files when `tmp_path` / `plugin_data_dir` fixture is not suitable
- `time.sleep` in retry logic tests
- Alpaca request/order classes when testing routing logic (not the objects themselves)

**What NOT to Mock:**
- `scripts.types` dataclasses — always use real `Signal` and `ClaudeRecommendation` instances
- SQLite `StateStore` — tests use real SQLite with `tmp_path`
- Python stdlib (`json`, `pathlib`, `datetime`)

## Fixtures and Factories

**Shared Fixtures (`tests/conftest.py`):**

```python
@pytest.fixture
def plugin_root(tmp_path):
    """Create a mock CLAUDE_PLUGIN_ROOT with requirements.txt."""

@pytest.fixture
def plugin_data(tmp_path):
    """Create a mock CLAUDE_PLUGIN_DATA directory."""

@pytest.fixture
def sample_config():
    """Return a valid config.json dict with all required fields."""
    return {
        "experience_level": "beginner",
        "paper_trading": True,
        "risk_tolerance": "conservative",
        "max_position_pct": 5.0,
        "max_daily_loss_pct": 2.0,
        "budget_usd": 10000,
        "max_positions": 10,
        "strategies": [{"name": "momentum", "weight": 1.0, "params": {...}}],
        "watchlist": ["AAPL", "MSFT", "SPY"],
        ...
    }

@pytest.fixture
def mock_trading_client():
    """Return a MagicMock trading client with sensible defaults."""

@pytest.fixture
def plugin_data_dir(tmp_path, monkeypatch):
    """Create a temp dir and set CLAUDE_PLUGIN_DATA env var."""
    data_dir = tmp_path / "plugin_data"
    data_dir.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data_dir))
    return data_dir

@pytest.fixture
def env_template():
    """Return expected .env template content."""
```

**Local Fixtures (defined in test files):**
Test files define their own fixtures when shared fixtures don't apply:
```python
# test_order_executor.py
@pytest.fixture
def buy_signal():
    """BUY signal fixture for AAPL."""
    return Signal(action="BUY", atr=2.5, symbol="AAPL", ...)

@pytest.fixture
def sell_signal():
    """SELL signal fixture for AAPL."""
    return Signal(action="SELL", atr=2.5, symbol="AAPL", ...)
```

**Synthetic DataFrames (strategy tests):**
Strategy tests use hand-crafted DataFrames with precise indicator values to force specific signals:
```python
def make_base_df(n: int = 50, base_price: float = 100.0, hour: int = 11) -> pd.DataFrame:
    """Helper function — not a fixture."""

def add_momentum_indicators(df, rsi=35.0, macd_hist=0.5, ...):
    """Add indicator columns to trigger specific signals."""

@pytest.fixture
def buy_momentum_df():
    """DataFrame with indicators configured to produce a BUY signal."""
    df = make_base_df()
    return add_momentum_indicators(df, rsi=35.0, macd_hist=0.5)
```

**Location:**
- Shared fixtures: `tests/conftest.py`
- Per-test-file fixtures and helpers: inline at top of each test file, before test classes

## Coverage

**Requirements:** None enforced. No `--cov` in `pytest.ini`, no minimum threshold set.

**Exclusions:**
- `# pragma: no cover` used on conditional import fallbacks: `except ImportError:  # pragma: no cover`

**View Coverage (manual run):**
```bash
pytest --cov=scripts --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- The dominant form — each method tested in isolation with mocked dependencies
- Every public method on `RiskManager`, `OrderExecutor`, `MarketScanner`, `StateStore` has unit tests
- Signal outcomes (BUY/SELL/HOLD) for all 4 strategies are unit tested with crafted DataFrames

**Integration Tests:**
- `test_state_store.py` uses real SQLite in `tmp_path` — tests schema creation, CRUD, WAL mode, and crash recovery in sequence
- `test_bot.py:TestScanAndTrade` tests the full `scan_and_trade()` pipeline with mocked but wired-together components

**File/Script Validation Tests:**
A notable pattern unique to this codebase: tests that validate file contents rather than code behavior:
```python
class TestPreToolUseHook:
    def test_hook_uses_json_deny_not_exit_code(self):
        content = hook_path.read_text()
        assert "permissionDecision" in content
        assert 'exit 2' not in content

class TestAgentDefinition:
    def test_agent_has_model_sonnet(self):
        content = agent_path.read_text()
        assert "model: sonnet" in content
```
Used for: hook scripts (`test_risk_manager.py`, `test_hook.py`), agent frontmatter (`test_agents.py`), plugin manifest (`test_plugin_manifest.py`), `.env` template (`test_env_template.py`).

**E2E Tests:** Not used. No subprocess calls to run the actual bot.

## Common Patterns

**Async Testing:**
Not applicable — codebase is synchronous. APScheduler runs background threads but tests call functions directly.

**Error Testing:**
```python
with pytest.raises(RuntimeError, match="circuit"):
    rm.initialize_session()
```
Always include `match=` to assert the exception message, not just the type.

**State Mutation Tests:**
When testing stateful behavior, set instance state directly before calling the method:
```python
rm = make_rm(sample_config, mock_trading_client)
rm.start_equity = 10000.0                          # Set state directly
mock_trading_client.get_account.return_value.equity = "9800.00"
assert rm.check_circuit_breaker() is True
```

**Env Var Isolation (`monkeypatch`):**
`plugin_data_dir` fixture uses `monkeypatch.setenv` — prefer this over `os.environ` direct mutation in test methods. Most risk_manager and state_store tests request `plugin_data_dir` to ensure `CLAUDE_PLUGIN_DATA` points to `tmp_path`.

**Config Mutation:**
When a test needs a different config value, copy `sample_config` first:
```python
config = dict(sample_config)
config["max_position_pct"] = 50.0
rm = RiskManager(config, mock_trading_client)
```

**Autouse Fixtures:**
Used in `test_bot.py` to reset module-level state:
```python
@pytest.fixture(autouse=True)
def reset_shutdown_flag():
    """Reset _shutdown_requested to False before and after each test."""
    import scripts.bot as bot_module
    bot_module._shutdown_requested = False
    yield
    bot_module._shutdown_requested = False
```

---

*Testing analysis: 2026-03-22*
