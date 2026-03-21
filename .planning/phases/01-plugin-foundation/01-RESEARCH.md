# Phase 1: Plugin Foundation - Research

**Researched:** 2026-03-21
**Domain:** Claude Code Plugin System, Python dependency management, interactive wizard patterns, configuration schema design
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Wizard Interaction Flow**
- Wizard uses Claude Code's native AskUserQuestion prompts — no external UI dependencies
- 5-6 grouped steps: experience level → risk tolerance → budget/mode → strategies → market hours → watchlist
- Smart defaults pre-filled based on experience level — beginners get conservative defaults, experts get neutral starting points
- Invalid input handled by re-prompting with explanation of valid options

**Configuration Schema**
- Config stored as JSON (`config.json`) in `${CLAUDE_PLUGIN_DATA}` directory
- Strategies stored as array of strategy objects with per-strategy params: `[{"name": "momentum", "weight": 0.5, "params": {...}}]`
- API keys stored in `.env` file in plugin data dir, loaded by pydantic-settings — never stored in config.json
- Config file format matches REQUIREMENTS STATE-03

**Beginner vs Expert Adaptation**
- First question asks directly: "What's your trading experience?" with 3 options (beginner/intermediate/expert)
- Beginners: fewer questions, conservative defaults auto-applied, explanatory descriptions on each option
- Experts: all parameters exposed, no defaults pre-selected, technical terminology used
- Default trading mode for beginners is paper trading only — live requires explicit opt-in

**Plugin Bootstrap & Dependencies**
- SessionStart hook installs deps via `uv pip install` into `${CLAUDE_PLUGIN_DATA}/venv`
- Dep reinstall triggered by diffing `requirements.txt` hash against cached hash in plugin data dir
- No MCP server — all Alpaca access goes through alpaca-py SDK in Python scripts; Claude reads bot output/logs for analysis

**ALP-04 DROPPED**: No Alpaca MCP server. SDK-only approach.

### Claude's Discretion

No items deferred to Claude's discretion — all areas resolved.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CMD-01 | User can run `/initialize` to start an interactive setup wizard | `/initialize` is a `commands/initialize.md` file; Claude executes it using AskUserQuestion tool |
| CMD-02 | Initialize wizard adapts questions based on beginner vs expert user | Command prompt instructs Claude to branch based on first question answer |
| CMD-03 | Initialize wizard captures risk tolerance, budget, paper vs live, autonomy level, strategies, market hours, ticker watchlist | Wizard prompt enumerates all fields; Claude gathers them sequentially and writes config.json |
| CMD-04 | Initialize wizard includes autonomous risk mode option where Claude decides aggression per trade | One wizard option sets `autonomy_mode: "claude_decides"` in config |
| CMD-05 | Initialize wizard outputs a complete config file that all other commands consume | Wizard writes `${CLAUDE_PLUGIN_DATA}/config.json` as final step |
| CMD-12 | User can select from momentum, mean reversion, breakout, and VWAP strategies during initialize | Wizard step presents strategy options; selected ones become strategy array in config |
| ALP-01 | Plugin authenticates with Alpaca API using environment variables (paper and live keys) | `.env` template written by wizard; pydantic-settings loads it in Python scripts |
| ALP-02 | Plugin supports paper trading mode with Alpaca's paper endpoint | `paper_trading: true` captured in wizard; propagated to config |
| ALP-03 | Plugin supports live trading mode with Alpaca's live endpoint | `paper_trading: false` requires explicit expert opt-in |
| ALP-04 | DROPPED per user decision — no MCP server | N/A |
| PLUG-01 | Plugin follows Claude Code plugin directory structure | Standard layout: commands/, agents/, skills/, hooks/, references/ |
| PLUG-05 | Trading rules skill provides domain context to all agents | `skills/trading-rules/SKILL.md` with `user-invocable: false` |
| PLUG-06 | SessionStart hook installs Python dependencies into plugin data directory | `hooks/hooks.json` with SessionStart command using `uv pip install` + diff pattern |
| PLUG-08 | Reference files document trading strategies, risk rules, and Alpaca API patterns | 3 files in `references/`: trading-strategies.md, risk-rules.md, alpaca-api-patterns.md |
| STATE-03 | Bot maintains configuration in JSON file editable without code changes | config.json in CLAUDE_PLUGIN_DATA; schema documented so users can hand-edit |
</phase_requirements>

