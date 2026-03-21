# Project Research Summary

**Project:** Automated Stock Day Trading Claude Code Plugin
**Domain:** Algorithmic trading bot distributed as a Claude Code plugin (Alpaca API, Python)
**Researched:** 2026-03-21
**Confidence:** HIGH

## Executive Summary

This project is a Claude Code plugin that enables users to configure, generate, and run an autonomous day trading bot against the Alpaca brokerage API. Expert builders in this domain follow a clear three-phase architecture: an interactive setup phase that captures user preferences, a code-generation phase that produces inspectable Python scripts, and an autonomous execution phase that runs a structured trading loop. The plugin's key differentiator over rule-based bots is Claude's contextual reasoning — but research is unambiguous that Claude must operate as a strategy-level reasoning layer, not as a per-trade execution layer. Orders must always flow through a deterministic Python risk management chain; Claude never submits orders directly.

The recommended stack is Python 3.12+, `alpaca-py` 0.43.2 (the official and only maintained Alpaca SDK), `pandas-ta` for technical indicators (pip-installable, no C compiler needed), `APScheduler` for market-hours-aware scheduling, `pydantic-settings` for typed configuration, `loguru` for structured audit logging, and the official Alpaca MCP server to give Claude real-time market data access within its context window. The Claude Code plugin layer wraps this runtime with three slash commands (`/initialize`, `/build`, `/run`), specialist agents (setup-wizard, market-analyst, risk-manager, trade-executor), auto-injected skills for trading rules, and a `PreToolUse` hook as a hard safety gate before any Alpaca order tool call.

The most critical risks fall into two categories: safety and correctness. Safety risks include a runaway bot draining an account without circuit breakers, PDT rule violations causing 90-day trading lockouts, and API key exposure through generated files. Correctness risks include LLM hallucination of market data, ghost positions from network failures, and the paper-to-live performance gap that creates false confidence. All of these have well-understood mitigations — the danger is treating them as optional features rather than foundational infrastructure.

---

## Key Findings

### Recommended Stack

The stack is well-established and high-confidence. `alpaca-py` (not the deprecated `alpaca-trade-api`) is the only viable Alpaca SDK. `pandas-ta` is the correct technical indicator library for a distributable plugin because it installs via pip without compiling native code, unlike TA-Lib. `APScheduler 3.x` (not 4.x alpha) handles market-hours scheduling with timezone-aware cron triggers. The Alpaca MCP server, distributed via `uvx`, provides Claude with live market data as first-class tools — this is the architecture that enables the Claude-analysis differentiator.

**Core technologies:**
- `alpaca-py` 0.43.2: Official Alpaca SDK — `TradingClient`, `StockDataStream`, `StockHistoricalDataClient`; the only maintained option
- `pandas-ta` 0.4.71b0: 150+ technical indicators, pip-installable (no C compiler), requires Python 3.12+
- `APScheduler` 3.x: Timezone-aware scheduling with market-hours cron triggers; stick to 3.x (4.x is alpha rewrite)
- `pydantic-settings` 2.x: Typed config loading from `.env`; consistent with `alpaca-py`'s own pydantic v2 usage
- `loguru`: Structured audit logging for unattended operation; replaces stdlib logging boilerplate
- `alpaca-mcp-server` (uvx): Official MCP server giving Claude direct access to 43 Alpaca API tools
- `APScheduler` + `zoneinfo` (stdlib): Market-hours scheduling and US/Eastern timezone without extra install

### Expected Features

The feature research identifies a clear v1/v1.x/v2 split. The slash command trio (`/initialize`, `/build`, `/run`) is the entire product skeleton — nothing else works without it. Risk controls (position sizing, daily circuit breaker, market hours guard, stop-loss on every order) are non-negotiable for v1 regardless of whether paper or live mode is used. Claude-powered trade analysis and multi-agent architecture are explicitly post-validation features — implement the deterministic loop first.

**Must have (table stakes):**
- `/initialize` command with setup-wizard agent — captures all preferences, generates `config.json`
- `/build` command — generates inspectable Python scripts from config templates
- `/run` command — launches autonomous trading loop
- Paper + live trading mode (one config flag, same code)
- Market + bracket orders (stop-loss + take-profit in single Alpaca call)
- Position sizing as percentage of equity per trade
- Daily loss circuit breaker (hard halt when threshold breached)
- Market hours guard (check `alpaca.get_clock()` before every loop iteration)
- Trade logging to file (timestamp, ticker, action, price, P&L)
- Portfolio P&L tracking
- Graceful shutdown (close or log open positions on SIGINT/SIGTERM)
- RSI + MACD technical indicators (sufficient for two common strategies)
- Momentum strategy (one working end-to-end strategy for v1 validation)
- Error handling with exponential backoff on all API calls
- Beginner/expert mode toggle (defaults, verbosity, safety guardrails)

