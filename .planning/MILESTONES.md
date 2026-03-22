# Milestones

## v1.0 Trading Bot Plugin MVP (Shipped: 2026-03-22)

**Phases completed:** 6 phases, 16 plans, 26 tasks

**Key accomplishments:**

- Claude Code plugin scaffold with SHA256-gated uv dependency installer, alpaca-py 0.43.2 pinned in requirements.txt, and 19-test pytest suite covering hook logic and manifest structure
- Auto-loaded trading-rules skill, 4-strategy reference suite with ATR/PDT/circuit-breaker risk rules, alpaca-py SDK patterns, and 26 config/env schema tests defining the wizard contract
- 183-line wizard command that adapts to beginner/intermediate/expert experience levels, captures all 7 preference categories, and writes config.json + .env template to CLAUDE_PLUGIN_DATA
- RiskManager class with circuit breaker, PDT tracking, position sizing with claude_decides clamping, and ghost-position-safe retry — 24 unit tests all green
- PreToolUse bash hook intercepting order-submission commands via flag-file checks, plus risk-manager agent with model: sonnet and 11 structural tests covering PLUG-03 and PLUG-07
- One-liner:
- OrderExecutor class wrapping 4 Alpaca order types with ATR-based bracket stops, routed through RiskManager.submit_with_retry(), plus market-analyst and trade-executor Claude Code agent definitions
- SQLite StateStore with WAL mode, full CRUD for 4 tables, 3-case crash recovery via Alpaca reconciliation, and one-shot pdt_trades.json migration to SQLite
- Four pluggable trading strategies (momentum, mean reversion, breakout, VWAP) implemented as BaseStrategy ABC subclasses, registered by config name in STRATEGY_REGISTRY, returning Signal dataclasses with programmatically derived indicator column names
- APScheduler trading loop with PortfolioTracker dual-sink trade logging (loguru NDJSON + SQLite), graceful SIGINT/SIGTERM shutdown that closes all Alpaca positions, and RiskManager PDT delegation to SQLite
- Config-driven standalone bot generator with strategy filtering and import rewriting — /build produces a self-contained directory ready to run on any server
- generate_build() extended to produce .env.template, .gitignore, requirements.txt, run.sh, and DEPLOY.md — complete standalone deployment package with cron/systemd instructions and explicit secret-hygiene enforcement
- ClaudeAnalyzer prompt-builder/response-parser and /run command with dual agent+standalone modes, all signals gated by Python RiskManager
- NDJSON AuditLogger + bot.py agent-mode helpers wiring ClaudeRecommendation through risk-manager before every Alpaca order
- EODReportGenerator (scripts/eod_report.py)

---