---

## Summary

This phase creates the Claude Code plugin scaffold and interactive `/initialize` setup wizard. Claude Code's plugin system is well-documented and mature — all required components (commands, agents, skills, hooks, references) have stable APIs. The directory structure is prescribed, component discovery is automatic, and the SessionStart hook pattern for dependency installation is directly documented in official examples.

The wizard is implemented as a `commands/initialize.md` file (a plain markdown prompt). Claude Code runs this prompt with full tool access — Claude uses `AskUserQuestion` to gather preferences, applies branching logic based on experience level, then writes `config.json` to `${CLAUDE_PLUGIN_DATA}`. No external UI framework is needed. The entire interaction is Claude reasoning through a prompt.

The critical constraint for this phase is that `${CLAUDE_PLUGIN_DATA}` is the only persistent location that survives plugin updates — all generated files (config.json, .env, venv) must go there. `${CLAUDE_PLUGIN_ROOT}` is the read-only plugin installation directory (bundled files: scripts, SKILL.md files, requirements.txt). The SessionStart hook follows the diff-then-reinstall pattern from official docs: compare `requirements.txt` hash, reinstall on mismatch.

**Primary recommendation:** Build the plugin skeleton first (manifest + hook + directory structure), validate it loads with `claude --debug`, then implement the wizard command, then add skills and reference files. Keep the wizard as a single command prompt file — do not create a separate agent for it; that adds unnecessary complexity for a linear flow.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alpaca-py | 0.43.2 | Alpaca SDK for trading (established in CLAUDE.md) | Only maintained Alpaca SDK; alpaca-trade-api is deprecated |
| pydantic-settings | 2.x | Config schema validation and .env loading | Consistent with alpaca-py's pydantic v2 usage; JsonConfigSettingsSource loads config.json natively |
| pydantic | 2.x | Data validation, config models | Required by alpaca-py; pydantic-settings 2.x depends on it |
| pandas-ta | 0.4.71b0 (beta) | Technical indicators (Phase 3 prep) | Listed in requirements.txt now; installed by SessionStart hook |
| pandas | 2.x | DataFrame operations | Required by pandas-ta |
| numpy | 1.26+ | Numerical ops | Required by pandas-ta |
| APScheduler | 3.x | Trading loop scheduling (Phase 3 prep) | In requirements.txt; avoid 4.x alpha rewrite |
| loguru | 0.7+ | Structured logging for autonomous loop | One-import structured logging; critical for unattended operation |
| python-dotenv | 1.x | .env loading in standalone scripts | Backup to pydantic-settings for scripts without full settings class |
| uv | Latest | Python package manager for dep installation | Already required for any Python tooling; 10-100x faster than pip |

### Supporting (Phase 1 only — no trading execution yet)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich | Latest | Pretty terminal output in wizard | `/initialize` output — tables for config preview |
| json (stdlib) | stdlib | Config file read/write | Used in command prompt's Bash calls to write config.json |
| hashlib (stdlib) | stdlib | SHA256 hash of requirements.txt | SessionStart hook diff check |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `uv pip install` | `pip install` | pip is slower and not required by anything else; uv is already the standard tool in this project |
| pydantic-settings JsonConfigSettingsSource | plain `json.load` | plain json works; pydantic-settings adds type validation and catches bad config before trading starts |
| `commands/initialize.md` | Dedicated agent for wizard | Agent adds isolation overhead for a sequential linear flow; simple command is sufficient |

