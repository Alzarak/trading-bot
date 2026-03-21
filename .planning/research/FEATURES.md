# Feature Research

**Domain:** Automated stock day trading Claude Code plugin (Alpaca API, Python)
**Researched:** 2026-03-21
**Confidence:** HIGH (core trading features), MEDIUM (Claude-specific integration patterns)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features every trading bot must have. Missing these = users consider it broken or unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Paper trading mode | Industry standard for testing before risking real money; Alpaca provides this free | LOW | Alpaca has separate paper/live endpoints; switch via config flag |
| Live trading mode | Core product purpose; paper-only is a toy | LOW | Same code, different Alpaca credentials |
| Market orders | Simplest order type; required for fast day trading exits | LOW | Alpaca SDK: `submit_order(side, qty, type='market')` |
| Limit orders | Required for controlled entry price; pure market orders bleed on slippage | LOW | Standard Alpaca order parameter |
| Stop-loss orders | Non-negotiable safety floor; any bot without this is reckless | MEDIUM | Can be bracket order or separate stop order submitted at entry |
| Take-profit orders | Symmetric to stop-loss; bots need automated exits on both sides | MEDIUM | Bracket orders combine stop-loss + take-profit in one API call |
| Position sizing (% of equity) | Prevents any single trade from wiping the account | MEDIUM | Calculate: `shares = (equity * risk_pct) / entry_price` |
| Daily loss circuit breaker | Halts trading when daily drawdown exceeds threshold; prevents runaway losses | MEDIUM | Compare start-of-day equity to current equity; pause loop if breach |
| Trade logging (file-based) | Users need to see what the bot did; essential for debugging | LOW | Append to CSV or SQLite; timestamp, ticker, action, price, P&L |
| Portfolio P&L tracking | Users need to know if the bot is working; daily/total return | LOW | Alpaca account endpoint provides equity, buying power, unrealized P&L |
| Market hours awareness | Day trading only happens 9:30am–4:00pm ET; bot must not trade pre/post | LOW | Check `alpaca.get_clock()` before each loop iteration |
| Graceful shutdown | Positions must be closed or bot must exit cleanly on interrupt | MEDIUM | Handle SIGINT/SIGTERM; close all positions or log open ones |
| Error handling and retry | API calls fail; network hiccups happen; silent failures cause stuck positions | MEDIUM | Wrap all API calls with exponential backoff, max retries, logging |
| Configuration file | All parameters (risk, budget, tickers) must be editable without code changes | LOW | JSON or YAML config; loaded at startup |
| Alpaca API authentication | Core integration; must support both paper and live keys | LOW | Environment variables for API keys; never hardcode |

### Differentiators (Competitive Advantage)

