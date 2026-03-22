# Trading Bot Plugin

## What This Is

A Claude Code plugin that automates stock day trading on US markets. Users run `/initialize` to configure trading preferences (adapts to beginner through expert), `/build` to generate standalone Python trading scripts, and `/run` to start an autonomous trading loop. The bot scans markets, computes technical indicators, applies configurable strategies, and executes trades via the Alpaca API — with Claude as an optional strategy-level analyst and a full risk management safety layer.

## Core Value

After initial setup, the bot trades autonomously without human intervention — scanning markets, making decisions (using Claude for analysis), and executing trades on a loop.

## Requirements

### Validated

- ✓ Interactive `/initialize` command with beginner/intermediate/expert adaptation — v1.0
- ✓ Autonomous risk mode where Claude analyzes trades and recommends actions — v1.0
- ✓ `/build` command generating standalone Python scripts from config — v1.0
- ✓ `/run` command starting the autonomous trading loop (agent + standalone modes) — v1.0
- ✓ Alpaca API integration for paper and live trading — v1.0
- ✓ Full plugin structure: 3 agents, 1 skill, 3 commands, 2 hooks, 3 reference files — v1.0
- ✓ Beginner-friendly (conservative defaults, guided) and expert (full control) modes — v1.0
- ✓ Loop-based autonomous execution via APScheduler with market hours enforcement — v1.0
- ✓ Standalone Python scripts runnable on VPS/server with cron/systemd — v1.0
- ✓ Publishable to Claude Code plugin marketplace — v1.0
- ✓ Circuit breaker, PDT tracking, position sizing, ghost position prevention — v1.0
- ✓ 4 strategies: momentum, mean reversion, breakout, VWAP — v1.0
- ✓ SQLite state persistence with crash recovery — v1.0
- ✓ End-of-day reports and Slack webhook notifications — v1.0

### Active

(None — next milestone TBD)

### Out of Scope

- Cryptocurrency trading — stocks only for v1
- Options trading — complexity too high for initial release
- Mobile app or web dashboard — CLI/Claude Code only
- Custom broker integrations — Alpaca only for v1
- Backtesting engine — defer to v2
- Alpaca MCP server — dropped in v1.0 (SDK-only approach chosen)

## Context

Shipped v1.0 with 4,512 LOC Python across 15 modules + 312 automated tests.
Tech stack: alpaca-py 0.43.2, pandas-ta 0.4.71b0, APScheduler 3.x, SQLite, loguru, pydantic-settings.
Plugin structure: 3 commands, 3 agents, 1 skill, 2 hooks (SessionStart + PreToolUse), 3 reference files.
All deployed in a single session on 2026-03-22.

Known tech debt:
- `/initialize` doesn't prompt for Slack webhook URL (notifications require manual config edit)
- `autonomy_mode` config field is informational — no runtime branching
- Email notification channel is a stub
- marketplace.json has placeholder GitHub repository URL

## Constraints

- **API**: Alpaca Markets API — free tier, paper trading support required
- **Language**: Python for trading scripts, standard Claude Code plugin structure for the plugin itself
- **Platform**: Must work on Linux, compatible with Claude Code plugin system
- **Marketplace**: Must follow plugin marketplace conventions for publishing
- **Autonomy**: Must be safe to run unattended — proper error handling, position limits, circuit breakers

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Alpaca API | Free, paper trading built-in, well-documented | ✓ Good — clean SDK, paper mode worked seamlessly |
| Drop MCP server (ALP-04) | SDK-only simplifies stack, Claude reads script output instead | ✓ Good — fewer moving parts, no MCP dependency |
| All preferences via /initialize | Plugin works for beginners and experts — no hardcoded assumptions | ✓ Good — 3-level adaptation works well |
| Python for trading logic | Industry standard for financial automation, rich library ecosystem | ✓ Good — pandas-ta, alpaca-py, APScheduler all solid |
| Plugin marketplace distribution | Publishable and usable by others | ✓ Good — valid manifest and marketplace.json |
| pandas-ta over TA-Lib | No C compiler needed for plugin users | ✓ Good — pip-installable, all 6 indicators work |
| Claude as analyst only | Safety — Claude never submits orders directly | ✓ Good — structural safety via type system |
| SQLite for state | Lightweight, no infrastructure, crash recovery via WAL | ✓ Good — reconciliation works cleanly |

---
*Last updated: 2026-03-22 after v1.0 milestone*
