# Pitfalls Research

**Domain:** Regime-aware multi-screener trading signal pipeline (Python, Alpaca, FMP)
**Researched:** 2026-03-23
**Confidence:** HIGH (pitfalls drawn from existing codebase failure analysis + verified research)

---

## Critical Pitfalls

### Pitfall 1: ATR Computed on 5-Minute Bars Used as Dollar Stop Distance

**What goes wrong:**
`pandas-ta` names the ATR column `ATRr_{period}` — the "r" stands for "ratio" (ATR as a fraction of close, not raw price distance in dollars). The current code passes this ratio value directly as `atr` in `ClaudeRecommendation` and uses `stop_price = entry - (atr * 2.0)`. On a $10 stock with ATR=0.014 (1.4%), the stop becomes `10 - 0.028 = $9.97` — 3 cents away on a 5-minute bar. Any noise wicks the stop immediately.

**Why it happens:**
`pandas-ta` has two ATR variants: `ATR` (absolute dollars) and `ATRr` (True Range ratio). The current `compute_indicators` calls `df.ta.atr()` which appends `ATRr_{period}`, not `ATR_{period}`. The naming was documented as a "quirk" in `market_scanner.py` line 146 but the downstream sizing logic never compensated for it.

**How to avoid:**
In `pipeline/screeners.py`, compute ATR in absolute dollars: multiply `ATRr` by `close` price to get dollar ATR before passing to signals. Or switch to `df.ta.atr(true_range=True)` which produces the absolute column. Verify the column name and value against a known price before using it in stop calculations.

**Warning signs:**
- Stop distance is less than the bid-ask spread on the scanned symbol
- Stops fire on the same bar as entry (visible in backtesting or paper trade logs)
- `atr` values in log output are below 0.10 for $10+ stocks (indicating ratio, not dollars)

**Phase to address:**
Phase: Screeners — when `technical_scan()` generates `RawSignal.atr` and `RawSignal.stop_price`, validate ATR is in dollar units before the signal leaves the screener.

---

### Pitfall 2: Regime Cache Goes Stale During Intraday Regime Flips

**What goes wrong:**
The plan caches regime state for 1 hour (`regime_cache_ttl_seconds: 3600`). If the market shifts from "green" to "red" zone during the cache window (e.g., a Fed announcement at 2 PM causes a spike in top_risk from 35 to 80), the bot keeps trading as if conditions are safe. All new BUY orders submitted between the flip and the next cache refresh are placed in hostile conditions.

**Why it happens:**
Hourly caching is reasonable for macro regime (weekly/monthly data from FMP) but top_risk uses intraday market data (RSP/SPY ratios, HYG/LQD). These components can move significantly within an hour. The macro regime label changes slowly; the top_risk score can change fast.

**How to avoid:**
Split the cache TTL by component type in `pipeline/regime.py`. Cache the macro regime label hourly (it is weekly/monthly data — changes slowly). Cache the top_risk score with a 15-minute TTL (it uses intraday price ratios). When top_risk crosses a zone boundary (e.g., from yellow to red), invalidate the cache and force a refresh before the next BUY signal is emitted, regardless of TTL.

**Warning signs:**
- Regime log shows "green" zone while SPY is down 2%+ intraday
- BUY signals generated during obvious market selloffs
- top_risk value in logs unchanged for 60+ minutes on volatile days

**Phase to address:**
Phase: Regime + Exposure — implement split TTL in `RegimeDetector.__init__` with separate `_macro_cached_at` and `_top_risk_cached_at` timestamps.

---

### Pitfall 3: Conviction Score Inflation When All Active Screeners Agree (Single-Source Dominance)

**What goes wrong:**
When only the technical screener is enabled (the default), the aggregator receives only one source. The agreement bonus (`two_skills_bonus: 0.10`, `three_plus_skills_bonus: 0.20`) never fires but the base conviction still passes `min_conviction: 0.50` whenever the technical score is high. This mimics the original 2-of-N failure mode — a single screener with inflated score generates trades in any direction the indicator happens to point.

**Why it happens:**
The aggregator was designed for multi-source input; it degrades gracefully to single-source but without recalibrating thresholds. A technical score of 0.55 that would be filtered out in a 3-screener system passes cleanly in a 1-screener system because the threshold doesn't tighten with reduced source count.

