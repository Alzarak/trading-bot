# Pitfalls Research

**Domain:** Automated stock day trading Claude Code plugin (Alpaca API)
**Researched:** 2026-03-21
**Confidence:** HIGH (multiple authoritative sources cross-verified)

---

## Critical Pitfalls

### Pitfall 1: PDT Rule Violation Causing 90-Day Trading Lockout

**What goes wrong:**
A bot executes 4+ day trades within a 5-business-day window in a margin account with less than $25,000 equity. Alpaca flags the account as a Pattern Day Trader (PDT), freezes all new positions, and restricts the account to closing transactions only for 90 days. The bot may not know it has been locked out and continues attempting orders that all get rejected with HTTP 403.

**Why it happens:**
The bot developer focused on strategy logic and didn't encode the PDT rule as a hard constraint. Day trades accumulate silently — the bot doesn't track its own trade count against the rolling 5-day window. A volatile session where the bot enters and exits 4+ positions in one day triggers the violation.

**How to avoid:**
- Maintain a rolling counter of day trades in the last 5 business days
- Halt new position entry when the count reaches 3 (not 4) as the safety margin
- At initialization, ask the user whether they have a margin account and their current equity — apply PDT mode only when equity is below $25,000
- Use a cash account for accounts under $25,000 (no PDT rule, but T+2 settlement applies)
- Alpaca's API returns HTTP 403 with a PDT-specific error on violation attempts — handle this explicitly, not as a generic error

**Warning signs:**
- HTTP 403 errors on order submission
- Account status returning `account_blocked: true` or `trading_blocked: true` in the Alpaca account endpoint
- Day trade count approaching 3 within a 5-day window in logs

**Phase to address:**
Phase building the core trading loop and order execution — must be a first-class constraint, not an afterthought.

---

### Pitfall 2: Wash Sale Rule Silently Destroying Tax Efficiency

**What goes wrong:**
The bot sells a stock at a loss then rebuts into a position in the same stock within 30 days (the 61-day wash sale window). The IRS disallows the loss deduction. An active bot executing many trades can trigger dozens of wash sales per month. The user sees "I lost $X this year" but owes taxes because all losses are disallowed. In extreme HFT cases, traders have gone bankrupt owing taxes larger than their actual gains.

**Why it happens:**
The bot has no concept of tax optimization — it only thinks in terms of strategy signals. A mean-reversion or momentum strategy will routinely sell a ticker at a loss and re-enter it minutes later when conditions change, which is a textbook wash sale.

**How to avoid:**
- Warn users explicitly during `/initialize` that the wash sale rule applies and the bot does not provide tax advice
- Add a configurable "wash sale avoidance" mode that tracks sold-at-loss positions and blocks re-entry for 31 days
- Surface this as a beginner-mode default (on) and expert-mode option (configurable)
- For MVP: at minimum, log a warning each time a loss position is closed so users can manually track it
- Mark-to-Market (MTM) election (Section 475(f)) eliminates wash sale tracking for traders who qualify — reference this in user documentation

**Warning signs:**
- Bot frequently re-entering positions immediately after a loss exit
- User's broker 1099-B showing large "wash sale disallowed" amounts

**Phase to address:**
The `/initialize` setup phase (user education) and the order execution phase (optional guard implementation).

---

### Pitfall 3: No Circuit Breakers — Runaway Bot Drains Account

**What goes wrong:**
A bug, bad market data, or an LLM hallucination causes the bot to enter a feedback loop of bad trades. Without a daily loss limit or drawdown circuit breaker, the bot continues trading until the account equity approaches zero. The user may be asleep, at work, or simply not watching.

**Why it happens:**
Developers focus on the "making money" path and treat loss limits as optional configuration. They test the happy path (strategy works), not the failure path (strategy enters a losing streak). The bot was designed to be autonomous — that autonomy becomes dangerous without kill switches.