**Installation (bundled requirements.txt — installed by SessionStart hook):**
```
alpaca-py==0.43.2
pandas-ta==0.4.71b0
pandas>=2.0
numpy>=1.26
APScheduler>=3.10,<4.0
pydantic-settings>=2.0
loguru>=0.7
python-dotenv>=1.0
rich>=13.0
```

---

## Architecture Patterns

### Recommended Project Structure

```
trading-bot/                    # Plugin root
├── .claude-plugin/
│   └── plugin.json             # Plugin manifest (name, version, description)
├── commands/
│   └── initialize.md           # /initialize wizard command
├── agents/
│   └── setup-wizard.md         # (optional) wizard subagent if logic grows complex
├── skills/
│   └── trading-rules/
│       └── SKILL.md            # Domain context — auto-loaded by Claude when relevant
├── hooks/
│   └── hooks.json              # SessionStart dep install hook
├── references/
│   ├── trading-strategies.md   # Strategy descriptions for agents
│   ├── risk-rules.md           # Risk parameter reference
│   └── alpaca-api-patterns.md  # alpaca-py code patterns
├── scripts/
│   └── install-deps.sh         # Called by SessionStart hook
└── requirements.txt            # Python deps (hash-checked on SessionStart)
```

**Runtime layout (CLAUDE_PLUGIN_DATA — not in git):**
```
~/.claude/plugins/data/trading-bot-*/
├── config.json                 # Written by /initialize
├── .env                        # API keys written by /initialize
├── requirements.txt.sha256     # Hash of last installed requirements.txt
└── venv/                       # Python venv created by SessionStart hook
    └── lib/...
```

### Pattern 1: Plugin Manifest

**What:** `.claude-plugin/plugin.json` declares the plugin identity. `name` is the only required field. All component directories (commands/, agents/, skills/, hooks/) are auto-discovered at the plugin root — no need to list them in the manifest.

**When to use:** Always create the manifest. Without it, the plugin name is derived from the directory name (fragile). Semver version field is required for marketplace cache invalidation on updates.

```json
// Source: https://code.claude.com/docs/en/plugins-reference#plugin-manifest-schema
{
  "name": "trading-bot",
  "version": "0.1.0",
  "description": "Autonomous stock day trading bot for Alpaca Markets",
  "author": {
    "name": "Your Name"
  },
  "repository": "https://github.com/your-user/trading-bot",
  "license": "MIT",
  "keywords": ["trading", "alpaca", "stocks", "autonomous"]
}
```

### Pattern 2: SessionStart Dependency Hook

**What:** `hooks/hooks.json` defines a `SessionStart` hook that checks if `requirements.txt` has changed (by SHA256 hash) and runs `uv pip install` into the plugin data venv when it has. This covers first-run and plugin-update cases.

**When to use:** Any plugin with Python deps. Official docs show the diff pattern with `package.json`; adapt it with SHA256 for `requirements.txt`.

```json
// Source: https://code.claude.com/docs/en/plugins-reference#persistent-data-directory (adapted for Python/uv)
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.sh\""
          }
        ]
      }
    ]
  }
}
```

```bash
#!/usr/bin/env bash
# scripts/install-deps.sh
# Source: Official diff pattern from plugins-reference, adapted for Python/uv
set -e

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
DATA_DIR="${CLAUDE_PLUGIN_DATA}"
VENV_DIR="${DATA_DIR}/venv"
REQ_FILE="${PLUGIN_ROOT}/requirements.txt"
REQ_HASH_FILE="${DATA_DIR}/requirements.txt.sha256"

# Compute current hash
CURRENT_HASH=$(sha256sum "${REQ_FILE}" | awk '{print $1}')
STORED_HASH=$(cat "${REQ_HASH_FILE}" 2>/dev/null || echo "")

if [ "${CURRENT_HASH}" != "${STORED_HASH}" ]; then
  echo "[trading-bot] Dependencies changed, installing..."
  uv venv "${VENV_DIR}" --python 3.12 --quiet
  uv pip install -r "${REQ_FILE}" --python "${VENV_DIR}/bin/python" --quiet
  echo "${CURRENT_HASH}" > "${REQ_HASH_FILE}"
  echo "[trading-bot] Dependencies installed."
else
  echo "[trading-bot] Dependencies up to date."
fi
```