**How to avoid:**
In `pipeline/aggregator.py`, scale `min_conviction` dynamically by active source count. With 1 source: require 0.65. With 2 sources: require 0.55. With 3+ sources: use configured 0.50. Document this in config comments so the operator knows the effective threshold changes when they enable FMP screeners.

**Warning signs:**
- All or nearly all scanned symbols produce BUY signals on up-trending days
- Conviction scores cluster tightly near the min_conviction threshold (0.50-0.55)
- Trade frequency spikes when market is moving strongly in any direction

**Phase to address:**
Phase: Aggregation — `SignalAggregator.aggregate()` should accept `active_source_count` and apply the scaling table.

---

### Pitfall 4: Kelly Criterion Applied to Insufficient Trade History

**What goes wrong:**
Kelly requires accurate win rate and average win/loss estimates. With fewer than 30 closed trades, the win rate estimate has a confidence interval of ±15-20 percentage points. A true 50% win rate could be estimated as 65% from a lucky 10-trade sample, causing Kelly to recommend 2x the appropriate bet size. Over-Kelly betting creates negative median growth even with a positive-expectancy strategy — the bot ramps up size into a drawdown period.

**Why it happens:**
The position-sizer skill's `calculate_kelly()` function accepts any win_rate value and does not enforce a minimum sample size guard. When `thesis_manager` begins populating postmortem data, the sizer may get called with 5-10 completed trades and treat the result as reliable.

**How to avoid:**
In `pipeline/sizer.py`, require a minimum of 30 closed theses before switching to Kelly mode. Before that threshold, force `method = "atr"`. When Kelly is available, cap at fractional Kelly (multiply result by 0.5) to account for estimation error. Never let Kelly produce a bet above `max_position_pct` regardless of the formula result.

**Warning signs:**
- Kelly-recommended size exceeds ATR-recommended size by more than 2x
- Fewer than 30 rows in the `theses` table with `status = "CLOSED"` but Kelly mode is active
- Position sizes grow progressively larger after a winning streak

**Phase to address:**
Phase: Position Sizer — add `min_kelly_sample_size: 30` guard in `SizingEngine.calculate()`.

---

### Pitfall 5: FMP Earnings Data Reflects Current Consensus, Not Historical Point-in-Time

**What goes wrong:**
The FMP Analyst Estimates API returns the current consensus snapshot. If you query it today for a stock that reported earnings 3 weeks ago, the estimate field reflects the post-announcement revised consensus, not the pre-announcement expectation. This means historical backtesting of the earnings drift screener is impossible with FMP's live API alone — you'd be computing "drift" against already-updated numbers and getting near-zero drift for every stock.

**Why it happens:**
FMP's free and lower-tier plans do not provide point-in-time historical estimate snapshots. The drift signal requires repeatedly capturing the consensus over time and storing local timestamps. The earnings-trade-analyzer skill was designed to be run repeatedly over multiple sessions, accumulating local history. Running it as a one-shot call in a pipeline loop misses the temporal delta.

**How to avoid:**
In `pipeline/screeners.py`, the `earnings_drift_scan()` must store FMP earnings snapshots to a local cache table on every poll cycle. The "drift" is computed between the stored snapshot and the current snapshot, not against a single live API call. Add a `fmp_estimates_cache` table to SQLite: `(symbol, fiscal_period, eps_estimate, captured_at)`. Only use the drift signal if two captures are at least 24 hours apart.

**Warning signs:**
- Earnings drift score is consistently 0 or very low across all symbols
- The screener always polls FMP but never produces a signal above threshold
- `captured_at` column has only one entry per symbol (no temporal delta available)

**Phase to address:**
Phase: FMP Client + Screeners — `fmp_client.py` must write snapshot data to SQLite on every successful poll; `earnings_drift_scan()` reads delta from local store.

---

### Pitfall 6: Claude Prompt Receives No Regime Context (Overconfidence on Hostile Days)

**What goes wrong:**
The current `claude_analyzer.py` sends only the last 5 indicator rows plus a strategy name. Claude has no awareness of macro regime, top_risk score, or exposure ceiling. Claude can return `confidence: 0.85, action: BUY` for a stock showing a momentum setup even when the bot is in sell-only mode due to `top_risk >= 70`. The bot then has to discard the recommendation after the fact, wasting the API call and creating log noise that looks like unexplained filtering.

