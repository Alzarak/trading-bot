---
name: build
description: "This skill should be used when the user runs /trading-bot:build, wants to generate standalone trading bot scripts, or needs to create a deployable Python trading bot from their config."
---

Generate a standalone trading bot from the user's configuration. Fully automated — no questions needed.

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

Read both files to understand what to build:

1. Read `./trading-bot/config.json` for structured configuration values
2. Read `./trading-bot/setup-context.md` for the full setup plan and build instructions

The setup-context.md contains the user's profile, strategy decisions, and explicit build instructions written by the initialize step. Follow those instructions.

## Run Generator

Read the config, then run the build generator:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" -c "
import json, sys
sys.path.insert(0, '.')
from scripts.build_generator import generate_build
from pathlib import Path

config = json.loads(Path('./trading-bot/config.json').resolve().read_text())
output_dir = Path('./trading-bot/standalone').resolve()
result = generate_build(config, output_dir)
print(json.dumps(result, indent=2))
"
```

## Report Results

Display:
- Output directory path
- Files created (from `files_generated`)
- Strategies included

## Next Steps

Provide deployment instructions:

1. Copy directory to server: `scp -r {output_dir} user@server:/path/`
2. Set up API credentials: `cp .env.template .env` and edit
3. Install deps: `pip install -r requirements.txt` (or `uv pip install`)
4. Start bot: `python bot.py`
5. For unattended operation: see `DEPLOY.md` for systemd setup
6. Monitor logs in `logs/` directory

**Security reminder:** `.env` contains API keys. The `.gitignore` prevents accidental commits. Bot defaults to paper trading (`ALPACA_PAPER=true`).

To run directly from Claude Code instead, use `/trading-bot:run`.