### Pattern 3: Initialize Command (Wizard)

**What:** `commands/initialize.md` is a plain markdown file whose content becomes Claude's prompt when the user runs `/initialize`. Claude uses `AskUserQuestion` to gather responses interactively. The command writes `config.json` and `.env` to `${CLAUDE_PLUGIN_DATA}` at the end.

**When to use:** All interactive setup flows. Do not use a separate agent for a linear 5-6 step wizard — the overhead isn't justified. Use `allowed-tools` to grant `AskUserQuestion`, `Write`, and `Bash` without per-call approval.

```markdown
// Source: https://code.claude.com/docs/en/slash-commands#frontmatter-reference
---
name: initialize
description: Interactive setup wizard to configure the trading bot
argument-hint: "[--reset]"
disable-model-invocation: true
allowed-tools: AskUserQuestion, Write, Bash, Read
---

You are guiding a user through the trading bot setup wizard.
Follow these steps in order. Do not skip steps.

## Step 1: Experience Level
Ask: "What is your trading experience level?"
Options:
1. Beginner — I'm new to trading, prefer guided defaults
2. Intermediate — I have some experience, want balanced options
3. Expert — I understand trading well, show me all parameters

Store result as `experience_level`.

## Step 2: Paper vs Live Mode
[... etc for each step ...]

## Final Step: Write Config
Write the completed configuration to ${CLAUDE_PLUGIN_DATA}/config.json.
Write the API key template to ${CLAUDE_PLUGIN_DATA}/.env.
Confirm to the user where files were written.
```

**Critical:** `allowed-tools` in command/skill frontmatter grants those tools without per-call approval dialogs during that command's execution. This is required for a smooth wizard flow.

### Pattern 4: Trading-Rules Skill (Auto-Loaded Context)

**What:** `skills/trading-rules/SKILL.md` with `user-invocable: false` provides domain context (risk parameters, market hours rules, position limits) automatically when Claude's conversation touches trading topics.

**When to use:** Domain knowledge that all agents should have but users shouldn't invoke directly. `user-invocable: false` hides it from the `/` menu but keeps the description in Claude's context so it auto-loads.

```yaml
// Source: https://code.claude.com/docs/en/slash-commands#control-who-invokes-a-skill
---
name: trading-rules
description: Trading domain rules — risk limits, market hours, position sizing constraints. Auto-load when discussing trading decisions, strategy execution, or risk management.
user-invocable: false
---

## Core Trading Rules
[risk limits, market hours, etc.]
```

### Pattern 5: Config Schema with pydantic-settings

**What:** The wizard writes a raw `config.json`. Python scripts (built in Phase 4) load it via pydantic-settings `JsonConfigSettingsSource`. This gives type validation before any trading begins.

**When to use:** Any Python script that consumes config. Define the schema once, reuse across all scripts.

```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
# and https://medium.com/@wihlarkop/how-to-load-configuration-in-pydantic-3693d0ee81a3
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict, JsonConfigSettingsSource
from typing import Tuple, Type

class StrategyConfig(BaseModel):
    name: str  # "momentum" | "mean_reversion" | "breakout" | "vwap"
    weight: float
    params: dict

class TradingBotConfig(BaseSettings):
    model_config = SettingsConfigDict(
        json_file="${CLAUDE_PLUGIN_DATA}/config.json",
        env_file="${CLAUDE_PLUGIN_DATA}/.env",
    )
    experience_level: str
    paper_trading: bool = True
    risk_tolerance: str  # "conservative" | "moderate" | "aggressive"
    autonomy_mode: str   # "claude_decides" | "fixed_params"
    max_position_pct: float
    max_daily_loss_pct: float
    budget_usd: float
    strategies: list[StrategyConfig]
    market_hours_only: bool = True
    watchlist: list[str]
    alpaca_api_key: str = ""      # loaded from .env
    alpaca_secret_key: str = ""   # loaded from .env
```

