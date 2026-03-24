# Phase 1: Foundation - Research

**Researched:** 2026-03-23
**Domain:** Python trading pipeline — typed data contracts, FMP API client, macro regime detection, exposure gating
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**FMP Degradation Behavior**
- D-01: Silent degradation with log warning — when FMP API key is missing or rate-limited, log a warning once per cache cycle and continue with neutral defaults (regime=transitional, top_risk=30). Never raise exceptions to callers.
- D-02: FMP client returns `None` for individual endpoints on failure; each consumer applies its own default. This prevents one bad endpoint from disabling all FMP-dependent features.
- D-03: Use `requests-cache` with SQLite backend for persistent caching across bot restarts. Use `tenacity` for exponential backoff with jitter on 429/5xx responses.

**Regime Cache Strategy**
- D-04: Split TTL — hourly (3600s) for macro regime label (uses weekly/monthly data that changes slowly), 15-minute (900s) for top_risk score (uses intraday ratios like RSP/SPY, HYG/LQD that can shift within a session).
- D-05: Cache is stored in-memory with timestamp; on bot restart, cache is cold and regime is re-fetched on first scan cycle. No persistent regime cache across restarts.

**Exposure Gating Thresholds**
- D-06: Use REWRITE-PLAN.md thresholds as defaults: block all BUY signals when top_risk >= 70, halve max_position_pct when regime == contraction, block new entries when exposure_ceiling <= current_exposure.
- D-07: All thresholds are configurable via `pipeline.regime_gating` section in config.json — not hardcoded.
- D-08: When top_risk is 41-69, reduce position sizes proportionally (linear scaling between full size and half size).

**Data Model Placement**
- D-09: Add all four new dataclasses (RegimeState, ExposureDecision, RawSignal, AggregatedSignal) to existing `scripts/models.py`, consistent with the existing Signal and ClaudeRecommendation pattern.
- D-10: Use `@dataclass` with `field(default_factory=dict)` for metadata/components dicts. Use `datetime` for timestamps. Use string literals for enum-like fields (regime types, risk zones, bias) — consistent with existing `Literal["BUY", "SELL", "HOLD"]` pattern.

### Claude's Discretion
- FMP client internal architecture (connection pooling, retry timing, cache eviction)
- Exact regime calculator implementations (adapt from reference skills as needed)
- Error logging format and verbosity levels
- Unit test structure for new modules

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | RegimeState dataclass with regime type, confidence, top_risk_score, risk_zone, cache timestamp, and components dict | REWRITE-PLAN.md exact field spec; models.py @dataclass pattern to follow |
| DATA-02 | ExposureDecision dataclass with max_exposure_pct, bias, position_size_multiplier, and reason | REWRITE-PLAN.md exact field spec; exposure-coach REGIME_SCORES mapping |
| DATA-03 | RawSignal dataclass with symbol, action, source, score, confidence, reasoning, entry/stop/atr prices, asset_type, metadata | REWRITE-PLAN.md exact field spec; uses existing AssetType enum |
| DATA-04 | AggregatedSignal dataclass with symbol, action, conviction, sources, agreement_count, contradictions, top_signal, all_signals | REWRITE-PLAN.md exact field spec; top_signal/all_signals reference RawSignal |
| FMP-01 | Shared FMP API client with per-endpoint caching (5-min TTL) and 250/day call counter | Reference fmp_client.py in macro-regime-detector; adapt with requests-cache + tenacity |
| FMP-02 | Graceful degradation — returns None/defaults when no API key present, never raises exceptions | D-01/D-02 locked; try/except ImportError pattern from existing codebase |
| FMP-03 | Rate limit handling with exponential backoff via tenacity | STACK.md: tenacity>=9.1.4 with wait_exponential + retry_if_exception_type |
| REG-01 | Macro regime classification into 5 types using 6 cross-asset ratios | macro-regime-detector scorer.py: classify_regime(), COMPONENT_WEIGHTS, REGIME_DESCRIPTIONS |
| REG-02 | Market top risk scoring (0-100) with 6 sub-components producing risk zones | market-top-detector scorer.py: calculate_composite_score(), _interpret_zone() |
| REG-03 | Regime cache with split TTL — hourly for macro regime label, 15-min for top_risk intraday ratios | D-04 locked; separate _macro_cached_at and _top_risk_cached_at timestamps in RegimeDetector |
| REG-04 | Defaults to transitional regime with top_risk=30 when FMP unavailable | D-01 locked; REGIME_SCORES["transitional"]=50 in reference but D-01 specifies top_risk=30 |
| EXP-01 | ExposureCoach synthesizes RegimeState into ExposureDecision | exposure-coach: determine_exposure_ceiling(), determine_recommendation(), REGIME_SCORES |
| EXP-02 | Block all new BUY signals when top_risk >= 70 (sell-only mode) | D-06 locked; ExposureDecision.bias = "SELL_ONLY" when top_risk >= 70 |
| EXP-03 | Halve max_position_pct when regime == contraction | D-06 locked; position_size_multiplier = 0.5 when regime == "contraction" |
| EXP-04 | Block new entries when exposure_ceiling <= current_exposure | D-06 locked; ExposureCoach.evaluate() compares ceiling against portfolio value |
</phase_requirements>