**Should have (v1.x, add after validation):**
- Trailing stop-loss and ATR-based dynamic stop placement
- Additional strategies (mean reversion, breakout, VWAP reversion)
- Alpaca MCP server integration + Claude-powered trade analysis
- End-of-day summary report
- PDT rule awareness (warn/block approaching 4th day trade in 5-day window)
- Event notifications (Slack/email webhooks)

**Defer (v2+):**
- Autonomous aggression adjustment by Claude
- Standalone server/VPS mode as extracted entrypoint
- News sentiment via Alpaca news endpoint
- Multi-agent plugin architecture (scanner/risk/execution as separate plugin agents)
- Crypto trading via Alpaca

**Anti-features (never build for v1):** backtesting engine, web dashboard, real-time WebSocket for data (use REST polling in v1), multiple broker support, options trading, margin/leverage trading, ML model training.

### Architecture Approach

The architecture has two distinct layers: the Claude Code plugin layer (commands, agents, skills, hooks, MCP server) and the generated Python runtime layer (produced by `/build`). These must stay cleanly separated — plugin scaffolding must not bleed into trading logic. The core pattern is Initialize → Build → Run with no phase bleeding. Within the runtime, the data flow is: Market Scanner → Signal Generator (indicators + optional Claude call) → Risk Manager (pre-trade checks, position sizing) → Order Executor (Alpaca API) → Portfolio Tracker (SQLite). Claude sits between Signal Generator and Risk Manager as a JSON-returning reasoning layer; it never calls Alpaca directly. All state persists to SQLite so the loop can resume after crashes without amnesia.

**Major components:**
1. `/initialize` + `setup-wizard` agent — elicits preferences, writes `config.json` (the source of truth for everything downstream)
2. `/build` command + Jinja2 templates — renders `config.json` into the full Python runtime in a generated directory
3. `/run` command + `market-analyst`/`trade-executor`/`risk-manager` agents — orchestrates the trading loop in Claude Code mode
4. Market Scanner → Signal Generator → Risk Manager → Order Executor → Portfolio Tracker — the Python runtime pipeline
5. SQLite state store — persists all trades, positions, P&L, and session state for crash recovery
6. `trading-rules` skill + `PreToolUse` hook — auto-injected context and hard safety gate before any Alpaca order call
7. Alpaca MCP server — real-time market data and account state exposed as Claude tools

### Critical Pitfalls

1. **No circuit breakers** — A bot without a hard daily loss limit and total drawdown halt will drain an account during any bad session. Circuit breakers are Phase 1 infrastructure, not optional configuration. Implement: daily loss limit (3% equity), total drawdown halt (10-15%), maximum concurrent positions, maximum position size per ticker.

2. **PDT rule violation causing 90-day lockout** — A bot that executes 4+ day trades in a 5-business-day window on a margin account with under $25,000 equity gets locked out for 90 days. The bot must maintain a rolling 5-day day-trade counter and halt new entries when the count reaches 3. During `/initialize`, ask for account equity and account type (margin vs. cash).

3. **LLM hallucination of market data** — If Claude is ever asked to supply tickers, prices, or market facts rather than reason over provided Alpaca data, it will hallucinate. The pattern is strict: always inject real Alpaca data into Claude's prompt; Claude never generates market data. Validate all Claude output before acting on it.

4. **Ghost positions from network failures** — Treating an HTTP timeout as "order failed" without querying Alpaca's actual positions creates unmanaged ghost positions. Every order submission must use an idempotency key (`client_order_id`) and verify actual state via `GET /v2/positions` before retrying. On startup, always reconcile with Alpaca's live position state.

5. **API key exposure in generated files** — The `/build` command generates Python files. If API keys are written into those files rather than read from environment variables, a single `git push` to a public repo exposes them. Never write key values into generated files; use `os.environ` references only; auto-generate `.env` and `.gitignore` as part of `/build`.

---

## Implications for Roadmap

Based on research, the build order is constrained by a hard dependency chain: config schema must exist before any script can be generated; risk management must exist before any order can be submitted; the deterministic loop must be validated before Claude analysis is layered on. Suggested phase structure:

### Phase 1: Plugin Foundation and Setup Flow

**Rationale:** Everything depends on the config schema and `/initialize` flow. The setup-wizard agent, config.json schema, plugin manifest, MCP server configuration, and `trading-rules` skill must all exist before any downstream work is possible. This phase produces no trading functionality but is the foundation for all of it.

