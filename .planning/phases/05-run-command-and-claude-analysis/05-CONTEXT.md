# Phase 5: Run Command and Claude Analysis - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the `/run` command that starts the autonomous trading loop via Claude Code agents. Claude acts as a strategy-level reasoning layer — analyzing trade opportunities from MarketScanner output and returning structured JSON recommendations (action, confidence, reasoning). Claude never submits orders directly; all recommendations pass through the deterministic Python risk manager. Every decision is audit-logged with full reasoning.

**Key change from original scope:** ALP-04 (MCP server) was dropped. Claude accesses market data through MarketScanner's Python output (indicator DataFrames), not via MCP tools. Success criteria #2 is adjusted accordingly.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure phase. The agent definitions (market-analyst, trade-executor) already exist from Phase 3. This phase wires them into the /run command and adds Claude's analysis prompt with structured JSON output.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agents/market-analyst.md` — Market scanning agent definition (Phase 3)
- `agents/trade-executor.md` — Trade execution agent definition (Phase 3)
- `scripts/bot.py` — Main bot loop with APScheduler (Phase 3)
- `scripts/market_scanner.py` — MarketScanner with 6 indicators
- `scripts/order_executor.py` — OrderExecutor routing through RiskManager
- `scripts/risk_manager.py` — RiskManager with all safety checks
- `scripts/portfolio_tracker.py` — Trade logging with loguru
- `scripts/strategies/` — 4 strategy modules
- `skills/trading-rules/SKILL.md` — Auto-loaded domain context for Claude
- `commands/build.md` — Build command pattern to follow for /run

### Established Patterns
- Commands are markdown files in `commands/` with YAML frontmatter
- Agents defined in `agents/` with model, tools, description
- Claude operates as analyst only — never executes orders directly (AI-03)
- All orders route through RiskManager.submit_with_retry()

### Integration Points
- `/run` command triggers bot.py or agent-based execution
- Claude's JSON recommendations feed into OrderExecutor.execute_signal()
- Audit log via loguru with trade=True binding
- Config determines agent mode vs standalone mode (CMD-11)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