**Why it happens:**
The old analyzer predates the pipeline redesign. The new `pipeline/analyzer.py` is meant to replace it, but if the regime context block is omitted from the prompt, Claude calibrates confidence against the isolated technical picture, not the full risk environment.

**How to avoid:**
The `PipelineAnalyzer.build_prompt()` must always include a `## Market Context` section with regime label, top_risk score, risk zone, and current exposure percentage before asking for a recommendation. Explicitly instruct Claude: "If top_risk >= 70, do NOT recommend BUY — return HOLD instead." This aligns Claude's confidence calibration with the gating rules already enforced in Python, reducing wasted calls.

**Warning signs:**
- Claude returns BUY recommendations that are immediately discarded by regime gate
- `confidence` values from Claude cluster above 0.80 regardless of market conditions
- Logs show "regime gate blocked" on the majority of Claude recommendations during downtrends

**Phase to address:**
Phase: Pipeline Analyzer — `PipelineAnalyzer` must receive `RegimeState` and `ExposureDecision` as required constructor/call arguments.

---

### Pitfall 7: Thesis Lifecycle State Machine Allows Contradictory Transitions

**What goes wrong:**
Without strict transition enforcement, the thesis table accumulates invalid states: `ACTIVE` theses that have no `actual_entry` price (order never filled but status advanced), or `CLOSED` theses that still have open positions in Alpaca. These orphaned states cause the exposure calculation to count phantom positions against the ceiling, blocking real trades, or to miss real open positions, allowing over-exposure.

**Why it happens:**
State machine correctness in SQLite requires explicit transition validation before every UPDATE. If `thesis_manager.py` is written with simple status assignments (`UPDATE theses SET status = 'ACTIVE'`) without checking the prior state, a crash between the order submission and the fill confirmation can leave a thesis in a mid-transition state forever.

**How to avoid:**
In `pipeline/thesis_manager.py`, enforce state transitions with conditional UPDATE statements:
```sql
UPDATE theses SET status = 'ACTIVE', actual_entry = ?
WHERE thesis_id = ? AND status = 'ENTRY_READY'
```
If `rowcount == 0`, the transition was invalid — log and alert. Reconcile the thesis table against actual Alpaca positions on every bot startup to detect orphans. Add a `reconcile_on_startup()` method that queries Alpaca positions and cross-references the `theses` table.

**Warning signs:**
- `theses` table has `status = 'ACTIVE'` rows with `actual_entry = NULL`
- Exposure ceiling calculation differs significantly from the Alpaca portfolio value
- Startup logs show no reconciliation step

**Phase to address:**
Phase: Thesis Manager — all UPDATE statements must use conditional transitions; `bot.py` must call `thesis_manager.reconcile_on_startup()` before the first scan cycle.

---

### Pitfall 8: Lookforward Contamination in Technical Screener Signal Scores

**What goes wrong:**
The screener computes indicators on the full bar history returned by `fetch_bars()` then scores the last row. This is correct for live trading. However, if any normalization step (e.g., percentile rank of RSI within the fetched window, z-score of volume) is computed over the entire fetched DataFrame before extracting the last row, the last-bar score implicitly "knows" about the distribution of past bars — including bars that would not exist at the time the score was used historically. This means signal scores in any walk-forward validation will be systematically optimistic.

**Why it happens:**
Percentile-based normalization and z-score rescaling require a lookback window. If that window includes the entire fetched history (e.g., 60 days of 1-minute bars), and the normalized score is used to gate entry, then the "strength" of any historical signal was computed using future bars relative to the signal date.

**How to avoid:**
In `pipeline/screeners.py`, all normalization must use a trailing window only. Never apply `.rank(pct=True)` or `.zscore()` to the full DataFrame and use the last value. Instead, compute the trailing 20-bar percentile rank explicitly: `df['rsi_rank'] = df['rsi'].rolling(20).rank(pct=True)`. This is safe because each rank value only uses bars that existed at that timestamp.

**Warning signs:**
- Backtest Sharpe ratio drops sharply when switching from full-window normalization to rolling-window normalization
- Signal scores on historical data are consistently higher than live scores for the same indicator levels