**Delivers:** Claude Code plugin installable structure; `/initialize` command; `setup-wizard` agent; config.json schema with validation; Alpaca MCP server wired into `.mcp.json`; `trading-rules` skill auto-injected into all agents; plugin SessionStart hook that installs Python dependencies.

**Addresses:** Beginner/expert mode toggle, Alpaca authentication setup, paper/live mode configuration, capital adequacy check and PDT warning during onboarding.

**Avoids:** Hardcoded preferences in plugin code (anti-pattern); secrets in generated files (must establish `.env` pattern here).

**Research flag:** Standard patterns — Claude Code plugin structure is well-documented via official sources. No additional research needed.

---

### Phase 2: Risk Management Foundation

**Rationale:** Risk controls must be built before any trading code exists. PITFALLS.md is explicit: "Risk management is Phase 1, not Phase 3." Circuit breakers, position sizing, PDT tracking, and the `PreToolUse` safety hook must be in place before order execution is possible. Building this phase second ensures no trading code is ever written without a safety layer to plug into.

**Delivers:** `risk-manager` agent; `PreToolUse` hook (`trade-safety-check.sh`); Python risk manager module (position sizing as % equity, daily loss circuit breaker, max concurrent positions, max position size per ticker, PDT rolling counter); stop-loss enforcement pattern (every order requires a bracket or explicit stop).

**Addresses:** Daily loss circuit breaker, position sizing, PDT rule awareness, maximum position limits.

**Avoids:** Pitfall 3 (runaway bot), Pitfall 1 (PDT lockout), Pitfall 7 (orders without stops).

**Research flag:** Standard patterns for circuit breaker implementation. PDT counter logic is well-specified in PITFALLS.md.

---

### Phase 3: Core Trading Loop (Deterministic, Paper Mode)

**Rationale:** Build the full Market Scanner → Signal Generator → Risk Manager → Order Executor → Portfolio Tracker pipeline using deterministic Python rules (no Claude analysis yet). Validate the loop end-to-end in paper mode before adding complexity. FEATURES.md specifies one working strategy (momentum with RSI + MACD) as the v1 MVP; the architecture must be validated on this before expanding.

**Delivers:** Market Scanner (Alpaca REST polling, configurable watchlist); Signal Generator (RSI + MACD via `pandas-ta`, momentum strategy logic); Order Executor (market + bracket orders via `alpaca-py`, idempotency keys); Portfolio Tracker (SQLite trade history, P&L calculation); SQLite state store; crash recovery / startup reconciliation with Alpaca positions; `loguru` audit logging; graceful shutdown (SIGINT/SIGTERM handler).

**Addresses:** Market orders, bracket orders (stop-loss + take-profit), position sizing, market hours guard, trade logging, portfolio P&L tracking, graceful shutdown, error handling with retry.

**Avoids:** Pitfall 6 (ghost positions from network failure — idempotency keys + reconciliation), Pitfall 12 (crash recovery — SQLite state + startup reconciliation), Pitfall 13 (market session edge cases — `alpaca.get_clock()` + `/v2/calendar`), Pitfall 9 (API rate limits — batch requests, backoff on 429).

**Research flag:** Standard patterns for Alpaca REST order flow. Market scanner and signal generator patterns are well-documented. SQLite + state machine pattern is verified in ARCHITECTURE.md sources.

---

### Phase 4: `/build` Command and Generated Artifacts

**Rationale:** The `/build` command renders the Phase 3 trading logic into user-specific Python scripts via templates. This is separate from Phase 3 because the template system (rendering `config.json` values into Jinja2 templates) is distinct work from the runtime logic itself. `/build` is also where security patterns for generated files are enforced.

**Delivers:** Jinja2 (or string template) rendering of all Python modules from Phase 3; `config_loader.py` that reads config.json and environment variables; auto-generated `.env.template`, `.gitignore`, `requirements.txt`; optional cron entry or systemd unit file for standalone execution; no API keys in any generated file (env var references only).

**Addresses:** Configuration file, Alpaca API authentication pattern in generated code, secret management.

**Avoids:** Pitfall 11 (API key exposure in generated files — critical to get right in this phase).

**Research flag:** Standard template rendering. Security pattern is explicit in PITFALLS.md and STACK.md.

---

### Phase 5: `/run` Command and Claude Code Execution Mode

**Rationale:** With the deterministic loop validated and `/build` generating clean scripts, wire up the `/run` command to launch the loop in Claude Code mode using the `market-analyst` and `trade-executor` agents. This phase also adds the Alpaca MCP server integration that gives Claude real-time data access — the prerequisite for Claude-powered analysis in the next phase.

