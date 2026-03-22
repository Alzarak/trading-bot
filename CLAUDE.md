## Project

**Trading Bot Plugin**

A Claude Code plugin that automates stock day trading on US markets. Interactive setup adapts to any user — from beginners to experts — then generates and runs autonomous trading infrastructure using the Alpaca API.

**Core Value:** After initial setup, the bot trades autonomously — scanning markets, making decisions (using Claude for analysis), and executing trades on a loop.

### Constraints

- **API**: Alpaca Markets API — free tier, paper trading support required
- **Language**: Python 3.12+ for trading scripts, standard Claude Code plugin structure
- **SDK**: alpaca-py 0.43.2 (not deprecated alpaca-trade-api)
- **Indicators**: pandas-ta 0.4.71b0 (pure Python, no C compiler needed)
- **Platform**: Linux, compatible with Claude Code plugin system
- **Autonomy**: Safe to run unattended — error handling, position limits, circuit breakers
- **Keys**: Never hardcode API keys — use pydantic-settings + .env

### Architecture

```
Market Data → MarketScanner → Technical Indicators → Claude Analysis
  → RiskManager (circuit breaker, PDT, position sizing) → OrderExecutor → Alpaca
```

**Key invariant:** Claude never submits orders directly. All recommendations route through deterministic Python risk checks.

### References

Detailed documentation in `references/`:
- `tech-stack.md` — Full technology stack, versions, alternatives, compatibility
- `trading-strategies.md` — Strategy logic, parameters, entry/exit conditions
- `risk-rules.md` — Risk management rules, circuit breaker, PDT, position sizing
- `alpaca-api-patterns.md` — Copy-paste Alpaca API code patterns

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