---

## Summary

Phase 1 establishes the typed data contracts and regime-gated exposure layer that all downstream pipeline phases depend on. It creates four dataclasses in `scripts/models.py`, builds a shared FMP API client in `scripts/pipeline/fmp_client.py`, implements regime detection in `scripts/pipeline/regime.py` adapted from two reference skills (macro-regime-detector and market-top-detector), and implements exposure gating in `scripts/pipeline/exposure.py` adapted from the exposure-coach reference skill.

All implementation decisions are locked by the CONTEXT.md discussion. The reference skills in `/tmp/claude-trading-skills/skills/` provide verified, production-quality scoring logic that must be extracted as pure Python functions (no argparse, no file I/O, no sys.path manipulation). The FMP client is a thin wrapper on `requests` + `requests-cache` + `tenacity` — not a third-party FMP SDK. The pipeline package structure, dataclass conventions, and logging patterns must match the existing `scripts/` codebase.

**Primary recommendation:** Adapt reference skill scoring functions directly — the arithmetic is correct and battle-tested. The only work is stripping CLI scaffolding, replacing dict inputs with typed dataclasses, and wiring in the FMP client with D-01/D-02 graceful degradation semantics.

---

## Standard Stack

### Core (new additions only — existing stack unchanged)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | >=2.31 | FMP HTTP calls | Used in all reference skill FMP clients; already a transitive dependency |
| `requests-cache` | >=1.3.1 | SQLite-backed HTTP caching for FMP responses | D-03 locked; zero-config SQLite backend consistent with state_store.py; survives restarts |
| `tenacity` | >=9.1.4 | Exponential backoff with jitter on 429/5xx | D-03 locked; replaces reference skill's fragile `time.sleep(60)` manual retry |

### Existing (do not re-install)
| Library | Version | Role |
|---------|---------|------|
| `alpaca-py` | 0.43.2 | Order execution + market data |
| `pandas-ta` | 0.4.71b0 | Technical indicators (Phase 2 use) |
| `APScheduler` | >=3.10,<4.0 | 5-minute loop |
| `pydantic-settings` | >=2.0 | Config + .env |
| `loguru` | >=0.7 | Logging — all new modules must use `loguru.logger` |
| `pandas` | >=2.0 | DataFrames for regime ratio calculations |
| `numpy` | >=1.26 | Percentile ranking, normalization |
| Python stdlib | 3.12 | `dataclasses`, `sqlite3`, `datetime`, `json`, `math`, `contextlib` |

### Alternatives Rejected (do not introduce)
| Avoid | Reason |
|-------|--------|
| `fmp-data` (PyPI v2.2.1) | Over-engineered — LangChain integration, async, Redis caching — for 5-6 endpoints |
| `fmp-python` (PyPI) | Unmaintained since 2021 |
| `hmmlearn` / `pomegranate` | HMM regime detection adds latency, requires training data, non-explainable |
| `PyYAML` | Reference skills use YAML for CLI config; bot uses `config.json` |
| SQLAlchemy | Two tables; raw `sqlite3` is the existing pattern |
| Pydantic models for pipeline | Use `@dataclass` — 6x faster for internal computation; Pydantic belongs at API boundaries |

**Installation (new packages only):**
```bash
pip install requests>=2.31 requests-cache>=1.3.1 tenacity>=9.1.4
```

