# Phase 4: Build Command - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the `/build` command that reads the user's `config.json` (produced by `/initialize`) and generates a complete, standalone set of Python trading scripts tailored to their selected strategies and preferences. Generated scripts load API keys from environment variables only — no secrets in generated files. Includes `.gitignore` generation and standalone server deployment artifacts (cron/systemd instructions).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure phase. The build command generates files from existing config and Phase 3 modules.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/bot.py` — Main bot entry point (Phase 3) — the template for generated standalone scripts
- `scripts/market_scanner.py` — MarketScanner module
- `scripts/order_executor.py` — OrderExecutor module
- `scripts/risk_manager.py` — RiskManager module
- `scripts/state_store.py` — StateStore module
- `scripts/portfolio_tracker.py` — PortfolioTracker module
- `scripts/strategies/` — 4 strategy modules with STRATEGY_REGISTRY
- `scripts/types.py` — Signal dataclass
- `requirements.txt` — Python dependencies
- `commands/initialize.md` — Initialize wizard that produces config.json

### Established Patterns
- Commands are markdown files in `commands/` with YAML frontmatter
- Config stored as JSON in `${CLAUDE_PLUGIN_DATA}/config.json`
- API keys in `.env` file loaded by pydantic-settings
- All Python scripts use alpaca-py SDK

### Integration Points
- `${CLAUDE_PLUGIN_DATA}/config.json` — input for build command
- Generated output directory for standalone scripts
- `.env.template` for API key placeholders
- `.gitignore` for secret exclusion

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
