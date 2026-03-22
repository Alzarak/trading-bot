# Codebase Concerns

**Analysis Date:** 2026-03-22

## Tech Debt

**plugin.json missing marketplace fields:**
- Issue: `.claude-plugin/plugin.json` only has `name`, `version`, `description`, `author` — missing `license`, `keywords`, `commands`, `dependencies` fields required for marketplace distribution. `marketplace.json` does not exist at all.
- Files: `.claude-plugin/plugin.json`
- Impact: 13 tests in `tests/test_plugin_manifest.py` fail (marketplace tests, plus plugin.json field tests for `license`, `keywords`, `commands`, `dependencies`). Plugin cannot be published to marketplace without these fields.
- Fix approach: Add `license`, `keywords`, `commands`, `dependencies` fields to `plugin.json`. Create `.claude-plugin/marketplace.json` with `source`, `name`, `version`, `repository`, `description` fields. Update the placeholder GitHub repository URL to the real repo URL before publishing.

**Agent model mismatch — tests expect sonnet, files use haiku:**
- Issue: `agents/risk-manager.md` and `agents/trade-executor.md` specify `model: haiku` in their frontmatter. `tests/test_agents.py` and `tests/test_risk_manager.py` assert `model: sonnet`. 3 tests fail as a result.
- Files: `agents/risk-manager.md` (line 25), `agents/trade-executor.md` (line 25), `tests/test_agents.py` (lines 75, 120), `tests/test_risk_manager.py`
- Impact: 3 failing tests. The agents run on haiku but were designed and tested assuming sonnet. Risk-manager agent performing safety-critical risk checks runs on a weaker model.
- Fix approach: Either update `agents/risk-manager.md` and `agents/trade-executor.md` to `model: sonnet` to match test expectations, or update the 3 tests to assert `model: haiku`. The former is safer for risk-critical agents.

**pydantic-settings listed as dependency but never imported:**
- Issue: `requirements.txt` and the generated standalone `requirements.txt` (in `scripts/build_generator.py` line 345) both include `pydantic-settings>=2.0`, but no Python source file imports or uses `pydantic-settings` or `BaseSettings`. The bot reads config via `json.loads()` and reads env vars via `os.environ.get()`.
- Files: `requirements.txt`, `scripts/build_generator.py` (line 345)
- Impact: Unnecessary install overhead (pydantic-settings pulls in pydantic). Misleading — suggests a settings model exists that doesn't.
- Fix approach: Remove `pydantic-settings>=2.0` from `requirements.txt` and from the generated standalone requirements template in `scripts/build_generator.py`.

**email notification is a stub:**
- Issue: `Notifier.send()` in `scripts/notifier.py` advertises email support via `email_enabled` and `email_to` config fields but the email channel logs "not yet implemented" and sends nothing.
- Files: `scripts/notifier.py` (lines 78–83)
- Impact: Users who configure `email_enabled: true` in config.json receive no notifications via email with no visible failure — only a loguru INFO message.
- Fix approach: Either implement SMTP email via stdlib `smtplib`, or remove `email_enabled`/`email_to` from config docs/wizard until implemented.

**CLAUDE.md out of sync with plugin cache:**
- Issue: `CLAUDE.md` at the repo root has been updated with hooks constraints, MCP configuration notes, and the two-env-var distinction, but these additions are not present in the cached plugin copy at `~/.claude/plugins/cache/alzarak-plugins/trading-bot/1.0.0/CLAUDE.md`. The cache also carries an `.orphaned_at` marker file with timestamp `1774201266215`.
- Files: `CLAUDE.md`, `~/.claude/plugins/cache/alzarak-plugins/trading-bot/1.0.0/CLAUDE.md`
- Impact: If users are running via the cached plugin, they see the old CLAUDE.md. `skills/build/SKILL.md` and `references/alpaca-api-patterns.md` also differ between source and cache.
- Fix approach: Reinstall the plugin from source to refresh the cache: `claude plugins reinstall trading-bot`.

## Known Bugs