**Verified versions (PyPI, March 2026):**
- `requests-cache` 1.3.1 — released March 4, 2026 (STACK.md confirmed)
- `tenacity` 9.1.4 — released February 7, 2026 (STACK.md confirmed)

---

## Architecture Patterns

### Recommended Project Structure (Phase 1 creates)
```
scripts/
├── models.py                  # EXTEND: add 4 new dataclasses
├── pipeline/
│   ├── __init__.py            # Package init (empty or version)
│   ├── fmp_client.py          # FMPClient — shared instance, no key = graceful None
│   ├── regime.py              # RegimeDetector — adapt 6+6 calculators + scorers
│   └── exposure.py            # ExposureCoach — synthesizes RegimeState → ExposureDecision
```

### Pattern 1: dataclass Extension in models.py

Follow the exact pattern of existing `Signal` and `ClaudeRecommendation`. Use `@dataclass`, `field()`, `Literal[]`, and `from __future__ import annotations`.

**D-10 locked field types:**
- Enum-like fields (regime, bias, risk_zone): `str` with `Literal[...]` type annotation
- Timestamp: `datetime` (import from `datetime`)
- Dicts: `field(default_factory=dict)`
- Lists: `field(default_factory=list)`

```python
# Source: REWRITE-PLAN.md + models.py existing pattern
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

@dataclass
class RegimeState:
    regime: Literal["broadening", "concentration", "contraction", "inflationary", "transitional"]
    regime_confidence: float          # 0.0-1.0 (maps from "high"/"moderate"/"low"/"very_low")
    top_risk_score: float             # 0-100 from market-top-detector
    risk_zone: Literal["green", "yellow", "orange", "red", "critical"]
    cached_at: datetime
    components: dict = field(default_factory=dict)

@dataclass
class ExposureDecision:
    max_exposure_pct: float           # 0-100
    bias: Literal["risk_on", "neutral", "risk_off", "SELL_ONLY"]
    position_size_multiplier: float   # 0.0-1.0
    reason: str

@dataclass
class RawSignal:
    symbol: str
    action: Literal["BUY", "SELL"]
    source: Literal["technical", "earnings_drift", "vcp"]
    score: float                      # 0-100
    confidence: float                 # 0-1
    reasoning: str
    entry_price: float
    stop_price: float
    atr: float                        # MUST be dollar amount, not ratio
    asset_type: AssetType
    metadata: dict = field(default_factory=dict)

@dataclass
class AggregatedSignal:
    symbol: str
    action: Literal["BUY", "SELL"]
    conviction: float                 # 0-1 weighted
    sources: list[str] = field(default_factory=list)
    agreement_count: int = 0
    contradictions: list[str] = field(default_factory=list)
    top_signal: RawSignal | None = None
    all_signals: list[RawSignal] = field(default_factory=list)
```

### Pattern 2: FMP Client (adapted from reference)

Reference: `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/fmp_client.py`

**Key adaptations over reference:**
1. Replace manual `time.sleep(60)` retry with `tenacity` decorator (D-03)
2. Replace in-memory dict cache with `requests-cache` SQLite session (D-03)
3. Construction succeeds when no API key — return `None` silently instead of raising `ValueError` (D-01/D-02)
4. Add `daily_call_count` counter for the 250/day free tier limit (FMP-01)
5. Use `loguru.logger.warning()` not `print(..., file=sys.stderr)` (existing codebase pattern)

