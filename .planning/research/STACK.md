# Stack Research

**Domain:** Regime-aware trading signal pipeline (Python, autonomous bot)
**Researched:** 2026-03-23
**Confidence:** HIGH — core choices derived from reference skill implementations + verified PyPI versions

---

## Context: What Is Already Settled

Do not re-evaluate these — they are validated and in production:

| Technology | Version | Role |
|------------|---------|------|
| alpaca-py | 0.43.2 | Order execution + market data |
| pandas-ta | 0.4.71b0 | Technical indicators |
| APScheduler | >=3.10,<4.0 | 5-minute loop scheduler |
| pydantic-settings | >=2.0 | Config + .env loading |
| loguru | >=0.7 | Structured logging |
| SQLite (stdlib) | built-in | State persistence |
| Python | 3.12+ | Runtime |

Everything below is **new** — additions needed for the pipeline rewrite.

---

## Recommended Stack

### FMP API Client

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `requests` | >=2.31 | FMP HTTP calls | Already used in all reference skill FMP clients (macro-regime-detector, vcp-screener, market-top-detector). The tradermonty skills ship their own `FMPClient` class built on requests; we adapt that pattern directly rather than adding an opinionated third-party FMP wrapper. |
| `requests-cache` | >=1.3.1 | SQLite-backed HTTP caching for FMP responses | FMP's free tier hits daily call limits fast. Caching treasury rates, S&P 500 constituents, and earnings calendars at the response level avoids redundant calls. SQLite backend is zero-config and consistent with existing state_store.py. |
| `tenacity` | >=9.1.4 | Retry with exponential backoff on 429/5xx | The reference skill FMP clients implement manual retry with `time.sleep(60)` — fragile. Tenacity's `@retry(wait=wait_exponential(...), retry=retry_if_exception_type(RequestException))` is cleaner and handles jitter. |

**Do NOT use `fmp-data` (PyPI).** It is a fully-featured third-party SDK (v2.2.1 as of March 2026) with LangChain integration, Redis caching, and async clients — all unnecessary weight for a bot that only needs 5-6 FMP endpoints. The reference skills deliberately use a thin custom `FMPClient`; adapt that pattern.

**FMP endpoints needed:**
- `/api/v3/historical-price-full/{symbol}` — regime component price history (SPY, IWM, RSP, HYG, LQD, TLT, XLY, XLP)
- `/stable/treasury-rates` — yield curve (10Y-2Y spread)
- `/api/v3/sp500_constituent` — VCP screener universe
- `/api/v3/earning_calendar` — earnings drift screener
- `/api/v3/historical-price-full/{symbol}?timeseries=N` — VCP pattern history

### Macro Regime Detection

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `pandas` | >=2.0 | Ratio calculations, rolling windows, regime component scoring | Already in requirements. All 6 regime calculators (concentration, yield curve, credit, size factor, equity-bond, sector rotation) operate on DataFrames of ratio histories. |
| `numpy` | >=1.26 | Percentile ranking, normalization | Already in requirements. Used for cross-sectional percentile scoring of component signals (0-100 scale). |

**No external regime detection library needed.** The reference `macro-regime-detector` skill contains complete scoring logic across 6 calculators + composite scorer with `classify_regime()`. Extract these pure functions (no argparse, no file I/O, no sys.path hacks) into `pipeline/regime/` modules. This is arithmetic on pandas DataFrames — no ML library is warranted.

**Do NOT use Hidden Markov Model libraries (hmmlearn, pomegranate).** HMM-based regime detection adds 200ms+ latency, requires training data, and produces probabilistic output that is harder to gate on than the deterministic 0-100 score from the reference implementation. The reference skill's rule-based approach (RSP/SPY ratio, yield curve inversion, credit spread, etc.) is explainable and directly actionable.

### Signal Aggregation and Conviction Scoring

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Standard library `dataclasses` | Python 3.12 stdlib | `RawSignal`, `AggregatedSignal`, `RegimeState`, `ExposureDecision` data contracts | The existing `models.py` uses `@dataclass` — be consistent. Dataclasses are 6x faster than Pydantic for internal pipeline computation; Pydantic belongs at API/config boundaries only. |
| Standard library `enum` | Python 3.12 stdlib | `ThesisState` (IDEA/ENTRY_READY/ACTIVE/CLOSED), `RegimeLabel`, `SignalDirection` | Already used for `AssetType` in `models.py`. Enums stored as `.value` strings in SQLite columns — straightforward and crash-recoverable. |