**How to avoid:**
- Implement a hard daily loss limit (recommended: 3% of account equity) — when hit, halt all new order submission for the calendar day
- Implement a total drawdown circuit breaker (recommended: 10-15% of starting equity) — when hit, close all open positions and halt until manual restart
- Implement per-trade maximum loss as stop-loss on every order — never enter a position without a stop
- Implement maximum concurrent positions limit (e.g., 5 stocks at once)
- Implement maximum position size as a percentage of portfolio (e.g., 20% in any single ticker)
- Add a "volatility halt" — if VIX or implied volatility spikes above a threshold, pause new entries
- These must be non-configurable minimums in the code, with only more-restrictive user overrides allowed

**Warning signs:**
- Account equity declining more than 2% within a single session
- Rapid succession of orders in the same ticker
- Bot attempting to trade with account equity below a safe minimum

**Phase to address:**
Risk management is Phase 1, not Phase 3. Must be foundational infrastructure before any live trading is possible.

---

### Pitfall 4: LLM Latency Makes Claude Unusable for Entry/Exit Timing

**What goes wrong:**
The bot calls Claude to analyze a trade opportunity, waits 2-10 seconds for a response, then submits the order. By then, the price has moved, the opportunity is gone, or slippage has consumed the edge. At scale, Claude API costs accumulate: a bot making 50 analysis calls per day at ~$0.01-0.10/call adds up to $150-$1,500/month just in AI costs.

**Why it happens:**
Developers conceptualize Claude as "the brain that decides each trade" — calling it inline for every signal. This works in paper trading (no real execution timing pressure) but fails in live trading where seconds matter for day trading.

**How to avoid:**
- Use Claude for strategy-level decisions, not per-trade execution decisions
  - GOOD: "Analyze the overall market context for today and tell me which of my configured strategies to favor"
  - GOOD: "Review today's P&L and tell me if my risk parameters should be adjusted"
  - BAD: "Should I buy AAPL right now at $182.34?"
- Use deterministic Python rule execution for per-trade entry/exit signals (moving averages, RSI thresholds, etc.)
- Reserve Claude calls for the strategy loop (e.g., once per hour or once per session start)
- Implement a token budget — log every Claude call with token count and estimated cost; alert when daily cost exceeds threshold
- Cache Claude's market context analysis and reuse for a defined validity window (e.g., 30 minutes)

**Warning signs:**
- Order submission timestamps more than 2 seconds after signal generation
- Claude API costs growing linearly with trade frequency
- Fill prices consistently worse than signal prices (latency-induced slippage)

**Phase to address:**
Architecture phase — the Claude integration pattern must be decided before building the trading loop, not retrofitted.

---

### Pitfall 5: Claude Hallucinating Market Data or Tickers

**What goes wrong:**
Claude is given a natural-language description of market conditions and returns a ticker symbol, a price level, or a company name that is incorrect, outdated, or fabricated. The bot then places a real order based on that hallucination. Example: Claude confuses "GOOG" and "GOOGL" share classes, or cites a pre-split price as a current support level.

**Why it happens:**
LLMs are trained on historical data and have no ground-truth market data access unless explicitly provided. If the prompt asks Claude to "recommend stocks to watch" without supplying current data, Claude will draw on training data that may be 6-18 months stale.

**How to avoid:**
- Never ask Claude to generate ticker symbols, prices, or market facts — always supply them as grounded input from Alpaca's market data API
- Prompt pattern: "Given this data [from Alpaca]: {data}, analyze..." not "What stocks should I buy today?"
- Validate all Claude output: if Claude references a ticker, verify it exists in Alpaca's universe before using it
- Use Claude as a reasoning engine over provided data, not as a data source
- The Alpaca MCP server should be the canonical source for all market data fed to Claude

**Warning signs:**
- Claude returning ticker symbols not in your watchlist without prompting
- Claude stating specific price levels not present in the input data
- Claude referencing market events as "recent" that occurred before its training cutoff