```python
# Source: reference fmp_client.py adapted pattern
import os
from contextlib import suppress
from typing import Optional
import requests_cache
from tenacity import retry, wait_exponential, retry_if_exception_type, stop_after_attempt
from loguru import logger

class FMPClient:
    BASE_URL = "https://financialmodelingprep.com/api/v3"
    STABLE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 300) -> None:
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        self._enabled = bool(self.api_key)
        if not self._enabled:
            logger.warning("FMP_API_KEY not set — FMP features disabled, using neutral defaults")
            return
        # requests-cache session with SQLite backend, per-endpoint TTL
        self.session = requests_cache.CachedSession(
            "fmp_cache", backend="sqlite", expire_after=cache_ttl
        )
        self.session.headers.update({"apikey": self.api_key})
        self._daily_calls = 0

    def get_historical_prices(self, symbol: str, days: int = 600) -> Optional[dict]:
        if not self._enabled:
            return None
        return self._get(f"{self.BASE_URL}/historical-price-full/{symbol}", {"timeseries": days})

    def get_treasury_rates(self, days: int = 600) -> Optional[list]:
        if not self._enabled:
            return None
        return self._get(f"{self.STABLE_URL}/treasury-rates", {"limit": days})

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(requests_cache.requests.exceptions.RequestException),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    def _get(self, url: str, params: dict) -> Optional[dict | list]:
        with suppress(Exception):
            resp = self.session.get(url, params=params, timeout=30)
            self._daily_calls += 1
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning("FMP rate limit (429) — tenacity will retry with backoff")
                raise requests_cache.requests.exceptions.RequestException("429")
            else:
                logger.warning("FMP API error {} for {}", resp.status_code, url)
        return None
```

### Pattern 3: RegimeDetector with Split Cache TTL (D-04)

Reference: `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/scorer.py` + `calculators/`

**Key design:**
- Two separate cache timestamps: `_macro_cached_at` and `_top_risk_cached_at`
- `detect()` method returns `RegimeState`; checks each TTL independently
- When FMP unavailable: returns `RegimeState(regime="transitional", top_risk_score=30, risk_zone="green", ...)`
- Component scores passed as plain `dict[str, float]` to scorer functions (they are pure arithmetic)

```python
# Source: macro-regime-detector scorer.py + market-top-detector scorer.py patterns
from datetime import datetime, timedelta
from scripts.models import RegimeState
from loguru import logger

MACRO_TTL_SECONDS = 3600   # D-04 locked
TOP_RISK_TTL_SECONDS = 900  # D-04 locked

class RegimeDetector:
    def __init__(self, fmp_client) -> None:
        self._fmp = fmp_client
        self._macro_cached_at: datetime | None = None
        self._top_risk_cached_at: datetime | None = None
        self._cached_regime: str = "transitional"
        self._cached_regime_confidence: float = 0.0
        self._cached_top_risk: float = 30.0
        self._cached_risk_zone: str = "green"
        self._cached_components: dict = {}

    def detect(self) -> RegimeState:
        now = datetime.utcnow()
        macro_stale = (
            self._macro_cached_at is None
            or (now - self._macro_cached_at).total_seconds() > MACRO_TTL_SECONDS
        )
        top_risk_stale = (
            self._top_risk_cached_at is None
            or (now - self._top_risk_cached_at).total_seconds() > TOP_RISK_TTL_SECONDS
        )
        if macro_stale:
            self._refresh_macro()
        if top_risk_stale:
            self._refresh_top_risk()
        return RegimeState(
            regime=self._cached_regime,
            regime_confidence=self._cached_regime_confidence,
            top_risk_score=self._cached_top_risk,
            risk_zone=self._cached_risk_zone,
            cached_at=now,
            components=self._cached_components,
        )
```

### Pattern 4: ExposureCoach

Reference: `/tmp/claude-trading-skills/skills/exposure-coach/scripts/calculate_exposure.py`

**Key adaptations:**
- Input is `RegimeState` (typed) not a dict loaded from JSON files
- Output is `ExposureDecision` dataclass, not a dict written to a file
- D-06/D-07/D-08 gating rules replace the reference's `determine_recommendation()` with bot-specific logic
- Thresholds sourced from `config["pipeline"]["regime_gating"]` not hardcoded