**Phase to address:**
Phase: Screeners — any normalization step in `technical_scan()` must be implemented with explicit rolling windows.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `ATRr` value directly as dollar ATR | Avoids changing existing market_scanner API | Stops fire on noise — every backtested strategy will show negative expectancy | Never |
| Single global `min_conviction = 0.50` regardless of source count | Simple config | Technical-only mode generates excessive false signals | Never |
| Skip thesis reconciliation at startup | Faster boot | Phantom positions block real trades after crashes | Never — add it in phase 1 |
| Kelly without minimum sample guard | Simpler code | Over-bets after lucky streaks, blows up in drawdown | Never — always enforce 30-trade minimum |
| Store FMP estimates in memory only (no SQLite cache) | No schema migration needed | Earnings drift signal requires temporal delta, can never work without local history | Never for earnings_drift_scan |
| Hardcode regime TTL at 60 minutes for all components | Simple | Misses intraday regime flips on top_risk score | Acceptable only for pure macro regime label, not top_risk |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FMP API — Earnings Estimates | Treating live API response as point-in-time historical data | Store snapshots locally on each poll; compute drift from local delta |
| FMP API — Rate Limits | No per-session request count, hitting bandwidth cap mid-session | Implement a request counter in `fmp_client.py`; cache aggressively with TTLs matched to data freshness (earnings: 4h, macro: 1h) |
| Alpaca IEX Feed — Bar Gaps | Assuming consecutive 1-minute bars with no gaps; dropna removes all rows for illiquid symbols | Check `len(df)` after `compute_indicators`; warn if fewer than 20 bars remain after dropna |
| pandas-ta `ATRr` vs `ATR` | Using `ATRr` (ratio) as dollar stop distance | Multiply `ATRr` by `close` to get dollar ATR; or call `df.ta.true_range()` for absolute ATR |
| Alpaca ScreenerClient API key access | Accessing private `_api_key` and `_secret_key` fields (used in existing `discover_symbols`) | Pass keys from config through `MarketScanner` constructor rather than reflecting private attributes |
| SQLite concurrent writes | Multiple APScheduler jobs writing simultaneously without explicit transactions | Use `BEGIN EXCLUSIVE` transactions in `thesis_manager.py`; all state writes are serialized |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching 60 days of 1-minute bars for every symbol on every 5-min cycle | Scan cycle takes 60-90 seconds; API rate limit warnings | Cache bars in memory; only re-fetch the delta since last scan | At 10+ symbols in watchlist |
| Calling FMP for regime data on every scan cycle (no cache) | FMP bandwidth exhausted within hours; graceful degradation fires too often | Honor `regime_cache_ttl_seconds` strictly; persist cache to SQLite so it survives restarts | Immediately on FMP tier with bandwidth cap |
| Computing full indicator set for symbols that fail regime gate | Wasted CPU and Alpaca API calls for symbols that will never reach Claude analysis | Apply regime gate before symbol-level bar fetching when `top_risk >= 70` (skip BUY scan entirely) | At 20+ symbol watchlist |
| Thesis postmortem weight feedback applied synchronously on CLOSE | Slows the trade execution path; blocks order confirmation while postmortem runs | Run `postmortem.record_outcome()` asynchronously (APScheduler job or thread pool) | Immediately if postmortem includes FMP API calls |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging `ClaudeRecommendation.reasoning` at INFO level in production | Reasoning often contains symbol names + price levels — creates trading intent paper trail visible in log aggregators | Log reasoning at DEBUG level only; use sanitized summary at INFO |
| FMP API key stored in `config.json` directly | Key committed to git if `config.json` is not gitignored | Use `fmp_api_key_env: "FMP_API_KEY"` indirection (already planned); validate `.gitignore` excludes `.env` |
| Alpaca paper/live mode flag not validated at startup | Connecting to live account with paper keys silently fails or connects to wrong environment | Assert `ALPACA_PAPER` env var on startup and log which mode is active; refuse to start if var is missing |

---

## "Looks Done But Isn't" Checklist