### Config JSON Schema (written by wizard)

```json
{
  "experience_level": "beginner",
  "paper_trading": true,
  "risk_tolerance": "conservative",
  "autonomy_mode": "fixed_params",
  "max_position_pct": 5.0,
  "max_daily_loss_pct": 2.0,
  "budget_usd": 10000,
  "strategies": [
    {
      "name": "momentum",
      "weight": 1.0,
      "params": {
        "rsi_period": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9
      }
    }
  ],
  "market_hours_only": true,
  "watchlist": ["AAPL", "MSFT", "SPY"],
  "autonomy_level": "notify_only",
  "created_at": "2026-03-21T00:00:00Z",
  "config_version": "1"
}
```

**API keys stay in `.env` — never in config.json:**
```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_PAPER=true
```

### Anti-Patterns to Avoid

- **Putting plugin.json inside commands/ or agents/ directory:** Only `plugin.json` goes in `.claude-plugin/`. All other component directories must be at the plugin root. This is the #1 structural mistake per official troubleshooting docs.
- **Referencing `${CLAUDE_PLUGIN_ROOT}` for persistent data:** Root is read-only and gets overwritten on plugin update. All user-written files go in `${CLAUDE_PLUGIN_DATA}`.
- **Using absolute paths in hooks.json:** All hook command paths must use `${CLAUDE_PLUGIN_ROOT}` variable, not hardcoded paths. Hardcoded paths break after plugin cache copy.
- **Creating a dedicated wizard agent instead of a command:** An agent adds isolation (no conversation history, separate context). The wizard needs access to the full conversation to handle re-prompts gracefully. Use a command (inline context).
- **Storing API keys in config.json:** The wizard must write them to `.env` only. config.json is potentially readable by generated scripts that get shared.
- **Skipping `chmod +x` on hook scripts:** Hook scripts must be executable or they silently fail. Add this to the troubleshooting checklist.
- **Using APScheduler 4.x:** The 4.x API is a complete rewrite in alpha. All community examples, this project's research, and CLAUDE.md say stick to 3.x.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Python dep management | Custom install scripts, version checks | `uv pip install -r requirements.txt` | uv handles dependency resolution, conflict detection, and version pinning correctly |
| Config validation | Manual JSON key presence checks | pydantic-settings with typed model | Catches missing fields, wrong types, and env var loading before trading begins |
| .env file loading | `os.environ.get()` calls scattered in scripts | pydantic-settings BaseSettings with env_file | Centralized, typed, with validation and clear error messages |
| Plugin manifest | None needed for simple plugins | `.claude-plugin/plugin.json` | Without it, plugin name derives from directory name — fragile during install |
| Hash-based reinstall detection | Custom timestamp checks | `sha256sum` diff against stored hash | Timestamps are unreliable across plugin updates; content hash is definitive |

**Key insight:** The plugin system handles component discovery automatically. The only code that needs to be written is: the hook shell script, the wizard markdown prompt, and the skill/reference markdown files. No Python is executed in Phase 1 — the Python scripts and venv are built in later phases.

---

## Common Pitfalls

### Pitfall 1: Component Directories Inside `.claude-plugin/`

**What goes wrong:** Developer puts `commands/` inside `.claude-plugin/` alongside `plugin.json`. Plugin loads but no commands appear. Claude reports "No commands found."