```python
# Source: exposure-coach calculate_exposure.py, REGIME_SCORES mapping
REGIME_SCORES = {
    "broadening": 80,
    "concentration": 60,
    "transitional": 50,
    "inflationary": 40,
    "contraction": 20,
}

class ExposureCoach:
    def __init__(self, config: dict) -> None:
        gating = config.get("pipeline", {}).get("regime_gating", {})
        self._block_buys_above = gating.get("block_buys_top_risk_above", 70)  # D-07
        self._contraction_pct = gating.get("reduce_size_contraction_pct", 50)  # D-07

    def evaluate(self, regime: RegimeState, current_exposure_pct: float) -> ExposureDecision:
        # D-02: block BUYs when top_risk >= threshold
        if regime.top_risk_score >= self._block_buys_above:
            return ExposureDecision(
                max_exposure_pct=current_exposure_pct,  # no new entries
                bias="SELL_ONLY",
                position_size_multiplier=0.0,
                reason=f"top_risk={regime.top_risk_score:.0f} >= {self._block_buys_above}",
            )
        # D-03: contraction halves position size
        size_mult = 1.0
        if regime.regime == "contraction":
            size_mult = (100 - self._contraction_pct) / 100.0  # 0.5 default
        # D-08: linear scaling 41-69
        elif 41 <= regime.top_risk_score <= 69:
            ratio = (regime.top_risk_score - 41) / (69 - 41)  # 0→1 as risk rises
            size_mult = 1.0 - (0.5 * ratio)  # 1.0→0.5
        regime_score = REGIME_SCORES.get(regime.regime, 50)
        max_exp = _determine_exposure_ceiling(regime_score)
        bias = "risk_off" if regime_score < 40 else ("risk_on" if regime_score >= 70 else "neutral")
        return ExposureDecision(
            max_exposure_pct=max_exp,
            bias=bias,
            position_size_multiplier=size_mult,
            reason=f"regime={regime.regime} top_risk={regime.top_risk_score:.0f}",
        )
```

### Pattern 5: config.json Pipeline Section

```json
{
  "pipeline": {
    "scan_interval_seconds": 300,
    "regime_cache_ttl_seconds": 3600,
    "screeners": {
      "technical": {"enabled": true, "weight": 0.40},
      "earnings_drift": {"enabled": false, "weight": 0.20},
      "vcp": {"enabled": false, "weight": 0.20}
    },
    "min_conviction": 0.50,
    "regime_gating": {
      "block_buys_top_risk_above": 70,
      "reduce_size_contraction_pct": 50
    },
    "position_sizing_method": "atr",
    "risk_pct_per_trade": 1.0,
    "atr_multiplier": 2.0
  },
  "fmp_api_key_env": "FMP_API_KEY"
}
```

### Anti-Patterns to Avoid
- **Raising exceptions in FMP client:** Callers must never crash due to FMP unavailability. Every public method returns `None` on failure (D-02).
- **Single cache timestamp for both regime label and top_risk:** They have different data freshness rates. Sharing one TTL will either over-fetch macro or under-fetch top_risk (D-04).
- **Hardcoded thresholds (70, 50%):** Always read from `config["pipeline"]["regime_gating"]` with sensible defaults (D-07).
- **Direct import of reference skill scripts:** They use `sys.path.insert()`, `argparse`, file I/O to `reports/`. Extract pure scoring functions only.
- **`print()` or `sys.stderr` in new modules:** Use `loguru.logger` — project-wide convention.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry with backoff | `time.sleep(60)` manual loop | `tenacity` `@retry` with `wait_exponential` | Handles jitter, max retries, exception type filtering — reference skill's manual retry is fragile |
| HTTP caching | In-memory dict keyed by URL | `requests-cache` SQLite backend | Survives bot restarts; TTL expiry built-in; wraps `requests.Session` transparently |
| Regime composite scoring | Custom weighted average | Adapt `calculate_composite_score()` from reference scorers | Reference has data quality weighting, correlation adjustment (market-top), partial data handling |
| Regime classification | Custom if/else tree | Adapt `classify_regime()` from macro-regime-detector scorer.py | Reference has tiebreak logic, transitional fallback, confidence capping by data availability |
| Exposure ceiling math | Custom curve | Adapt `determine_exposure_ceiling()` from exposure-coach | Reference has non-linear mapping tuned to regime score ranges |
| FMP endpoints | Generic REST client | Custom `FMPClient` wrapping `requests-cache` | 5-6 known endpoints, known response shapes — thin purpose-built client is correct |

**Key insight:** The reference skills contain ~800 lines of regime/exposure arithmetic that took iteration to tune. Adapt it directly rather than re-deriving the scoring curves.

---

## Common Pitfalls