- [ ] **ATR in dollar units:** `RawSignal.atr` must be in dollars, not ratio — verify with `assert signal.atr > 0.01 * entry_price` before stop computation
- [ ] **Regime cache split:** Check that `top_risk` has a shorter TTL than macro regime label in `RegimeDetector`
- [ ] **Thesis reconciliation:** Verify `reconcile_on_startup()` runs before the first `scan_and_trade()` call in `bot.py`
- [ ] **Kelly minimum sample guard:** Confirm `sizer.py` returns to ATR method when `closed_theses < 30`
- [ ] **FMP snapshot persistence:** Confirm `fmp_estimates_cache` table exists in SQLite with `captured_at` column after first run
- [ ] **Aggregator source-count scaling:** Verify `min_conviction` threshold is higher when only 1 screener is active
- [ ] **Claude prompt regime block:** Confirm `## Market Context` section appears in every prompt sent to Claude with `top_risk` value present
- [ ] **Contradictory thesis transitions:** Test that `UPDATE WHERE status = 'ENTRY_READY'` returns `rowcount == 0` when thesis is already `ACTIVE` (simulate double-fill scenario)
- [ ] **Rolling normalization:** Any `rank(pct=True)` or z-score in screeners uses `rolling(N)` not full DataFrame

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| ATR dollar/ratio confusion in live trades | HIGH | Stop bot; audit all open positions for stop price sanity; manually close any where stop is within 0.5% of entry; fix ATR computation; restart in paper mode |
| Stale regime cache allowed buys during selloff | MEDIUM | Review all fills during the stale window; compare against regime score at fill time; assess P&L impact; tighten TTL |
| Orphaned ACTIVE theses after crash | MEDIUM | Run `reconcile_on_startup()` manually; cross-reference Alpaca `/positions` endpoint; manually CLOSE any thesis with no matching open position |
| Kelly over-bet during lucky streak | HIGH | Reduce `max_position_pct` immediately; enforce ATR-only mode until drawdown recovers; add 30-trade guard in code |
| FMP snapshot not stored — drift signal never fires | LOW | Add `fmp_estimates_cache` table; accept that earnings_drift_scan will produce no signals for 24 hours while baseline builds |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| ATR dollar/ratio confusion | Phase: Screeners (technical_scan) | Unit test: `signal.atr` for a $10 stock should be > $0.05 and < $2.00 |
| Regime cache stale for top_risk | Phase: Regime + Exposure | Integration test: assert top_risk cache TTL is 15 min, macro label TTL is 60 min |
| Conviction inflation (single source) | Phase: Aggregation | Unit test: single-source conviction threshold = 0.65, not 0.50 |
| Kelly without sample guard | Phase: Position Sizer | Unit test: Kelly method with 10 closed trades → falls back to ATR method |
| FMP point-in-time earnings data | Phase: FMP Client + Screeners | Integration test: two sequential polls store two rows in `fmp_estimates_cache` |
| Claude receives no regime context | Phase: Pipeline Analyzer | Prompt inspection test: `## Market Context` present and `top_risk` value non-zero |
| Thesis state machine orphans | Phase: Thesis Manager | Unit test: duplicate ACTIVE transition returns rowcount=0 and logs error |
| Lookforward in normalization | Phase: Screeners | Assert no `.rank(pct=True)` call operates on non-rolling Series |

---

## Sources

- Codebase analysis: `/home/parz/projects/trading-bot/scripts/market_scanner.py` line 146 (ATRr naming note), `claude_analyzer.py` stop computation
- Reference skill: `/tmp/claude-trading-skills/skills/position-sizer/scripts/position_sizer.py` (Kelly validation requirements)
- Reference skill: `/tmp/claude-trading-skills/skills/edge-signal-aggregator/scripts/aggregate_signals.py` (DEFAULT_CONFIG weights and agreement bonuses)
- Reference skill: `/tmp/claude-trading-skills/skills/macro-regime-detector/scripts/scorer.py` (component TTL separation rationale)
- FMP earnings API point-in-time limitation: https://site.financialmodelingprep.com/education/calendar/build-an-earnings-revision-pressure-signal-estimate-drift-monitor
- Kelly over-betting risk: https://medium.com/@idsts2670/why-do-even-excellent-traders-go-broke-the-kelly-criterion-and-position-sizing-risk-62c17d279c1c
- ATR timeframe mismatch: https://chartingpark.com/articles/atr-stop-loss-basics
- Lookforward bias taxonomy: https://www.luxalgo.com/blog/backtesting-traps-common-errors-to-avoid/
- LLM trading overconfidence: https://arxiv.org/html/2502.15800v3

---
*Pitfalls research for: Regime-aware multi-screener trading signal pipeline*
*Researched: 2026-03-23*
