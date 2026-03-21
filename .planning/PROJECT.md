# Trading Bot Plugin

## What This Is

A Claude Code plugin that automates stock day trading on US markets. It provides an interactive setup command that adapts to any user — from complete beginners to expert traders — then generates and runs autonomous trading infrastructure using the Alpaca API. The plugin leverages the full Claude Code plugin system: agents, skills, commands, reference files, and hooks.

## Core Value

After initial setup, the bot trades autonomously without human intervention — scanning markets, making decisions (using Claude for analysis), and executing trades on a loop.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Interactive `/initialize` command that walks users through trading preferences (risk tolerance, budget, paper vs live, autonomy level, strategies, market hours)
- [ ] Autonomous risk mode where Claude analyzes each trade opportunity and decides aggression based on context
- [ ] `/build` command that generates all Python scripts, configs, and infrastructure from initialize context
- [ ] `/run` command that starts the autonomous trading loop
- [ ] Alpaca API integration for both paper trading and live trading
- [ ] Alpaca MCP server integration for real-time market data access within Claude
- [ ] Full plugin structure: agents (for market analysis, trade execution, risk management), skills, commands, reference files, hooks
- [ ] Configurable for beginners (guided, conservative defaults) and experts (direct, full control)
- [ ] Loop-based autonomous execution after initial setup — no user interaction needed
- [ ] Option to run within Claude Code or as standalone Python scripts on a server/cron
- [ ] Publishable to the Claude Code plugin marketplace (~/projects)

### Out of Scope

- Cryptocurrency trading — stocks only for v1
- Options trading — complexity too high for initial release
- Mobile app or web dashboard — CLI/Claude Code only
- Custom broker integrations — Alpaca only for v1
- Backtesting engine — defer to v2

## Context

- User is new to trading; the plugin must handle all domain knowledge
- Other users (potentially expert traders) will install this from the marketplace
- Alpaca chosen for: free API, built-in paper trading, community MCP server, good documentation
- Plugin lives in its own repo under ~/projects, publishable to existing marketplace repo
- All user-specific preferences must flow through /initialize — nothing hardcoded
- The plugin-creator skill should be used for proper plugin structure

## Constraints

- **API**: Alpaca Markets API — free tier, paper trading support required
- **Language**: Python for trading scripts, standard Claude Code plugin structure for the plugin itself
- **Platform**: Must work on Linux, compatible with Claude Code plugin system
- **Marketplace**: Must follow plugin marketplace conventions for publishing
- **Autonomy**: Must be safe to run unattended — proper error handling, position limits, circuit breakers

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Alpaca API | Free, paper trading built-in, MCP server available, well-documented | — Pending |
| All preferences via /initialize | Plugin must work for beginners and experts — no hardcoded assumptions | — Pending |
| Python for trading logic | Industry standard for financial automation, rich library ecosystem | — Pending |
| Plugin marketplace distribution | User wants it publishable and usable by others | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-21 after initialization*