**Why it happens:** The directory is named `.claude-plugin/` which sounds like it should contain plugin files.

**How to avoid:** Only `plugin.json` goes in `.claude-plugin/`. All other directories (`commands/`, `agents/`, `skills/`, `hooks/`) must be at the plugin root.

**Warning signs:** Plugin loads successfully (`claude --debug` shows it) but `/initialize` doesn't appear in the command list.

### Pitfall 2: Hook Script Not Executable

**What goes wrong:** `SessionStart` hook fires but does nothing. No error, no output.

**Why it happens:** Shell scripts require the executable bit. The hook `command` type runs the script directly, not via `bash -c`.

**How to avoid:** Run `chmod +x scripts/install-deps.sh` after creating the file. Verify with `ls -la scripts/`.

**Warning signs:** No output from the hook on session start. Manually running the script works fine.

### Pitfall 3: uv Not in PATH During Hook Execution

**What goes wrong:** `install-deps.sh` fails with `uv: command not found` even though `uv` is installed.

**Why it happens:** Hook processes may have a restricted PATH that doesn't include user-level tool installs (e.g., `~/.cargo/bin` or `~/.local/bin`).

**How to avoid:** Use the full path to uv in the hook script, or add a PATH expansion at the top of the script:
```bash
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
```

**Warning signs:** `uv --version` works in terminal but hook fails.

### Pitfall 4: Writing config.json to Wrong Location

**What goes wrong:** Wizard writes `config.json` to the project working directory instead of `${CLAUDE_PLUGIN_DATA}`. The file is created, but subsequent commands can't find it because they look in `${CLAUDE_PLUGIN_DATA}`.

**Why it happens:** The wizard prompt uses a `Write` tool call. If `${CLAUDE_PLUGIN_DATA}` isn't expanded before the Write call, Claude may write to a relative path.

**How to avoid:** Use `Bash` to get the value of `${CLAUDE_PLUGIN_DATA}` first, then pass the expanded path to `Write`. Alternatively, write via:
```bash
cat > "${CLAUDE_PLUGIN_DATA}/config.json" << 'EOF'
{...json content...}
EOF
```

**Warning signs:** config.json appears in the current working directory instead of `~/.claude/plugins/data/trading-bot-*/`.

### Pitfall 5: Plugin Version Not Bumped After Changes

**What goes wrong:** Developer changes hook script or skill content, pushes to git, but existing users don't see the update.

**Why it happens:** Claude Code uses the `version` field in `plugin.json` to detect updates. Same version = same cache = no update.

**How to avoid:** Bump `version` in `plugin.json` on every change pushed to the marketplace. Use semver: patch bump for bug fixes, minor for new features.

**Warning signs:** Users report old behavior after a push. `/plugin update` does nothing.

### Pitfall 6: Wizard Prompt Too Long for Context

**What goes wrong:** `commands/initialize.md` grows to 500+ lines with detailed instructions for every edge case. Context budget is consumed before Claude can finish the wizard.

**Why it happens:** It's tempting to document every wizard variation inline. The wizard is a command prompt, not a reference doc.

**How to avoid:** Keep `initialize.md` under 200 lines. Move strategy descriptions to `references/trading-strategies.md`. Reference that file in the wizard prompt: "For strategy descriptions, read references/trading-strategies.md".

---

## Code Examples

Verified patterns from official sources:

### hooks/hooks.json (complete file)
```json
// Source: https://code.claude.com/docs/en/plugins-reference#hooks
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.sh\""
          }
        ]
      }
    ]
  }
}
```

### skills/trading-rules/SKILL.md (frontmatter)
```yaml
// Source: https://code.claude.com/docs/en/slash-commands#control-who-invokes-a-skill
---
name: trading-rules
description: Core trading rules and risk parameters for this bot. Provides position sizing limits, market hours constraints, PDT rules, and strategy context. Auto-load when the conversation involves trading decisions, risk management, or strategy execution.
user-invocable: false
---
```