### Pitfall 1: top_risk Default — Reference vs. Locked Decision Mismatch
**What goes wrong:** The reference exposure-coach skill uses `REGIME_SCORES["transitional"] = 50` as the default regime score, which maps to a moderate exposure ceiling. But D-01 locks the FMP-absent default to `top_risk=30` (neutral-low risk). If a developer uses the reference defaults unchanged, the no-FMP-key bot will operate at 50% risk instead of 30%.
**How to avoid:** In `RegimeDetector.__init__`, initialize `_cached_top_risk = 30.0` (not 50) per D-01. Log this at DEBUG on every cache hit when FMP is unavailable.
**Warning signs:** Bot logs show `top_risk=50` when FMP key is absent.

### Pitfall 2: Regime Cache Stale on top_risk During Intraday Regime Flips
**What goes wrong:** If `top_risk` and macro regime share a single 60-minute TTL, a Fed announcement causing `top_risk` to jump from 35 to 80 mid-session won't be detected until the next hourly refresh. BUY orders will be placed in hostile conditions for up to 45 minutes.
**Why it happens:** Single TTL timestamp — D-04 explicitly requires split TTLs.
**How to avoid:** Two separate timestamps `_macro_cached_at` and `_top_risk_cached_at` with `MACRO_TTL = 3600` and `TOP_RISK_TTL = 900` in `RegimeDetector`.
**Warning signs:** `top_risk` value in logs unchanged for 60+ minutes on volatile days.

### Pitfall 3: FMP Client Construction Raises Instead of Degrading
**What goes wrong:** The reference `FMPClient.__init__` raises `ValueError` when `FMP_API_KEY` is absent. If the bot passes `fmp_client = FMPClient()` at startup without a key, it crashes immediately.
**How to avoid:** In the adapted `FMPClient`, set `self._enabled = bool(self.api_key)`. All public methods return `None` immediately when `_enabled` is False (D-02). Log once at `WARNING` level during `__init__`.
**Warning signs:** `ValueError: FMP API key required` in startup logs.

### Pitfall 4: Exposure Bias Field — Reference vs. REWRITE-PLAN Mismatch
**What goes wrong:** The exposure-coach reference uses `bias` values of `"GROWTH"`, `"VALUE"`, `"DEFENSIVE"`, `"NEUTRAL"`. The REWRITE-PLAN.md spec uses `"risk_on"`, `"neutral"`, `"risk_off"`. EXP-02 requires `bias="SELL_ONLY"` when `top_risk >= 70`. Mixing these causes downstream consumers to fail on unexpected literal values.
**How to avoid:** `ExposureDecision.bias` must use the REWRITE-PLAN.md literals exactly: `Literal["risk_on", "neutral", "risk_off", "SELL_ONLY"]`. The reference bias logic (`determine_bias()`) can be adapted as guidance, but output values must be remapped.
**Warning signs:** `bias="GROWTH"` in log output; downstream `if bias == "SELL_ONLY"` check never matches.

### Pitfall 5: risk_zone String — market-top-detector vs. Models Spec
**What goes wrong:** The market-top-detector scorer's `_interpret_zone()` returns `zone_color` values like `"green"`, `"yellow"`, `"orange"`, `"red"`, `"critical"` — and the zone label as `"Green (Normal)"`, `"Yellow (Early Warning)"`, etc. The models spec uses just the color string for `RegimeState.risk_zone`. If the full zone label string is stored, `if risk_zone == "red"` checks will silently fail.
**How to avoid:** In `RegimeDetector._refresh_top_risk()`, store `zone_result["zone_color"]` (the bare color) into `_cached_risk_zone`, not `zone_result["zone"]` (the full label).
**Warning signs:** `risk_zone="Red (High Probability Top)"` instead of `risk_zone="red"` in RegimeState logs.

### Pitfall 6: requests-cache and requests Version Mismatch
**What goes wrong:** `requests-cache` wraps `requests.Session`. If the installed `requests` major version differs from what `requests-cache` expects, cache instrumentation silently fails (returns live requests instead of cached).
**How to avoid:** Pin `requests>=2.31` and `requests-cache>=1.3.1` together. Verify with `pip show requests requests-cache` after install.
**Warning signs:** FMP API call count exceeds expected cache hits; `_daily_calls` counter grows faster than expected.

---

## Code Examples

Verified patterns from reference implementations:

### RegimeDetector neutral defaults (D-01 / REG-04)
```python
# When FMP client is disabled or all FMP calls return None
NEUTRAL_REGIME = RegimeState(
    regime="transitional",
    regime_confidence=0.0,
    top_risk_score=30.0,      # D-01: neutral default
    risk_zone="green",
    cached_at=datetime.utcnow(),
    components={},
)
```