**`execute_claude_recommendation` uses `rec.stop_price` as `current_price` proxy:**
- Symptoms: In agent mode, `bot.py:383` calls `executor.execute_signal(signal, rec.stop_price)`. The `current_price` parameter controls position sizing (`equity * max_position_pct / current_price`). Using `stop_price` (which is set below entry) produces inflated share counts.
- Files: `scripts/bot.py` (line 381–383)
- Trigger: Any agent-mode trade execution via `execute_claude_recommendation()`.
- Workaround: None automatic. The code has a comment acknowledging this (`"Use stop_price as proxy for current_price since agent mode should supply accurate price via context"`). The `get_analysis_context()` function collects `current_price` per symbol but that data is not threaded through to `execute_claude_recommendation()`.

**`check-session.sh` Stop hook outputs `{"decision": "allow", ...}` — not valid hook output format:**
- Symptoms: The Stop hook at `hooks/check-session.sh` (line 33) emits `{"decision": "allow", "reason": "..."}` which is not a recognized Claude Code hook response schema. The PreToolUse hook correctly uses `hookSpecificOutput` + `permissionDecision`. The Stop hook has no `hookSpecificOutput` wrapper.
- Files: `hooks/check-session.sh` (line 33)
- Trigger: Any session stop when open positions or circuit breaker are present.
- Workaround: The hook exits 0 either way so it never blocks — the incorrectly formatted warning is simply ignored.

## Security Considerations

**Two env vars for paper trading mode — confusion risk:**
- Risk: The bot uses `ALPACA_PAPER` (set in `.env`, read as `config["paper_trading"]`). The Alpaca MCP server uses `ALPACA_PAPER_TRADE`. A user who disables paper mode on one system and forgets the other could execute live trades in one pathway while believing both are in paper mode.
- Files: `references/alpaca-api-patterns.md` (line 38–40), `CLAUDE.md` (line 60), `skills/trading-rules/SKILL.md` (line 56)
- Current mitigation: `CLAUDE.md` documents the distinction. `references/alpaca-api-patterns.md` has an explicit note. The initialize wizard sets `paper_trading` in `config.json` and writes `ALPACA_PAPER=true` to `.env` — it does not configure `ALPACA_PAPER_TRADE`.
- Recommendations: The initialize wizard should explicitly warn users when MCP is enabled that `ALPACA_PAPER_TRADE` is a separate control. Consider adding a verification step in `/trading-bot:run` that checks both settings are consistent.

**API keys requested in plaintext during `/trading-bot:initialize` interactive session:**
- Risk: The initialize wizard collects `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` interactively via `AskUserQuestion`. These appear in the Claude session context.
- Files: `skills/initialize/SKILL.md` (lines 47–49, 92–94)
- Current mitigation: Keys are written to `${CLAUDE_PLUGIN_DATA}/.env` only, never to `config.json`. `.env` is gitignored.
- Recommendations: This is an inherent limitation of the interactive setup flow. Document in the wizard that users can also pre-populate `.env` before running `/initialize`.

**`circuit_breaker.flag` resides in `CLAUDE_PLUGIN_DATA` which defaults to `/tmp` in some code paths:**
- Risk: `scripts/risk_manager.py` (line 56) uses `Path(os.environ.get("CLAUDE_PLUGIN_DATA", "/tmp"))` as the fallback. A `/tmp` circuit breaker flag is lost on reboot or cleared by OS temp cleanup.
- Files: `scripts/risk_manager.py` (lines 56, 117)
- Current mitigation: In plugin mode, `CLAUDE_PLUGIN_DATA` is always set by Claude Code. Fallback to `/tmp` only affects dev/test contexts. Hooks use `.plugin-data/` as dev fallback (consistent).
- Recommendations: Change the Python fallback from `/tmp` to a project-relative path (e.g., `.plugin-data/`) to match the hook fallback pattern.

## Performance Bottlenecks

**Market scanner fetches 60 days of 1-minute bars per symbol per scan cycle:**
- Problem: `scripts/market_scanner.py:183` requests 60 calendar days of minute bars every 60-second scan cycle. For 5 default symbols, that is 5 Alpaca IEX API calls each fetching ~43,200 bars.
- Files: `scripts/market_scanner.py` (line 183)
- Cause: No bar caching — each `scan()` call hits the API from scratch.
- Improvement path: Cache bars in memory (or SQLite) with incremental updates — fetch only the delta since last scan, append to cached DataFrame. Add `days_back` config option so users can tune warmup window vs. request size.