Features that set this plugin apart from generic trading scripts. Aligned with the Claude Code angle.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Claude-powered trade analysis | LLM evaluates each signal for context (news, price action, broader market) before executing; human-like judgment without a human | HIGH | Claude reads market data via Alpaca MCP server and decides per-opportunity aggression level; key differentiator vs dumb rule-based bots |
| Interactive `/initialize` command | Guided setup that adapts to beginner vs expert; generates all config and infrastructure from answers | HIGH | Multi-turn dialogue; extracts risk tolerance, budget, tickers, strategies, autonomy level; outputs complete config |
| `/build` command that generates scripts | Plugin generates the trading Python files from initialize context; users don't write code | HIGH | Claude Code generates tailored scripts; can regenerate if preferences change |
| Autonomous aggression adjustment | Claude dynamically adjusts how aggressive to be based on current market conditions, recent performance, and volatility | HIGH | Expert mode: Claude decides position sizes and entry thresholds per trade, not just fixed rules |
| Beginner / expert mode toggle | Beginner: conservative defaults, explanatory logs, extra confirmations; Expert: full control, no hand-holding | MEDIUM | Single config flag that controls verbosity, defaults, and safety guardrails |
| Alpaca MCP server integration | Real-time market data accessible inside Claude's context window during analysis; no manual data piping | MEDIUM | Alpaca has official MCP server; Claude can query prices, positions, news directly during reasoning |
| Multi-agent plugin structure | Separate agents for market scanning, risk management, and trade execution with clear boundaries | HIGH | Follows Claude Code plugin conventions; each agent has narrow, auditable responsibility |
| Trailing stop-loss | Locks in profits as price moves favorably; standard stop-loss gives back too much on winners | MEDIUM | Alpaca supports trailing stop as native order type |
| ATR-based dynamic stop placement | Stop distance scales with volatility; tight stops in calm markets, wider in volatile | MEDIUM | Use `ta` library: `ATR(high, low, close, period=14)` |
| Notification on key events | Slack/email alert when circuit breaker fires, daily summary, large win/loss | MEDIUM | Webhook-based; fire on stop events, end-of-day P&L summary |
| Standalone server mode | Can be extracted from Claude Code and run as a cron job on a VPS | MEDIUM | Separate entrypoint that runs the loop without Claude Code context |
| PDT rule awareness | Warns beginner users approaching 4-trade-per-5-day limit if under $25k equity | LOW | FINRA PDT rule is pending change (FINRA SR-2025-017 awaiting SEC approval as of March 2026) but still active; track day trade count |
| Technical indicator library | RSI, MACD, EMA, Bollinger Bands, VWAP implemented and selectable via config | MEDIUM | Use `pandas-ta` or `ta-lib`; indicators computed on bar data from Alpaca |
| Strategy selection at initialize | Choose from momentum, mean reversion, breakout, or VWAP reversion during setup | MEDIUM | Each strategy is a configurable module; user picks one or more at setup time |
| End-of-day summary report | Daily P&L, trades taken, win rate, biggest winner/loser; written to file | LOW | Run at 4:00pm ET after market close; parse trade log |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good on the surface but create serious problems for this project.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Backtesting engine | "Test before risking money" — obvious appeal | Implementing correct backtesting (slippage, fills, bid/ask spread, bar timing) is a full product in itself; bad backtests give false confidence and are worse than no backtest | Paper trading mode on Alpaca is the honest equivalent; forward-test in paper before going live |
| Web dashboard / UI | Visual P&L charts look impressive | Adds a full web server, frontend framework, auth layer to scope; this is a CLI plugin, not a SaaS product | Write end-of-day summary to a log file; use Alpaca's built-in web dashboard for portfolio visualization |
| Real-time streaming WebSocket data | Lower latency than polling | Adds WebSocket connection management, reconnect logic, message queuing; for day trading 1-min bars, REST polling is sufficient and far simpler | Poll Alpaca REST API on each loop iteration; 1-min bars are adequate for the strategies in scope |
| Multiple broker support | "What if Alpaca goes down?" | Each broker has different APIs, order types, fill behavior; multi-broker abstractions leak everywhere; doubles testing surface | Alpaca is the chosen broker for v1; the project spec says so explicitly |
| Options trading | Higher leverage, more profit potential | Options pricing, Greeks, expiry management, and margin requirements are a fundamentally different domain; complexity would swamp the project | Stocks only for v1 as stated in project scope |
| Leverage / margin trading | Amplify returns | Margin calls can liquidate entire account; beginners should never touch this; it contradicts the "safe to run unattended" constraint | Position sizing (1–3% equity per trade) achieves risk control without leverage |
| Crypto trading | 24/7 markets, more volatility | Out of scope per project spec; crypto APIs differ meaningfully; PDT rules don't apply creating different risk profile | Alpaca supports crypto via a separate API; can be v2 addition |
| Full autonomous ML model training | "Self-improving bot" | Training ML models correctly requires datasets, validation pipelines, overfitting prevention; Claude's LLM judgment is the differentiator, not a custom model | Use Claude for contextual analysis; use fixed, well-understood technical indicators for signal generation |
| Social / copy trading | Strategy sharing among users | Privacy and regulatory complexity (investment advice laws); requires user accounts, a backend, moderation | Focus on single-user autonomous operation; users can share their config files manually |
| Sentiment from social media (Reddit/Twitter) | "Retail sentiment signals" | Social sentiment APIs are expensive or unreliable; retail crowd behavior has low predictive value for single-day trades; adds significant dependency chain | News sentiment via Alpaca's built-in news endpoint is sufficient and already in the API |

---

## Feature Dependencies

```
[/initialize command]
    └──generates──> [Config file]
                        └──required by──> [/build command]
                                              └──generates──> [Python trading scripts]
                                                                  └──required by──> [/run command]

[Alpaca API authentication]
    └──required by──> [Paper trading mode]
    └──required by──> [Live trading mode]
    └──required by──> [Portfolio P&L tracking]
    └──required by──> [Market hours awareness]

[Market orders]
    └──required by──> [Autonomous trading loop]

[Position sizing]
    └──required by──> [Stop-loss orders] (stop distance derived from position size)
    └──required by──> [Daily loss circuit breaker] (breach calculated as % of equity)

[Trade logging]
    └──required by──> [End-of-day summary report]
    └──required by──> [PDT rule awareness] (must count day trades)

[Technical indicator library]
    └──required by──> [Strategy selection] (strategies compute their own signals)
    └──enhances──> [Claude-powered trade analysis] (indicators feed Claude's context)

[Alpaca MCP server integration]
    └──enhances──> [Claude-powered trade analysis] (real-time data in Claude's context)

[Standalone server mode] ──conflicts──> [Claude Code plugin mode]
    (same loop, different entrypoints — must be designed for both from the start)

[Autonomous aggression adjustment] ──requires──> [Claude-powered trade analysis]
    (aggression logic lives inside Claude's per-trade reasoning)
```

