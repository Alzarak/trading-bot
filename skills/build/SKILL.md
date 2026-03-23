---
name: build
description: "This skill should be used when the user runs /trading-bot:build, wants to generate bot trading bot scripts, or needs to create a deployable Python trading bot from their config."
---

Generate a bot trading bot from the user's configuration. Fully automated — no questions needed.

## Pre-check — Required Files

Verify the trading bot folder and required files from `/trading-bot:initialize` exist:

```bash
BOT_DIR="$(pwd)/trading-bot"
MISSING=""

if [ ! -d "${BOT_DIR}" ]; then
  MISSING="trading-bot folder"
fi

if [ ! -f "${BOT_DIR}/config.json" ] || [ "$(cat "${BOT_DIR}/config.json" 2>/dev/null)" = "{}" ]; then
  MISSING="${MISSING:+${MISSING}, }config.json (empty or missing)"
fi

if [ ! -f "${BOT_DIR}/setup-context.md" ] || [ ! -s "${BOT_DIR}/setup-context.md" ]; then
  MISSING="${MISSING:+${MISSING}, }setup-context.md (empty or missing)"
fi

if [ -n "$MISSING" ]; then
  echo "MISSING: ${MISSING}"
else
  echo "ALL_FOUND"
fi
```

**If MISSING:** Stop and tell the user:
"The build command needs files from the setup wizard. Missing: {list what's missing}. Please run `/trading-bot:initialize` first to configure your bot."

Do NOT proceed with the build if any required files are missing.

## Load Context

Read these files to understand the project and what to build:

1. Read `CLAUDE.md` in the current project root for project architecture, constraints, and conventions
2. Read `./trading-bot/config.json` for structured configuration values
3. Read `./trading-bot/setup-context.md` for the full setup plan and build instructions

The CLAUDE.md contains the project architecture, key invariants, and technical constraints. The setup-context.md contains the user's profile, strategy decisions, and explicit build instructions written by the initialize step. Follow those instructions.

## Run Generator

Read the config, then run the build generator:

**Path resolution:** Always use these exact variables. Do NOT use `$HOME/.claude/` — the install may be local (`./.claude/`).

```bash
BOT_DIR="$(pwd)/trading-bot"
VENV_PYTHON="${BOT_DIR}/venv/bin/python"
INSTALL_DIR="$(pwd)/.claude/trading-bot"

cd "${INSTALL_DIR}" && "${VENV_PYTHON}" -c "
import json, sys
sys.path.insert(0, '.')
from scripts.build_generator import generate_build
from pathlib import Path

config = json.loads(Path('${BOT_DIR}/config.json').read_text())
output_dir = Path('${BOT_DIR}/bot')
result = generate_build(config, output_dir)
print(json.dumps(result, indent=2))
"
```

## Report Results

After the generator runs, display a clear summary so the user knows exactly what was built:

1. **What was built**: Explain that a bot, self-contained trading bot was generated in `./trading-bot/bot/` — this is separate from the installed scripts in `.claude/` and can run independently on any machine.
2. **Files created**: List each file with a one-line description of its role (e.g., `bot.py` — main entry point, `risk_manager.py` — circuit breaker + PDT + position sizing, etc.)
3. **Configuration baked in**: Show which strategies, risk limits, and discovery mode were included based on their config.
4. **How to run it**: Explain the two ways to use it:
   - **From Claude Code**: `/trading-bot:run` (agent mode — Claude analyzes markets interactively)
   - **Standalone on any server**: Copy `bot/` to a server, set up `.env`, run `python bot.py`

## Next Steps

Tell the user:

"**Next step:** Type `/clear` to reset the conversation context, then run `/trading-bot:run` to start autonomous trading. Clearing first gives the run step a clean context — your bot scripts are built and ready to go."

**Security reminder:** `.env` contains API keys. The `.gitignore` prevents accidental commits. Bot defaults to paper trading (`ALPACA_PAPER=true`).