The `edge-signal-aggregator` skill's `aggregate_signals.py` implements weighted conviction scoring, deduplication, contradiction detection, and recency decay as pure functions operating on dicts. Extract these into `pipeline/aggregator.py` with typed dataclass inputs instead of raw dicts. The aggregation logic itself (~300 lines of arithmetic) needs no library beyond stdlib.

**Do NOT introduce `PyYAML`.** The reference aggregator uses YAML for config as a CLI tool. In the bot, aggregation weights live in `config.json` under a `pipeline.weights` key — already handled by pydantic-settings. YAML adds a dependency with no benefit.

### Position Sizing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Standard library `math` | Python 3.12 stdlib | Kelly criterion formula | `kelly_pct = win_rate - (1 - win_rate) / (avg_win / avg_loss)` is 3 lines of arithmetic. No library needed. |

The reference `position-sizer` skill implements three sizing methods (fixed fractional, ATR-based, Kelly) as pure functions with no external dependencies. Copy these functions directly into `pipeline/sizer.py`. The reference implementation already handles Half-Kelly clamping, negative expectancy floor, and portfolio constraint caps (max position %, max sector %).

**ATR is the default.** Kelly requires historical win rate and avg win/loss from completed trades; at bot startup there is no history, so ATR-based sizing is the required default. Add Kelly as an upgrade path once `signal_postmortem` has populated enough closed-thesis records.

**Do NOT use `PyPortfolioOpt` or similar portfolio optimization libraries.** The sizing problem here is single-trade risk sizing under a budget cap, not mean-variance portfolio construction.

### Thesis Lifecycle Tracking

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Standard library `sqlite3` | Python 3.12 stdlib | Thesis table, postmortem table | Consistent with existing `state_store.py`. SQLite supports atomic writes via transactions — crash recovery is the primary requirement. No ORM needed for a 2-table schema. |

Schema pattern (adapts `trader-memory-core` + `signal-postmortem` skill patterns):

```sql
CREATE TABLE IF NOT EXISTS theses (
    id TEXT PRIMARY KEY,           -- uuid4
    symbol TEXT NOT NULL,
    state TEXT NOT NULL,           -- IDEA | ENTRY_READY | ACTIVE | CLOSED
    regime_at_entry TEXT,          -- RegimeLabel.value
    conviction_score REAL,         -- 0.0-1.0 from aggregator
    source_signals TEXT,           -- JSON array of RawSignal dicts
    entry_price REAL,
    stop_price REAL,
    target_price REAL,
    created_at TEXT NOT NULL,      -- ISO 8601
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_postmortems (
    id TEXT PRIMARY KEY,
    thesis_id TEXT REFERENCES theses(id),
    source_skill TEXT,             -- which screener fired
    outcome_category TEXT,         -- TRUE_POSITIVE | FALSE_POSITIVE | REGIME_MISMATCH
    realized_return_5d REAL,
    recorded_at TEXT NOT NULL
);
```

State transitions are guarded by Python before the SQLite write — no SQLite trigger magic needed.

**Do NOT use SQLAlchemy or any ORM.** Two tables with a handful of columns do not justify ORM overhead. Raw `sqlite3` with parameterized queries is sufficient and already the pattern in `state_store.py`.

### Graceful Degradation (FMP Optional)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Standard library `contextlib` | Python 3.12 stdlib | `suppress(Exception)` guard around FMP calls | When `FMP_API_KEY` is absent or rate limit is reached, each FMP-dependent screener returns `None`. The aggregator treats `None` inputs as absent signals, not errors. No external circuit-breaker library needed. |

---

## Installation

```bash
# Add to requirements.txt
pip install requests>=2.31 requests-cache>=1.3.1 tenacity>=9.1.4
```