**`PreToolUse` hook intercepts every Bash call:**
- Problem: `hooks/hooks.json` sets the `PreToolUse` matcher to `"Bash"`, meaning every single Bash tool invocation Claude makes during a session triggers `validate-order.sh`. The script reads stdin, runs jq, and does grep on every call.
- Files: `hooks/hooks.json` (line 16), `hooks/validate-order.sh`
- Cause: Bash matcher is intentional (catches order commands regardless of how they're formed) but adds latency to non-trading operations.
- Improvement path: Acceptable for current scale. If hook execution latency becomes noticeable, consider narrowing the matcher or moving to a lighter check.

## Fragile Areas

**`build_generator.py` import rewriting via `str.replace`:**
- Files: `scripts/build_generator.py` (lines 63–65)
- Why fragile: Import rewriting uses simple string substitution: `content.replace("from scripts.strategies.", "from strategies.")` then `content.replace("from scripts.", "from ")`. Any import that does not follow the `from scripts.X` pattern (e.g., a new `import scripts.X` style or an `from scripts import X` form) would be missed silently, producing broken standalone scripts.
- Safe modification: Always add new cross-module imports in the `from scripts.X import Y` form. The test at `tests/test_build_generator.py` validates key modules are present in the standalone output but does not verify runtime import correctness.
- Test coverage: Import rewriting is tested structurally (file presence) but not functionally (can the generated scripts actually import their dependencies).

**`StateStore.upsert_position` uses `INSERT OR REPLACE` — deletes then re-inserts:**
- Files: `scripts/state_store.py` (lines 128–136)
- Why fragile: SQLite's `INSERT OR REPLACE` deletes the existing row and inserts a new one. If `opened_at` is not explicitly passed (defaults to current time), a crash-recovery upsert will silently reset the `opened_at` timestamp on an existing position. This corrupts position age tracking.
- Safe modification: When calling `upsert_position` for updates (not new inserts), always pass the existing `opened_at` from the fetched row. The crash recovery code in `reconcile_positions` does this correctly but callers could easily miss it.
- Test coverage: `tests/test_state_store.py` covers the three reconciliation cases but does not assert `opened_at` preservation on update.

**`validate-order.sh` PDT check relies on SQLite or JSON existing — no DB means no PDT check:**
- Files: `hooks/validate-order.sh` (lines 50–68)
- Why fragile: The hook only checks PDT count if `$CUTOFF` is non-empty AND either `trading.db` or `pdt_trades.json` exists. On a fresh installation before any trades have been made, neither file exists, and the PDT check silently passes (`COUNT=0`). This is correct behavior but the lack of any log output means there is no signal that the check was skipped.
- Safe modification: This is the intended design (Python RiskManager is the primary enforcer). Understand that the hook is a secondary defense; do not rely on it for the first-trade PDT check.

**Agent mode `run.md` step 5 uses a Python one-liner placeholder:**
- Files: `skills/run/SKILL.md` (lines 88–94)
- Why fragile: Step 5 shows a bash block with `# ... parse and execute recommendations through risk manager` comment and instructs Claude to "Replace placeholder with actual JSON recommendations." The step depends entirely on Claude correctly inlining the JSON from step 4 into a working Python call — there is no fixed code template. If Claude's inlined code is malformed, order execution silently fails.
- Safe modification: This is a prompt-engineering dependency. The audit logger captures attempts before execution, so failures leave a trace in `audit/claude_decisions.ndjson`.
- Test coverage: `tests/test_bot.py` tests `execute_claude_recommendation()` directly with mocked inputs but does not test the `/run` skill's step 5 Python generation end-to-end.

## Scaling Limits

**Watchlist polling rate — IEX feed limits:**
- Current capacity: 60-second scan cycles across default 5 symbols.
- Limit: The Alpaca IEX free feed has rate limits. Fetching 60 days of minute bars for 20+ symbols at 60-second intervals will trigger HTTP 429 errors (documented in `.planning/research/PITFALLS.md`).
- Scaling path: Implement bar caching with incremental updates. Consider WebSocket streaming for real-time data above ~15 symbols. Add retry-with-backoff in `market_scanner.fetch_bars()`.

## Dependencies at Risk

**`pandas-ta==0.4.71b0` — beta release, non-standard column naming:**
- Risk: Pinned to a beta version (`0.4.71b0`). The BBands column naming quirk (`BBL_{period}_{std}_{std}` with std repeated twice) is a known beta-release artifact documented in `scripts/market_scanner.py` (line 162). This naming may change in a stable release.
- Impact: If `pandas-ta` is upgraded, Bollinger Band column names may change and all BB-based strategies (mean_reversion, possibly others) silently produce empty DataFrames after `dropna()`.
- Migration plan: Pin remains necessary. Monitor pandas-ta releases. The `get_indicator_columns()` method is the single source of truth — update there if column names change.

**`APScheduler>=3.10,<4.0` — version cap for breaking API change:**
- Risk: APScheduler 4.x is a complete rewrite with incompatible API. `requirements.txt` caps below 4.0. If a user upgrades packages without pinning, they could receive APScheduler 4.x via pip.
- Impact: `BackgroundScheduler`, `IntervalTrigger`, `CronTrigger` imports in `scripts/bot.py` break. Bot fails to start.
- Migration plan: Cap is already in place. Consider pinning more tightly (e.g., `APScheduler>=3.10,<4.0`) — which is already done. No action needed unless migrating to APScheduler 4.x intentionally.

## Missing Critical Features

**No wash sale rule enforcement:**
- Problem: The 30-day wash sale rule (IRS rule prohibiting repurchase of a substantially identical security within 30 days of a loss-sale) is not implemented. The PDT guard protects against regulatory designation but the wash sale rule affects tax treatment.
- Blocks: Live trading at tax time — bot could repeatedly trade the same symbol creating wash sale disallowances with no warning.
- Note: Documented in `.planning/STATE.md` as a research flag deferral ("Determine during Phase 3 planning whether 31-day re-entry block is v1 or deferred").

**No position exit on signal reversal — only SELL signals close positions:**
- Problem: The trading loop only closes positions when a `SELL` signal fires for that symbol. If a strategy generates repeated `BUY` signals on an already-open position, the position grows (bracket orders stack). There is no "close on opposite signal" logic.
- Blocks: Proper position management — a BUY-heavy strategy in a trending market could exceed `max_position_pct` via stacked bracket entries.

## Test Coverage Gaps

**`hooks/check-session.sh` (Stop hook) — zero test coverage:**
- What's not tested: The entire Stop hook script has no tests. No test verifies it handles the database-missing case, the open-positions case, or the circuit breaker warning case.
- Files: `hooks/check-session.sh`
- Risk: Incorrect JSON output format (uses `{"decision": "allow"}` instead of `hookSpecificOutput` structure) goes undetected.
- Priority: Medium — the hook only warns, never blocks, so incorrect output is swallowed silently.

**`skills/*.md` wizard flows — zero integration tests:**
- What's not tested: The initialize, build, and run command skills are prompt documents. No tests verify the wizard produces valid `config.json`, that the MCP install step succeeds, or that the standalone build can execute.
- Files: `skills/initialize/SKILL.md`, `skills/build/SKILL.md`, `skills/run/SKILL.md`
- Risk: Wizard instruction drift — a change to one skill step could produce invalid config or a non-functional build without any test catching it.
- Priority: Medium — structural config schema tests (`tests/test_config.py`) partially cover the output contract.

**`scripts/build_generator.py` — generated scripts not tested for runtime import correctness:**
- What's not tested: `tests/test_build_generator.py` checks that `generate_build()` produces the expected files and that key content is present (e.g., `ALPACA_PAPER=true` in `.env.template`). It does not run the generated standalone `bot.py` or verify that the rewritten imports actually resolve.
- Files: `scripts/build_generator.py`, `tests/test_build_generator.py`
- Risk: A refactor that changes import style in any script file could produce a broken standalone build that passes all tests.
- Priority: Low — the current import rewriting pattern is simple and tested at the string level.

**Agent mode `execute_claude_recommendation` — `stop_price` as `current_price` proxy not tested:**
- What's not tested: The known inaccuracy (using `rec.stop_price` instead of `current_price` for position sizing) is not captured in any test assertion. Tests in `tests/test_bot.py` mock the executor but don't verify sizing accuracy.
- Files: `scripts/bot.py` (line 383), `tests/test_bot.py`
- Risk: Position sizes in agent mode are systematically inflated (stop_price < entry_price, so `equity / stop_price` > `equity / entry_price`).
- Priority: High — affects real money in live trading mode.

---

*Concerns audit: 2026-03-22*