### Macro regime component weights (from scorer.py verified source)
```python
# Source: /tmp/claude-trading-skills/skills/macro-regime-detector/scripts/scorer.py
MACRO_COMPONENT_WEIGHTS = {
    "concentration": 0.25,  # RSP/SPY ratio
    "yield_curve":   0.20,  # 10Y-2Y spread
    "credit_conditions": 0.15,  # HYG/LQD ratio
    "size_factor":   0.15,  # IWM/SPY ratio
    "equity_bond":   0.15,  # SPY/TLT + stock-bond correlation
    "sector_rotation": 0.10,  # XLY/XLP ratio
}
# FMP symbols needed: SPY, RSP, IWM, HYG, LQD, TLT, XLY, XLP
# Treasury endpoint: /stable/treasury-rates (year2, year10 fields)
```

### Market top risk component weights (from market-top-detector scorer.py)
```python
# Source: /tmp/claude-trading-skills/skills/market-top-detector/scripts/scorer.py
TOP_RISK_COMPONENT_WEIGHTS = {
    "distribution_days":  0.25,
    "leading_stocks":     0.20,
    "defensive_rotation": 0.15,
    "breadth_divergence": 0.15,
    "index_technical":    0.15,
    "sentiment":          0.10,
}
# Note: correlation adjustment applies when both distribution_days and
# defensive_rotation are >= 80 (discount lower-weight one by 0.8x)
```

### ExposureCoach gating logic (D-06/D-08)
```python
# Linear scale for top_risk 41-69 (D-08)
# At top_risk=41: multiplier=1.0 (full size)
# At top_risk=69: multiplier=0.5 (half size)
# At top_risk=70+: bias=SELL_ONLY, multiplier=0.0

def _linear_size_multiplier(top_risk: float) -> float:
    ratio = (top_risk - 41) / (69 - 41)  # 0.0 at 41, 1.0 at 69
    return 1.0 - (0.5 * ratio)           # 1.0 at 41, 0.5 at 69
```

### Exposure ceiling mapping (from exposure-coach reference)
```python
# Source: exposure-coach/scripts/calculate_exposure.py determine_exposure_ceiling()
def _determine_exposure_ceiling(regime_score: int) -> float:
    """Non-linear mapping from regime score (0-100) to max exposure %."""
    if regime_score >= 80:
        return min(100, 90 + (regime_score - 80))
    elif regime_score >= 65:
        return 70 + (regime_score - 65) * 1.3
    elif regime_score >= 50:
        return 50 + (regime_score - 50) * 1.3
    elif regime_score >= 35:
        return 30 + (regime_score - 35) * 1.3
    elif regime_score >= 20:
        return 10 + (regime_score - 20) * 1.3
    else:
        return max(0, regime_score / 2)
```

### Confidence string-to-float conversion
```python
# Source: macro-regime-detector scorer.py classify_regime() output
# "high" / "moderate" / "low" / "very_low" → float for RegimeState.regime_confidence
CONFIDENCE_MAP = {
    "high": 0.85,
    "moderate": 0.60,
    "low": 0.35,
    "very_low": 0.10,
}
```