**Phase to address:**
Claude integration design phase — establish the data-grounding pattern at the start, never depart from it.

---

### Pitfall 6: Network Failure Leaving Ghost Positions

**What goes wrong:**
The bot submits a buy order, the network drops before receiving confirmation, and the bot marks the order as "failed" locally. The order was actually received by Alpaca and filled. The bot doesn't know it owns a position, so it doesn't manage it — no stop loss, no exit logic. The position sits unmanaged, potentially losing value, while the bot continues operating unaware.

**Why it happens:**
Error handling treats network timeout as "order failed" without reconciling against actual Alpaca account state. The bot's local state drifts from broker state.

**How to avoid:**
- On any order submission failure (network error, timeout, non-200 response), immediately query `GET /v2/orders` and `GET /v2/positions` to reconcile state before retrying
- Use Alpaca's idempotency key (`client_order_id`) on every order — submit the same UUID on retry; Alpaca will deduplicate
- At bot startup, always fetch current positions and pending orders from Alpaca — never assume a clean slate
- Implement a reconciliation loop that runs every N minutes comparing local state to Alpaca state
- Never retry an order without first checking whether the original filled

**Warning signs:**
- Local position count differs from Alpaca account position count
- Bot showing "no open positions" while account equity differs from cash balance
- Duplicate orders appearing in Alpaca order history

**Phase to address:**
Order execution module phase — reconciliation must be part of the core order submission wrapper, not optional middleware.

---

### Pitfall 7: Race Condition Between Signal and Order Price

**What goes wrong:**
The bot fetches a quote (e.g., AAPL at $182.50), calculates a stop-loss at $181.50, then submits the order. Between quote fetch and order submission, the price moves to $180.00. The limit order is rejected as below market, or the stop-loss is immediately triggered on fill, locking in an immediate loss.

**Why it happens:**
Sequential "fetch price → calculate stops → submit order" logic assumes price is static during execution. In volatile markets, even a 100-500ms delay can invalidate the calculation.