**Delivers:** `/run` command; `market-analyst` agent (reads Alpaca MCP data, applies trading-rules skill, generates analysis signals); `trade-executor` agent (submits orders via Alpaca MCP tools, gated by `PreToolUse` hook); dual-mode execution verified (Claude Code mode via agents and standalone mode via `main_loop.py`).

**Addresses:** Alpaca MCP integration, `/run` command, multi-agent plugin structure for execution.

**Avoids:** Anti-pattern of Claude directly submitting orders (market-analyst produces JSON, trade-executor submits only after risk-manager approval).

**Research flag:** The Claude Code agent orchestration pattern across multiple agents may benefit from a focused research-phase to nail down inter-agent communication flow. MCP tool integration with the `PreToolUse` hook needs verification.

---

### Phase 6: Claude-Powered Analysis and Enhanced Features (v1.x)

**Rationale:** With a validated deterministic loop, add Claude as the strategy-level reasoning layer. This is explicitly post-validation per FEATURES.md. Also add the v1.x features: trailing stops, ATR-based dynamic stop placement, additional strategies, PDT enforcement in the loop, end-of-day summary, event notifications.

**Delivers:** Claude analysis integration in Signal Generator (structured JSON prompt with Alpaca data → action/confidence/reasoning response); confidence threshold gating before risk manager evaluation; Claude call caching (per-session, not per-trade); token budget logging; trailing stop-loss orders; ATR-based stop placement; mean-reversion and breakout strategies; end-of-day P&L summary report; PDT counter enforcement (block 4th day trade in 5-day window); optional Slack/email webhook notifications.

**Addresses:** Claude-powered trade analysis, trailing stops, ATR stops, additional strategies, PDT rule awareness, end-of-day summary, notifications.

**Avoids:** Pitfall 4 (LLM latency per-trade — Claude called per-session not per-trade); Pitfall 5 (LLM hallucination — Alpaca data always injected, Claude never generates market data).

**Research flag:** Claude API prompt structure for structured JSON trading analysis is an area where a focused research-phase would add value. Token cost modeling for sustainable per-session analysis frequency needs validation.

---

### Phase Ordering Rationale

- Plugin foundation before runtime: The Claude Code plugin structure (manifest, commands, hooks, skills) must exist before any Python runtime can be wired up through it.
- Risk management before execution: Circuit breakers and position sizing are foundational constraints that every order must pass through; retrofitting them after the loop exists creates safety gaps.
- Deterministic loop before Claude analysis: Validating the loop with rule-based signals first isolates bugs in data plumbing from bugs in AI reasoning. FEATURES.md explicitly calls this out as the correct sequence.
- `/build` after loop logic: Template rendering is cleanest when the runtime logic is stable; generating templates from moving code creates version drift.
- Claude analysis last: This is the differentiator but not the foundation. A trading bot that executes reliable rule-based signals is useful; one that only works when Claude says something insightful is fragile.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5** (Claude Code agent orchestration): Inter-agent communication patterns for multi-agent Claude Code plugin execution are moderately documented but the specific pattern for market-analyst → risk-manager → trade-executor hand-off with PreToolUse hook interception needs validation against live plugin docs.
- **Phase 6** (Claude analysis prompt design): Structured JSON prompt design for trading signal analysis and token cost modeling for production frequency requires targeted research. The right prompt structure determines whether Claude analysis is cost-effective.

Phases with standard patterns (skip research-phase):
- **Phase 1** (plugin foundation): Claude Code plugin structure is extensively documented via official Anthropic docs. STACK.md sources are HIGH confidence.
- **Phase 2** (risk management): Circuit breaker and position sizing math are well-established. PDT rules are explicitly specified in PITFALLS.md with verified regulatory sources.
- **Phase 3** (trading loop): Alpaca REST order flow, `alpaca-py` SDK usage, and SQLite state persistence are fully documented and HIGH confidence.
- **Phase 4** (`/build` template rendering): Standard Python template rendering with well-defined security requirements. No research needed.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core libraries verified via PyPI, official Alpaca docs, and official Claude Code plugin docs. Version requirements (Python 3.12+, alpaca-py 0.43.2, pandas-ta 0.4.71b0 beta, APScheduler 3.x) are confirmed against actual package pages. |
| Features | HIGH | Table stakes features match industry norms verified via competitor analysis. Differentiators (Claude analysis, code generation) are validated via real Claude Code plugin examples. Anti-features are well-reasoned with clear rationale. |
| Architecture | HIGH (plugin layer), MEDIUM (runtime patterns) | Claude Code plugin structure is from official documentation. The Market Scanner → Signal Generator → Risk Manager → Order Executor → Portfolio Tracker pattern is verified via multiple independent trading bot architecture sources. Specific inter-agent communication within plugin agents has MEDIUM confidence. |
| Pitfalls | HIGH | PDT rules sourced from Alpaca and FINRA directly. Circuit breaker and security pitfalls are cross-verified across multiple authoritative sources. LLM-specific pitfalls (hallucination, latency) are verified with recent 2025-2026 sources. |