### Dependency Notes

- **/initialize requires Config file output:** The initialize command is the source of truth; everything downstream reads from that config. If initialize is broken, nothing else works.
- **Position sizing requires equity data:** Alpaca account endpoint must be queried at the start of each trading session to get current equity before sizing can be calculated.
- **Claude analysis requires Alpaca MCP:** Without the MCP server, Claude cannot query live market data in-context, falling back to stale training data. MCP integration is a prerequisite for the core differentiator.
- **Standalone mode conflicts with plugin mode:** They share the trading loop code but have different entrypoints. Design the loop as a standalone Python module that the plugin wraps — do not let Claude Code plugin scaffolding bleed into the trading logic.
- **PDT tracking requires trade log:** The bot must count day trades from the log (or from Alpaca's order history API) to warn users approaching the PDT threshold.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] `/initialize` command — captures user preferences, generates config file; the entire plugin is useless without this
- [ ] `/build` command — generates Python trading scripts from config; core value delivery
- [ ] `/run` command — starts the autonomous loop; what users are here for
- [ ] Alpaca authentication (paper + live) — must support both from day one; paper mode is how users test safely
- [ ] Market orders + bracket orders (stop-loss + take-profit in one call) — minimum viable order management
- [ ] Position sizing (% of equity per trade) — non-negotiable safety baseline
- [ ] Daily loss circuit breaker — must not run unattended without a kill switch
- [ ] Market hours guard — must not attempt orders when market is closed
- [ ] Trade logging to file — users must be able to see what happened
- [ ] Portfolio P&L tracking — users must see daily/total return
- [ ] Graceful shutdown — must close or log open positions on exit
- [ ] RSI + MACD technical indicators — sufficient for 2 of the most common strategies
- [ ] Momentum strategy (one working strategy) — validate the loop before adding more
- [ ] Error handling and retry on API calls — required for unattended operation
- [ ] Beginner / expert mode in config — core user segmentation from project requirements

### Add After Validation (v1.x)

Features to add once the core loop is working and validated in paper mode.

- [ ] Trailing stop-loss — add after bracket orders are proven stable; meaningfully improves exits
- [ ] ATR-based dynamic stop placement — upgrade from fixed-percentage stops after first strategy is live
- [ ] Additional strategies (mean reversion, breakout, VWAP) — expand menu once one strategy is running cleanly
- [ ] Alpaca MCP server integration — enables Claude in-context market analysis; adds the key differentiator after baseline loop works
- [ ] Claude-powered trade analysis — requires MCP integration; upgrade from pure rule-based to LLM-judged signals
- [ ] End-of-day summary report — valuable but not blocking; add after logging is stable
- [ ] PDT rule awareness — warning system for users under $25k equity; important but not a launch blocker
- [ ] Notification on key events — Slack/email alerts; useful for unattended operation reassurance

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Autonomous aggression adjustment — requires Claude analysis to be stable first; complex to tune safely
- [ ] Standalone server mode (VPS/cron entrypoint) — defer until plugin mode is validated; extraction is straightforward once logic is clean
- [ ] News sentiment via Alpaca news endpoint — meaningful signal enhancement but adds complexity; validate strategy profitability first
- [ ] Multi-agent plugin structure (separate scanner/risk/execution agents) — architectural improvement; implement once single-agent loop is proven
- [ ] Additional technical indicators (Bollinger Bands, VWAP, ADX) — expand after core indicators are battle-tested
- [ ] Crypto trading via Alpaca — out of scope for v1 per project spec

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `/initialize` command | HIGH | HIGH | P1 |
| `/build` command | HIGH | HIGH | P1 |
| `/run` command | HIGH | MEDIUM | P1 |
| Alpaca auth (paper + live) | HIGH | LOW | P1 |
| Market + bracket orders | HIGH | LOW | P1 |
| Position sizing | HIGH | LOW | P1 |
| Daily loss circuit breaker | HIGH | LOW | P1 |
| Market hours guard | HIGH | LOW | P1 |
| Trade logging | HIGH | LOW | P1 |
| Error handling + retry | HIGH | MEDIUM | P1 |
| Beginner/expert mode | HIGH | MEDIUM | P1 |
| RSI + MACD indicators | HIGH | MEDIUM | P1 |
| Momentum strategy | HIGH | MEDIUM | P1 |
| Portfolio P&L tracking | HIGH | LOW | P1 |
| Trailing stop-loss | MEDIUM | LOW | P2 |
| ATR-based stops | MEDIUM | MEDIUM | P2 |
| Additional strategies | MEDIUM | MEDIUM | P2 |
| Alpaca MCP integration | HIGH | MEDIUM | P2 |
| Claude trade analysis | HIGH | HIGH | P2 |
| End-of-day summary | MEDIUM | LOW | P2 |
| PDT rule awareness | MEDIUM | LOW | P2 |
| Notifications (Slack/email) | MEDIUM | MEDIUM | P2 |
| Autonomous aggression | HIGH | HIGH | P3 |
| Standalone server mode | MEDIUM | MEDIUM | P3 |
| News sentiment | MEDIUM | HIGH | P3 |
| Multi-agent structure | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | 3Commas / TradingView Bots | StockHero / Trade Ideas | Our Approach |
|---------|----------------------------|-------------------------|--------------|
| Setup experience | Web UI wizard | Web UI, strategy templates | Claude Code `/initialize` — conversational, adaptive to user skill level |
| Code generation | No — closed platform | No — black box | Yes — generates Python scripts users can inspect, modify, and run independently |
| LLM analysis | Rule-based only (no LLM) | AI signal generation, opaque | Claude reasons explicitly per trade; reasoning is inspectable in logs |
| Paper trading | Yes, most platforms | Yes | Yes via Alpaca native paper mode |
| Broker lock-in | Platform-specific | Platform-specific | Alpaca-specific for v1; Alpaca is free with no commissions |
| Position on risk | User-configurable parameters | Preset templates | Adaptive: beginner gets conservative defaults; expert gets full control |
| Distribution | SaaS subscription | SaaS subscription | Open plugin, free, runs in user's own Claude Code |
| Strategy customization | Visual rule builder | Limited | Full Python access; experts can modify generated code directly |
| Extensibility | Closed | Closed | Plugin marketplace; other developers can extend |

---

## Regulatory Note

**PDT Rule Status (March 2026):** FINRA filed SR-FINRA-2025-017 in December 2025 to replace the $25,000 pattern day trader minimum equity requirement with a risk-based intraday margin system. SEC approval is pending as of March 2026. The existing $25,000 minimum remains in force. The bot should:
1. Warn users with under $25k equity that they are subject to PDT limits (max 3 day trades per 5 business days)
2. Optionally track day trade count and refuse a 4th day trade in the window if in beginner mode
3. Recommend paper trading for users who cannot meet the $25k threshold

---

## Sources

- [StockBrokers.com — Best AI Stock Trading Bots 2026](https://www.stockbrokers.com/guides/ai-stock-trading-bots)
- [3Commas — AI Trading Bot Risk Management Guide 2025](https://3commas.io/blog/ai-trading-bot-risk-management-guide-2025)
- [Alpaca — Free RSI and MACD Trading Bot with ChatGPT](https://alpaca.markets/learn/free-rsi-and-macd-trading-bot-with-chatgpt-and-alpaca)
- [QuantVPS — Top 20 Trading Bot Strategies for 2026](https://www.quantvps.com/blog/trading-bot-strategies)
- [For Traders — Why Most Trading Bots Lose Money](https://www.fortraders.com/blog/trading-bots-lose-money)
- [FINRA — Notice of Filing SR-FINRA-2025-017 (PDT Rule Change)](https://www.federalregister.gov/documents/2026/01/14/2026-00519/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-of-a)
- [StockEducation.com — Pattern Day Trading Canonical Guide 2026](https://www.stockeducation.com/pattern-day-trading/)
- [DEV Community — Building an AI Trading Bot with Claude Code](https://dev.to/ji_ai/building-an-ai-trading-bot-with-claude-code-14-sessions-961-tool-calls-4o0n)
- [Alpaca GitHub — Official MCP Server](https://github.com/alpacahq/alpaca-mcp-server)
- [Mindful Markets — AI in Trading 2026: Claude Code and Agent-Led Markets](https://www.mindfulmarkets.ai/ai-in-trading-2026-claude-code-and-the-rise-of-agent-led-markets/)

---
*Feature research for: automated stock day trading Claude Code plugin*
*Researched: 2026-03-21*