**How to avoid:**
- Use market orders for entries in liquid stocks rather than limit orders that can race against price movement (accept known slippage vs. race conditions)
- Calculate stop-loss and take-profit as percentages relative to fill price (reported in Alpaca's order fill event), not relative to the pre-order quote
- Use Alpaca's trailing stop orders where the exchange manages the stop dynamically
- Subscribe to Alpaca's WebSocket order updates (`trade_updates` stream) to receive fill prices and set stops immediately on fill confirmation

**Warning signs:**
- High rate of limit order rejections
- Stop-loss orders triggering immediately after position entry
- Large difference between target entry price and actual fill price in logs

**Phase to address:**
Order execution module phase, specifically order type selection and stop management design.

---

### Pitfall 8: Paper Trading Results Don't Predict Live Trading Results

**What goes wrong:**
The bot performs well in paper trading for weeks. The user switches to live trading and sees significantly worse results or losses. Paper trading creates false confidence because: (a) fills are simulated at quoted price with no slippage, (b) large orders fill instantly regardless of available liquidity, (c) there's no market impact from the bot's own orders, (d) paper trading has massive latency vs. live trading infrastructure.

**Why it happens:**
Alpaca's paper trading engine is a best-effort simulator, not a market microstructure replica. It will fill 100,000 shares of a thinly-traded stock instantly — live trading would move the market against you significantly.

**How to avoid:**
- Restrict the bot to high-liquidity stocks (top 500 by average daily volume) where slippage is minimal
- Build a slippage model into paper trading validation: add 0.05-0.10% slippage cost to every fill in performance calculations
- Require 30-60 days of profitable paper trading before enabling live mode
- Start live trading with 10% of intended capital to empirically measure live vs. paper performance gap
- Document for users clearly in the `/initialize` flow: "Paper trading results will be better than live results"
- Avoid strategies that depend on precise entry prices (e.g., scalping) — favor strategies robust to 0.1-0.5% slippage

**Warning signs:**
- Paper trading Sharpe ratio > 2.0 (suspiciously good — likely slippage-blind)
- Strategy relies on capturing moves smaller than 0.5%
- High trade frequency (>20 trades/day) suggesting scalping strategy

**Phase to address:**
Paper-to-live transition phase, and the `/initialize` strategy configuration phase (where strategy type and trade frequency are set).

---

### Pitfall 9: Alpaca API Rate Limit (200 req/min) Causing Missed Trades

**What goes wrong:**
The bot polls price data for a watchlist of 50 stocks every second plus submits orders plus queries positions. At 3+ requests per stock per minute, the bot hits Alpaca's 200 requests/minute limit. API calls return HTTP 429. The bot may silently drop market data refreshes or order submissions during this period.

**Why it happens:**
Developers build the polling loop without calculating total API call volume. A naive implementation: 50 stocks × 1 quote/30s = 100 calls/min just for market data, plus order management calls, leaves almost no headroom.

**How to avoid:**
- Use WebSocket streams (Alpaca's `wss://stream.data.alpaca.markets`) for real-time market data instead of REST polling — WebSockets bypass rate limits for market data
- Batch REST calls where possible: use `/v2/stocks/bars` multi-symbol endpoints instead of per-symbol calls
- Implement rate limit tracking: count calls per minute, back off when approaching 160/min (80% of limit)
- On HTTP 429, implement exponential backoff starting at 1 second (not immediate retry)
- Cache position and account data locally, only refreshing on order events not on every loop iteration

**Warning signs:**
- HTTP 429 responses in logs
- Market data refresh timestamps showing gaps greater than expected interval
- Orders submitted but confirmations delayed

**Phase to address:**
Market data architecture phase — WebSocket vs. REST polling decision must be made before building the data pipeline.

---

### Pitfall 10: Insufficient Capital for Strategy + Fees + Margin Requirements

**What goes wrong:**
User starts with $500 and attempts to day trade. Even without the PDT rule (using a cash account), T+2 settlement means the funds from a sale are not available for 2 business days. The bot has no buying power after the first trade of the day. In a margin account under $25,000, PDT applies. The strategy is economically unviable before the bot even has a chance.

**Why it happens:**
The user doesn't understand settlement rules. The plugin was not explicit about minimum capital requirements during setup.

**How to avoid:**
- During `/initialize`, ask for available capital and warn explicitly if it is below $25,000 for margin day trading or if cash account with T+2 settlement will limit daily trade count
- Recommend a minimum of $1,000 for meaningful paper trading validation and $5,000 for cash account swing trading
- Clearly communicate: "For active day trading, $25,000+ is required to avoid PDT restrictions"
- In cash account mode, implement T+2 settlement tracking — the bot must not reuse unsettled funds
- The "autonomous risk mode" must factor in actual buying power, not theoretical position sizes

**Warning signs:**
- Buying power returning $0 despite positive equity (unsettled funds)
- All buy orders rejected during the afternoon session after a morning trade
- User reports "bot isn't trading" — often a buying power/settlement issue

**Phase to address:**
The `/initialize` setup and onboarding phase — capital adequacy check must be step one of setup.

---

### Pitfall 11: Secrets (API Keys) Committed to Git or Hardcoded

**What goes wrong:**
The plugin generates Python scripts that include the Alpaca API key and secret directly in the file. The user pushes their plugin config or generated scripts to a public GitHub repo. A scraper harvests the keys. An attacker places orders, drains buying power, or routes trades through the account for market manipulation. Even if caught quickly, the trades may not be reversible.

**Why it happens:**
The `/build` command generates files with secrets inline for "ease of use." The user doesn't realize config files containing keys are dangerous to version control.

**How to avoid:**
- Never write API keys into generated script files — always reference environment variables (`os.environ["ALPACA_API_KEY"]`)
- Generate a `.env` file for secrets, add `.env` to generated `.gitignore` automatically
- During `/initialize`, warn explicitly: "Your API keys will be stored in .env — never commit this file"
- On Alpaca, create keys with only "Trading" permission enabled — never "Withdrawals" — so a leaked key cannot drain funds
- Recommend IP whitelisting on Alpaca API keys where supported

**Warning signs:**
- Generated files contain literal key strings
- No `.gitignore` in the generated project
- User asking to "copy their config" between machines (often bypasses .env)

**Phase to address:**
The `/build` command implementation phase — secret handling pattern must be designed before any file generation.

---

### Pitfall 12: Plugin Crash During Open Position Without Recovery

**What goes wrong:**
The bot has 3 open positions. Claude Code crashes, the terminal closes, or the server reboots. The bot restarts from scratch with no memory of the open positions. It doesn't close them, doesn't manage stop-losses, and may open new conflicting positions. The unmanaged positions drift for hours or days.

**Why it happens:**
The bot's state (open positions, pending orders, daily trade count) is only in memory. There's no persistent state store. Crash = amnesia.

**How to avoid:**
- On every startup, the bot must query Alpaca's `/v2/positions` and `/v2/orders` as ground truth — never assume a clean state
- Persist bot state (strategy context, daily trade count, configured stops) to a local JSON or SQLite file after every state change
- Implement a startup reconciliation routine: "here are positions Alpaca says I have — are they expected? Apply configured stop-losses to any unmanaged ones"
- Design the bot as stateless + externally reconcilable, not stateful + memory-dependent
- For the Claude Code plugin context: implement a `/status` command that shows current positions, today's P&L, and bot state at any time

**Warning signs:**
- Bot startup not logging "reconciling X open positions"
- Position data only sourced from local memory, not Alpaca API
- No state persistence file in the generated project structure

**Phase to address:**
State management and crash recovery phase — must be built before the first live trading session.

---

### Pitfall 13: Market Open/Close Edge Cases Causing Bad Fills

**What goes wrong:**
The bot submits a market order at 9:29 AM (1 minute before market open). The order queues and fills at the open at a wildly different price from the pre-market quote. Alternatively, the bot submits an order at 3:59 PM, it queues, and Alpaca routes it to after-hours trading where liquidity is extremely thin and spreads are wide.

**Why it happens:**
The bot's trading loop doesn't enforce market session awareness. It treats 9:00 AM and 3:00 PM identically. Pre-market and after-hours orders on liquid stocks can have 1-5% wider spreads.

**How to avoid:**
- Define a strict "trading window" with configurable start and end times (default: 9:35 AM - 3:45 ET to avoid open/close volatility spikes)
- Cancel all unfilled orders before market close to prevent after-hours routing
- During `/initialize`, configure extended-hours trading explicitly as opt-in, not default
- Use Alpaca's `extended_hours: false` parameter on all orders unless user explicitly opted into extended hours
- Implement a "market calendar" check using Alpaca's `/v2/calendar` endpoint — don't trade on holidays or early-close days

**Warning signs:**
- Orders submitted within 5 minutes of market open or close
- After-hours position entries appearing in logs
- Fill prices significantly different from last-quote prices (>1% gap)

**Phase to address:**
Trading loop scheduling phase — market session constraints must be part of the core loop scheduler.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Polling REST for market data instead of WebSocket | Simpler initial implementation | Hits rate limits at 10+ tickers; adds latency | Never for production; paper trading only |
| Storing API keys in config files instead of .env | Easier copy/paste during dev | Catastrophic if committed to git | Never — not acceptable at any stage |
| Skipping T+2 settlement tracking in cash accounts | Less complexity | Bot runs out of buying power, confuses user | Never — must be implemented before live |
| No crash recovery / startup reconciliation | Faster MVP | Ghost positions, missed stop-losses | Paper trading only (no real money risk) |
| Calling Claude per-trade instead of per-session | Conceptually cleaner | API cost explosion, latency kills timing | Never for live trading |
| Hard-coding watchlist instead of deriving it from strategy | Faster to ship | No adaptability; wrong tickers for user strategy | Paper trading validation only |
| No idempotency keys on orders | Simpler code | Duplicate orders on network retry | Never — costs money |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Alpaca REST API | Polling quotes per-ticker every second | Use WebSocket `wss://stream.data.alpaca.markets` for real-time quotes |
| Alpaca Order API | Treating HTTP timeout as "order failed" | Check `/v2/positions` and `/v2/orders` before retrying; use `client_order_id` |
| Alpaca Paper Trading | Trusting paper fill prices as live equivalent | Add synthetic slippage model; validate performance on liquid high-volume stocks only |
| Alpaca Account API | Reading buying_power without checking settlement | Check `cash` vs `buying_power` — cash may be unsettled; margin may not be available |
| Claude API | Calling Claude for every trade signal | Cache Claude's session-level analysis; call per-session not per-trade |
| Claude API | Asking Claude to generate market data | Always inject real Alpaca data into prompt; validate all Claude-referenced tickers/prices |
| Alpaca PDT Check | Assuming broker enforces PDT (and you don't need to) | Broker enforcement is reactive (rejects the 4th trade); build proactive pre-check in the bot |
| Alpaca Market Calendar | Trading on market holidays | Call `/v2/calendar` at session start to verify it's a trading day |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| REST polling for 20+ tickers | HTTP 429 errors; stale data warnings; missed signals | Switch to WebSocket streaming for all real-time data | Around 15-20 tickers at 1-second polling |
| Claude called per-trade signal | Response latency 2-10s per trade; monthly API costs $300+ | Call Claude per-session (once/day or once/hour) for strategy context only | Immediately with any live trading |
| No local state caching | Account status API hammered; 429 errors on position queries | Cache positions/orders locally; refresh on events, not on timer | Around 50-100 queries/session |
| Synchronous order + confirmation + next-action | Sequential waits compound; 5s/trade = 10 trades/min max | Use async order submission with WebSocket `trade_updates` stream | Any strategy with >5 trades/day |
| Logging every tick to disk | Disk fills up; I/O bottleneck slows trading loop | Log signals and orders only; use rotating log files | About 10,000 ticks/day per ticker |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| API key with withdrawal permissions enabled | Attacker drains funds if key leaked | Enable only "Trading" permission on Alpaca API keys; never "Withdrawals" |
| API keys in generated Python files | Key committed to git; public repo exposes it | Always use environment variables; generate .env file; add to .gitignore |
| No IP whitelisting on Alpaca API key | Leaked key usable from anywhere | Set IP restriction on Alpaca API key to the server/machine running the bot |
| Config files with secrets shared between users | Plugin user shares config; exposes another user's keys | Each user generates their own keys; plugin never shares config files across users |
| Logging API responses verbatim | Logs may contain order confirmation details or position sizes | Scrub sensitive fields before logging; never log raw API key values |
| No rate limit on /initialize secrets prompt | Confused user types key into wrong prompt; stored in shell history | Accept API keys via env var or secure file prompt, not command-line argument |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Bot "just starts trading" with no confirmation | Beginner user doesn't realize real money is at stake | Require explicit "I confirm this is LIVE trading with REAL money" acknowledgment |
| All configuration in one long /initialize session | Users don't remember what they configured; can't audit settings | Write config to a human-readable YAML after /initialize; include /config command to review |
| Cryptic error messages from Alpaca API | User sees HTTP 403, doesn't know it means PDT | Translate all Alpaca API error codes into plain-English explanations in the plugin |
| No daily summary | User can't assess bot performance | Generate daily P&L summary (trades made, profit/loss, PDT count remaining, buying power) |
| Paper-to-live switch buried in config | Beginner accidentally runs live from day 1 | Default to paper mode; require explicit step to enable live; add warning banner in status output |
| No way to pause bot without killing process | User can't step in during unusual market event | Implement pause/resume mechanism via a flag file or /pause command |

---

## "Looks Done But Isn't" Checklist

- [ ] **PDT Tracking:** Bot appears to trade correctly — verify it maintains a rolling 5-day day-trade counter and halts at 3 (not 4)
- [ ] **Circuit Breakers:** Bot submits orders successfully — verify daily loss limit actually halts trading (test by simulating losses)
- [ ] **Crash Recovery:** Bot restarts cleanly — verify it reads open positions from Alpaca on startup, not just from local memory
- [ ] **Paper-to-Live Guard:** `/run` command works — verify it cannot start in live mode without explicit confirmation and API key validation
- [ ] **Stop-Loss on Every Position:** Bot enters positions — verify every entry has a corresponding stop-loss order submitted to Alpaca
- [ ] **API Key Security:** Plugin generates scripts — verify no API key appears in any generated file; only env var references
- [ ] **Market Calendar:** Bot runs on a Monday — verify it checks `/v2/calendar` and would not trade on market holidays or early-close days
- [ ] **Rate Limit Handling:** Bot makes API calls — verify it handles HTTP 429 with exponential backoff, not immediate retry
- [ ] **T+2 Settlement:** Cash account configured — verify bot tracks settled vs. unsettled funds; doesn't reuse unsettled proceeds
- [ ] **Order Idempotency:** Network failure simulated — verify retry uses same `client_order_id` and doesn't create duplicate orders
- [ ] **Extended Hours Guard:** Default config — verify no orders submit before 9:30 AM or after 4:00 PM ET without explicit opt-in
- [ ] **Claude Data Grounding:** Claude called with market analysis — verify prompt always includes real Alpaca data, never asks Claude to supply market data

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| PDT violation (90-day restriction) | HIGH | Switch to cash account; wait 90 days; or deposit enough to bring equity above $25,000 |
| API key leaked to git | HIGH | Immediately revoke key in Alpaca dashboard; generate new key; scrub git history with BFG or git-filter-repo |
| Ghost position from network failure | MEDIUM | Query Alpaca positions; manually close unmanaged positions in Alpaca dashboard; improve reconciliation logic |
| Claude API cost spike | LOW | Review logs for call frequency; implement caching; set API spend alert in Anthropic console |
| Rate limit 429 storm | LOW | Add 60s backoff; switch to WebSocket for market data; the situation self-resolves quickly |
| Wash sale triggered | MEDIUM | Consult tax professional; implement wash sale guard; consider MTM election for future years |
| Runaway bot before circuit breaker | HIGH | Emergency: use Alpaca's "Cancel All Orders" API endpoint; close all positions manually in Alpaca dashboard |
| Paper-to-live transition failure | MEDIUM | Immediately switch back to paper mode; review fill quality differences; add slippage buffer to strategy minimum edge |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| PDT rule violation | Phase: Order Execution & Risk Engine | Test: submit a 4th simulated day trade; verify rejection before submission |
| Wash sale trap | Phase: /initialize setup + Order Execution | Test: sell at loss and re-enter same ticker within 30 days; verify warning/block |
| No circuit breakers | Phase: Risk Management Foundation (must be Phase 1) | Test: simulate daily loss exceeding threshold; verify halt |
| LLM latency per-trade | Phase: Architecture Design (pre-coding) | Measure: time from signal to order submission must be < 500ms |
| LLM hallucination | Phase: Claude Integration Design | Test: prompt without market data; verify Claude cannot fabricate tickers |
| Ghost positions from crash | Phase: State Management & Recovery | Test: kill process mid-order; verify restart reconciles from Alpaca |
| Network failure ghost order | Phase: Order Execution Layer | Test: simulate network timeout; verify idempotency and reconciliation |
| Race condition on price | Phase: Order Execution Layer | Test: use trailing stop orders; verify stops set from fill price not quote price |
| Paper vs live gap | Phase: Paper-to-Live Transition | Verify: 30-day paper trading with synthetic slippage model matches live within 20% |
| Capital insufficiency | Phase: /initialize Onboarding | Test: enter $500 capital; verify PDT warning and cash account recommendation |
| API key in files | Phase: /build Command Implementation | Audit: grep generated files for literal key strings; verify .env pattern |
| Crash recovery failure | Phase: State Persistence Implementation | Test: kill bot with open positions; verify startup reads and manages those positions |
| Market session edge cases | Phase: Trading Loop Scheduler | Test: attempt order at 9:28 AM; verify rejection; test market holiday |
| API rate limit exhaustion | Phase: Market Data Architecture | Load test: run 25-ticker watchlist for 10 minutes; verify no 429 errors |

---

## Sources

- [Alpaca PDT Rule Support](https://alpaca.markets/support/what-is-the-pattern-day-trading-pdt-rule)
- [Alpaca Paper Trading Docs](https://docs.alpaca.markets/docs/paper-trading)
- [Alpaca API Rate Limits](https://alpaca.markets/support/usage-limit-api-calls)
- [Alpaca User Protection](https://docs.alpaca.markets/docs/user-protection)
- [Wash Sale Rule Algo Trading - Terms.Law](https://terms.law/Trading-Legal/guides/wash-sale-algo-trading.html)
- [Taxation and Algo Trading - LuxAlgo](https://www.luxalgo.com/blog/taxation-and-algo-trading-know-your-liabilities/)
- [SEC/FINRA Automated Trading Regulations](https://daytraderbusiness.com/regulations/sec-finra/sec-finra-rules-on-automated-trading-and-algorithms/)
- [FINRA Algorithmic Trading Rules](https://www.finra.org/rules-guidance/key-topics/algorithmic-trading)
- [Algorithmic Trading Overfitting](https://blog.pickmytrade.trade/algorithmic-trading-overfitting-backtest-failure/)
- [Backtesting vs Live Trading Gap - PineConnector](https://www.pineconnector.com/blogs/pico-blog/backtesting-vs-live-trading-bridging-the-gap-between-strategy-and-reality)
- [Key Risks in Automated Trading - DarkBot](https://darkbot.io/blog/key-risks-in-automated-trading-what-traders-miss)
- [Why Most Trading Bots Lose Money - ForTraders](https://www.fortraders.com/blog/trading-bots-lose-money)
- [LLM Token Costs and Latency - Stevens Online](https://online.stevens.edu/blog/hidden-economics-ai-agents-token-costs-latency/)
- [Risk Management in Algo Trading - LuxAlgo](https://www.luxalgo.com/blog/risk-management-strategies-for-algo-trading/)
- [Daily Loss Limit Day Trading - Trade That Swing](https://tradethatswing.com/setting-a-daily-loss-limit-when-day-trading/)
- [API Key Security for Trading Bots - Streamline](https://www.usestreamline.net/resources/blog/how-to-secure-your-crypto-trading-bot-api-keys-safety/)
- [Circuit Breaker Pattern for AI Agents - DEV.to](https://dev.to/tumf/ralph-claude-code-the-technology-to-stop-ai-agents-how-the-circuit-breaker-pattern-prevents-3di4)
- [Troubleshooting Automated Trading Race Conditions - TradersPost](https://blog.traderspost.io/article/troubleshooting-automated-trading-strategies)
- [Alpaca Paper vs Live Trading](https://alpaca.markets/support/difference-paper-live-trading)
- [Alpaca Community Forum - Rate Limits](https://forum.alpaca.markets/t/429-rate-limit-exceeded-when-creating-orders/14120)

---
*Pitfalls research for: Automated stock day trading Claude Code plugin (Alpaca API)*
*Researched: 2026-03-21*