### commands/initialize.md (frontmatter)
```yaml
// Source: https://code.claude.com/docs/en/slash-commands#frontmatter-reference
---
name: initialize
description: Interactive setup wizard — configure the trading bot preferences and generate config.json
argument-hint: "[--reset]"
disable-model-invocation: true
allowed-tools: AskUserQuestion, Write, Bash, Read
---
```

### Environment variable expansion in hook commands
```json
// Source: https://code.claude.com/docs/en/plugins-reference#environment-variables
// Both variables are expanded inline in hook commands AND exported to hook processes
{
  "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.sh\""
}
// Inside the script, CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA are available as env vars
```

### pydantic-settings JsonConfigSettingsSource (Python scripts, Phase 4+)
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic_settings import BaseSettings, SettingsConfigDict

class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(
        json_file="config.json",   # path resolved before instantiation
        env_file=".env",
    )
    paper_trading: bool = True
    # ... all fields
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `.claude/commands/deploy.md` | `.claude/skills/deploy/SKILL.md` | 2025 (merged) | Both still work; skills add supporting files dir and invocation control |
| `plugin.json` at plugin root | `.claude-plugin/plugin.json` | Plugin system v1 | Manifest must be in `.claude-plugin/` subdirectory |
| alpaca-trade-api | alpaca-py | 2023 (deprecated) | alpaca-trade-api still works but no new features; alpaca-py is the only maintained SDK |
| APScheduler 3.x | APScheduler 4.x (alpha) | 2024 (alpha) | Stick to 3.x — 4.x is a complete API rewrite not yet stable |

**Deprecated/outdated:**
- `alpaca-trade-api`: Officially deprecated by Alpaca since 2023. Do not use in any generated code.
- MCP server for this project: Dropped per user decision. The ALP-04 requirement is voided.
- Placing component directories inside `.claude-plugin/`: Always put them at the plugin root.

---

## Open Questions

1. **`${CLAUDE_PLUGIN_DATA}` expansion in `Write` tool calls during wizard**
   - What we know: `${CLAUDE_PLUGIN_DATA}` is documented to expand "anywhere they appear in skill content, agent content, hook commands, and MCP or LSP server configs"
   - What's unclear: Whether `${CLAUDE_PLUGIN_DATA}` also expands in a Claude command prompt's `Write` tool call path argument, or only in hook/MCP config files
   - Recommendation: In the wizard prompt, use `Bash` to resolve the path first (`echo "${CLAUDE_PLUGIN_DATA}"`), capture the result, then pass the absolute path to `Write`. This avoids any expansion ambiguity.

2. **`uv venv` Python version availability**
   - What we know: `uv venv --python 3.12` works when Python 3.12 is available on the system
   - What's unclear: What happens if the user only has Python 3.11 installed? pandas-ta 0.4.71b0 requires Python >=3.12
   - Recommendation: Add a Python version check to `install-deps.sh`. If 3.12 is not available, print a clear error with installation instructions instead of failing silently.

3. **`allowed-tools: AskUserQuestion` in command frontmatter**
   - What we know: `allowed-tools` in skill/command frontmatter grants those tools without per-call approval
   - What's unclear: Whether `AskUserQuestion` is a valid tool name in `allowed-tools` or if it requires a different format
   - Recommendation: Test with `claude --plugin-dir .` locally after creating `commands/initialize.md`. If the tool isn't recognized, fall back to Claude's default interactive behavior (it will ask questions anyway; the approval dialog just appears more frequently).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (standard Python; no config yet — greenfield) |