**Overall confidence:** HIGH

### Gaps to Address

- **Inter-agent communication pattern in Claude Code plugins:** How exactly do multiple plugin agents hand off context (e.g., market-analyst passes analysis JSON to trade-executor) needs validation during Phase 5 planning. The plugin docs describe individual agents but not agent-to-agent invocation patterns in depth.
- **Claude API cost modeling for production:** The PITFALLS.md estimate of $0.01-0.10 per analysis call is a range, not a verified model. Before Phase 6, define the exact prompt size, response size, and call frequency to produce a monthly cost projection. This informs whether the feature is economically viable at the user's trading frequency.
- **Wash sale rule implementation complexity:** PITFALLS.md notes wash sale as a critical issue but the MVP guidance only requires a warning log. Determine during Phase 3 planning whether a 31-day re-entry block is included in v1 or deferred.
- **APScheduler 3.x vs. asyncio event loop compatibility:** The Alpaca WebSocket streams use asyncio. APScheduler 3.x has async support but the interaction between APScheduler's async scheduler and alpaca-py's async WebSocket client needs validation during Phase 3 planning.

---

## Sources

### Primary (HIGH confidence)
- [alpaca-py GitHub](https://github.com/alpacahq/alpaca-py) — SDK version, client classes, pydantic v2, paper vs live mode
- [Alpaca MCP Server GitHub](https://github.com/alpacahq/alpaca-mcp-server) — official MCP server, 43 tools, uvx installation
- [Alpaca MCP Server docs](https://docs.alpaca.markets/docs/alpaca-mcp-server) — Claude Code integration confirmed
- [pandas-ta PyPI](https://pypi.org/project/pandas-ta/) — version 0.4.71b0, Python 3.12+ requirement
- [Claude Code Plugins Reference](https://code.claude.com/docs/en/plugins-reference) — full plugin schema, hooks, skills, MCP config
- [Claude Code Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) — marketplace.json, GitHub hosting
- [Alpaca PDT Rule Support](https://alpaca.markets/support/what-is-the-pattern-day-trading-pdt-rule) — PDT rules and enforcement
- [FINRA SR-FINRA-2025-017](https://www.federalregister.gov/documents/2026/01/14/2026-00519/) — PDT rule change filing status
- [Alpaca API Rate Limits](https://alpaca.markets/support/usage-limit-api-calls) — 200 req/min confirmed
- [Alpaca Paper Trading Docs](https://docs.alpaca.markets/docs/paper-trading) — paper vs live behavior differences

### Secondary (MEDIUM confidence)
- [Stock Trading Bot Architecture (Medium)](https://medium.com/@halljames9963/stock-trading-bot-architecture-core-components-explained-d46f5d77c019) — component breakdown pattern
- [Building AI Trading Chatbot with Alpaca MCP (FlowHunt)](https://www.flowhunt.io/blog/building-ai-trading-chatbot-alpaca-mcp/) — MCP integration data flow
- [Alpaca Algorithmic Trading Python (official)](https://alpaca.markets/learn/algorithmic-trading-python-alpaca) — REST client initialization, order types
- [APScheduler 3.x docs](https://apscheduler.readthedocs.io/) — cron trigger, timezone support, async mode
- [StockBrokers.com — AI Trading Bots 2026](https://www.stockbrokers.com/guides/ai-stock-trading-bots) — competitor feature analysis
- [Why Most Trading Bots Lose Money (ForTraders)](https://www.fortraders.com/blog/trading-bots-lose-money) — common failure patterns

### Tertiary (cited for specific facts)
- [Wash Sale Rule Algo Trading (terms.law)](https://terms.law/Trading-Legal/guides/wash-sale-algo-trading.html) — wash sale applicability to bots
- [LLM Token Costs and Latency (Stevens Online)](https://online.stevens.edu/blog/hidden-economics-ai-agents-token-costs-latency/) — cost per call estimates
- [DEV Community — Building AI Trading Bot with Claude Code](https://dev.to/ji_ai/building-an-ai-trading-bot-with-claude-code-14-sessions-961-tool-calls-4o0n) — real-world plugin build reference

---
*Research completed: 2026-03-21*
*Ready for roadmap: yes*
