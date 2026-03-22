---
name: build
description: "This skill should be used when the user runs /build, wants to generate standalone trading bot scripts, or needs to create a deployable Python trading bot from their config."
---

Generate a standalone trading bot from the user's configuration. Fully automated — no questions needed.

## Pre-check

Verify config.json exists:

```bash
test -f "${CLAUDE_PLUGIN_DATA}/config.json" && echo "EXISTS" || echo "NOT_FOUND"
```

If NOT_FOUND: tell the user to run `/initialize` first. Stop.

## Run Generator

Read the config, then run the build generator:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" -c "
import json, sys
sys.path.insert(0, '.')
from scripts.build_generator import generate_build
from pathlib import Path

config = json.loads(Path('${CLAUDE_PLUGIN_DATA}/config.json').read_text())
output_dir = Path('${CLAUDE_PLUGIN_DATA}/trading-bot-standalone')
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

To run directly from Claude Code instead, use `/run`.