| Config file | `tests/pytest.ini` or `pyproject.toml` — Wave 0 creates this |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v --tb=short` |

**Note:** Phase 1 produces no executable Python code — only plugin scaffold files (JSON, markdown, shell script). Tests in this phase validate the shell script logic and JSON schema correctness, not trading logic.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLUG-06 | SessionStart hook shell script installs deps correctly | integration (shell) | `bash tests/test_install_deps.sh` | Wave 0 |
| PLUG-06 | Hash change triggers reinstall; no-change skips | unit (shell) | `bash tests/test_install_deps.sh` | Wave 0 |
| STATE-03 | config.json schema validates against pydantic model | unit (Python) | `pytest tests/test_config_schema.py -x` | Wave 0 |
| CMD-05 | config.json contains all required fields after wizard | manual smoke | Manual: run `/initialize`, check output file | N/A |
| PLUG-01 | Plugin structure validates cleanly | smoke | `claude plugin validate .` | Now (manual) |
| ALP-01/02/03 | .env template has correct variable names | unit (Python) | `pytest tests/test_env_template.py -x` | Wave 0 |

**Manual-only justification (CMD-05):** The wizard runs inside Claude Code's interactive session. Automating it would require a full Claude Code session harness — out of scope for Phase 1.

### Sampling Rate
- **Per task commit:** `claude plugin validate . && pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green + `claude plugin validate .` passes before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/pytest.ini` — configure test discovery root
- [ ] `tests/test_config_schema.py` — validates config.json schema with pydantic model; covers ALP-01/02/03, STATE-03
- [ ] `tests/test_env_template.py` — validates .env template has ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER
- [ ] `tests/test_install_deps.sh` — bash integration test for install-deps.sh diff logic; covers PLUG-06
- [ ] Framework install: `uv pip install pytest` — if pytest not present in venv

---

## Sources

### Primary (HIGH confidence)
- `https://code.claude.com/docs/en/plugins-reference` — Complete plugin manifest schema, hooks format, environment variables (CLAUDE_PLUGIN_ROOT, CLAUDE_PLUGIN_DATA), SessionStart dep install pattern, directory structure, validation commands
- `https://code.claude.com/docs/en/slash-commands` — Skill/command SKILL.md frontmatter fields (name, description, allowed-tools, disable-model-invocation, user-invocable, argument-hint), AskUserQuestion tool, invocation control table
- `https://code.claude.com/docs/en/plugin-marketplaces` — marketplace.json schema, plugin source types, GitHub source format
- `CLAUDE.md` (project file) — Full technology stack, alpaca-py 0.43.2, pandas-ta 0.4.71b0, APScheduler 3.x, uv, loguru — all HIGH confidence per prior research

### Secondary (MEDIUM confidence)
- `https://docs.pydantic.dev/latest/concepts/pydantic_settings/` — JsonConfigSettingsSource, SettingsConfigDict, json_file + env_file loading (verified via official pydantic docs)
- `https://medium.com/@wihlarkop/how-to-load-configuration-in-pydantic-3693d0ee81a3` — pydantic-settings JsonConfigSettingsSource code pattern (verified pattern matches official docs)
- `https://pydevtools.com/blog/claude-code-hooks-for-uv/` — uv + Claude Code hooks integration patterns (cross-verified with official hook docs)

### Tertiary (LOW confidence)
- Reddit/community sources on CLAUDE_ENV_FILE and SessionStart PATH issues — pattern noted in pitfalls, recommend testing in actual install

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages established in CLAUDE.md from prior research with verified PyPI versions
- Architecture: HIGH — directly from official Claude Code plugin documentation fetched 2026-03-21
- Pitfalls: MEDIUM — structural pitfalls are HIGH (from official troubleshooting docs); PATH/uv issues are MEDIUM (community-sourced, plausible)
- Config schema: HIGH — pydantic-settings JsonConfigSettingsSource pattern verified against official pydantic docs
- Test infrastructure: MEDIUM — standard pytest patterns for shell/Python; specific Claude Code wizard testing is manual-only

**Research date:** 2026-03-21
**Valid until:** 2026-06-21 (plugin API is stable; 90-day window is conservative)