### tenacity retry decorator for FMP calls
```python
# Source: STACK.md recommendation + tenacity 9.x docs
from tenacity import (
    retry,
    wait_exponential,
    retry_if_exception_type,
    stop_after_attempt,
    before_sleep_log,
)
import logging

@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=False,
)
def _get(self, url: str, params: dict) -> Optional[dict | list]:
    ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-TTL regime cache | Split TTL: macro hourly, top_risk 15-min | D-04 decision | Catches intraday risk spikes without over-fetching slow-moving macro data |
| Manual `time.sleep(60)` retry | `tenacity` with exponential backoff + jitter | D-03 decision | Handles burst 429s without blocking the scan loop for 60 full seconds |
| In-memory session cache (lost on restart) | `requests-cache` SQLite (persists across restarts) | D-03 decision | Avoids burning daily FMP quota on first scan after bot restart |
| Raise ValueError on missing FMP key | `_enabled=False`, return None | D-01/D-02 decision | Bot runs fully without FMP key — never crashes callers |
| Reference skill bias literals (GROWTH/VALUE/DEFENSIVE) | REWRITE-PLAN.md literals (risk_on/neutral/risk_off/SELL_ONLY) | D-10 decision | Consistent with pipeline consumer expectations |

**Deprecated/outdated (do not use):**
- `fmp-python` PyPI package: Last release 2021, uses deprecated FMP v3 patterns only
- Reference `FMPClient` as-is: Uses `print(sys.stderr)` and `time.sleep(60)` — replace with loguru + tenacity

---

## Open Questions

1. **FMP 250 calls/day free tier — actual limit unverified**
   - What we know: STACK.md notes "FMP 250 calls/day free tier limit unverified"
   - What's unclear: Whether 250/day is calls or credits; whether historical-price-full counts as 1 call per symbol or N calls
   - Recommendation: Implement the `_daily_calls` counter in FMPClient regardless. Log a warning when it approaches 200. Validate with a live key during Phase 1 verification before finalizing TTL values.

2. **Regime calculator FMP symbol availability on free tier**
   - What we know: macro-regime-detector needs SPY, RSP, IWM, HYG, LQD, TLT, XLY, XLP historical prices + treasury rates
   - What's unclear: Whether all these symbols are available on FMP's free tier, or require paid plan
   - Recommendation: Test each endpoint in isolation during Phase 1 implementation. If any symbol is blocked, add a `data_availability` flag per component so the scorer can operate with partial data (the reference scorers already support this via `data_availability` dict parameter).

3. **`requests-cache` TTL per-endpoint vs. session-level**
   - What we know: `requests-cache` supports per-URL TTL via `urls_expire_after` dict
   - What's unclear: Whether to use a single session TTL (5 min as FMP-01 specifies) or per-endpoint TTL to match the split regime cache
   - Recommendation: Use a single 5-minute session TTL for `requests-cache` (FMP-01 requires 5-min TTL). The split macro/top_risk logic lives at the `RegimeDetector` layer, not the HTTP cache layer. The HTTP cache prevents redundant API calls within a window; the RegimeDetector cache controls when to re-call FMP at all.

---

## Sources

### Primary (HIGH confidence)
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/scorer.py` — verified `classify_regime()`, `calculate_composite_score()`, `COMPONENT_WEIGHTS` (6 components, weights)
- `/tmp/claude-trading-skills/skills/market-top-detector/scripts/scorer.py` — verified `calculate_composite_score()`, `_interpret_zone()`, zone color literals, correlation adjustment
- `/tmp/claude-trading-skills/skills/exposure-coach/scripts/calculate_exposure.py` — verified `REGIME_SCORES`, `determine_exposure_ceiling()`, `determine_recommendation()` logic
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/fmp_client.py` — verified FMPClient pattern, endpoint URLs, rate limit approach
- `/home/parz/projects/trading-bot/scripts/models.py` — verified existing dataclass pattern (`@dataclass`, `field()`, `Literal`, `AssetType` enum)
- `/home/parz/projects/trading-bot/scripts/state_store.py` — verified SQLite pattern (WAL mode, `row_factory`, `_create_tables()`)
- `/home/parz/projects/trading-bot/.planning/phases/01-foundation/01-CONTEXT.md` — locked decisions D-01 through D-10
- `/home/parz/projects/trading-bot/REWRITE-PLAN.md` — canonical data model field specs, config schema, pipeline flow
- `/home/parz/projects/trading-bot/.planning/research/STACK.md` — verified package versions (requests-cache 1.3.1, tenacity 9.1.4)
- `/home/parz/projects/trading-bot/.planning/research/PITFALLS.md` — domain pitfalls (regime cache stale, ATR ratio bug, etc.)

### Secondary (MEDIUM confidence)
- PyPI `requests-cache` 1.3.1 release date March 4, 2026 (STACK.md verified)
- PyPI `tenacity` 9.1.4 release date February 7, 2026 (STACK.md verified)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — packages verified against PyPI; existing stack unchanged; alternatives directly rejected by project research
- Architecture patterns: HIGH — directly adapted from verified reference skill implementations with locked decisions applied
- Pitfalls: HIGH — derived from codebase analysis + reference skill review + locked decision mismatches identified during research

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (stable stack; FMP API tier limits need live-key validation within Phase 1)