All other new code (`pipeline/` modules) uses Python stdlib only.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Custom `FMPClient` (requests + tenacity) | `fmp-data` PyPI (v2.2.1) | Only if you need async WebSocket streaming, LangChain integration, or access to 40+ endpoint categories. Overkill for 5-6 endpoints. |
| `requests-cache` (SQLite backend) | In-memory dict cache | Use in-memory if deployment environment is ephemeral (Docker) and you don't want a cache file on disk. SQLite survives restarts, which is better for a 5-min polling bot. |
| Deterministic rule-based regime scoring | `hmmlearn` HMM | Use HMM if you have years of labeled regime data and need probabilistic forward-looking regime probabilities. Rule-based is better for explainability and real-time gating. |
| Stdlib `sqlite3` + raw SQL | SQLAlchemy | Use SQLAlchemy if the schema grows beyond ~5 tables and joins become complex, or if you add async DB access later. |
| `@dataclass` for pipeline models | Pydantic `BaseModel` | Use Pydantic for models that cross HTTP boundaries (API request/response) or need JSON schema generation. Internal pipeline models don't need validation overhead. |
| `tenacity` retry decorator | Manual `time.sleep()` retry | Use manual retry only for scripts that can't take dependencies. In a long-running bot process, tenacity is cleaner and supports jitter. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `fmp-python` (PyPI) | Last release 2021, unmaintained, uses deprecated FMP v3 patterns only | Custom `FMPClient` on requests |
| `PyYAML` | Reference skills use it for CLI config files only; bot uses `config.json` + pydantic-settings | `json` stdlib + pydantic-settings |
| `hmmlearn` / `pomegranate` | ML regime detection adds latency, requires training data, non-explainable output — wrong tool for real-time gating | Deterministic component scoring from adapted reference skills |
| `PyPortfolioOpt` | Portfolio optimization library for mean-variance portfolios; overkill for per-trade ATR/Kelly sizing | Stdlib math + adapted `position_sizer.py` from reference skills |
| `alpaca-trade-api` (old SDK) | Deprecated, replaced by `alpaca-py` | Already using `alpaca-py` — do not add old SDK as transitive dep |
| `vectorbt` / `backtrader` | Backtesting frameworks — not needed for live pipeline execution | Not applicable to runtime pipeline |

---

## Stack Patterns by Variant

**If FMP_API_KEY is set:**
- `FMPClient` initializes, regime detection uses all 6 calculators with real data
- VCP screener and earnings drift screener are enabled
- `requests-cache` warms up on first 5-min cycle, subsequent cycles hit cache

**If FMP_API_KEY is absent:**
- `FMPClient` construction is skipped entirely
- `RegimeState` defaults to `RegimeLabel.TRANSITIONAL` with `top_risk=50` (neutral)
- `ExposureDecision` defaults to 50% max exposure, no bias
- Technical screener (Alpaca data only) still runs — bot is functional

**If trade history >= 20 closed theses:**
- Position sizing upgrades from ATR-only to Kelly (with Half-Kelly cap)
- `calculate_kelly()` reads `signal_postmortems` table for win_rate and avg_win/avg_loss

**If conviction_score < 0.50 (DEFAULT_CONFIG min_conviction):**
- Signal is dropped before reaching Claude analysis
- No ClaudeRecommendation generated, no API spend

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `requests>=2.31` | `requests-cache>=1.3.1` | requests-cache wraps requests.Session — must use same major version |
| `tenacity>=9.1.4` | Python 3.12+ | tenacity 9.x dropped Python 3.7 support; requires 3.8+ (3.12 fine) |
| `requests-cache>=1.3.1` | `sqlite3` stdlib | SQLite backend uses stdlib — no extra install needed |
| `pandas>=2.0` | `numpy>=1.26` | pandas 2.x requires numpy >=1.23; project already pins >=1.26 |
| `pandas-ta==0.4.71b0` | `pandas>=2.0` | pandas-ta 0.4.71b0 has known pandas 2.x compatibility issues with append(); already handled in existing market_scanner.py — no change needed for pipeline additions |

---

## Sources

- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/fmp_client.py` — FMP client pattern (requests, 300ms rate limit, in-memory cache, 429 retry)
- `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/scorer.py` — Regime composite scoring weights and classify_regime() logic
- `/tmp/claude-trading-skills/skills/position-sizer/scripts/position_sizer.py` — ATR-based, fixed fractional, and Kelly sizing implementations
- `/tmp/claude-trading-skills/skills/edge-signal-aggregator/scripts/aggregate_signals.py` — Weighted conviction scoring, dedup, contradiction detection
- `/tmp/claude-trading-skills/skills/exposure-coach/scripts/*.py` — Regime-to-exposure mapping (WEIGHTS dict, REGIME_SCORES mapping)
- https://pypi.org/project/fmp-data/ — fmp-data v2.2.1 verified (March 17, 2026); confirmed over-engineered for this use case
- https://pypi.org/project/requests-cache/ — requests-cache v1.3.1 verified (March 4, 2026); SQLite backend confirmed
- https://pypi.org/project/tenacity/ — tenacity v9.1.4 verified (February 7, 2026)
- `scripts/models.py` — Existing dataclass + enum pattern confirmed; new pipeline models follow same convention

---

*Stack research for: regime-aware signal pipeline rewrite (trading bot)*
*Researched: 2026-03-23*
