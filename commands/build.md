---
name: build
description: "Generate standalone Python trading scripts from your config — ready to run on any server"
allowed-tools: Bash, Read, Write
---

You are generating a standalone trading bot from the user's configuration. This is a fully automated process — no questions needed.

## Pre-check

Use Bash to verify config.json exists at the plugin data directory:

```bash
test -f "${CLAUDE_PLUGIN_DATA}/config.json" && echo "EXISTS" || echo "NOT_FOUND"
```

If the output is "NOT_FOUND": tell the user — "No configuration found. Please run `/initialize` first to set up your trading preferences, then run `/build` again." Stop here.

## Read Config

Use Bash to read and display the configuration:

```bash
cat "${CLAUDE_PLUGIN_DATA}/config.json"
```

Note the selected strategies and key settings for your report.

## Run Generator

Use Bash to run the build generator:

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

Parse the JSON output to get `output_dir`, `files_generated`, and `strategies_included`.

## Report Results

Tell the user what was generated. Use this format:

---

**Trading bot generated successfully.**

**Output directory:** `{output_dir}`

**Files created:**
- List all files from `files_generated`

**Strategies included:**
- List all strategies from `strategies_included`

---

## Next Steps

Tell the user:

"Your standalone trading bot has been generated at: `{output_dir}`"

**Files generated:** List all files from `result["files_generated"]`

**Strategies included:** List all strategies from `result["strategies_included"]`

**To deploy on a server:**

1. **Copy the entire directory to your server:**
   ```bash
   scp -r {output_dir} user@your-server:/path/to/trading-bot
   ```
   Or run it locally from the output directory.

2. **Set up your API credentials:**
   ```bash
   cp .env.template .env
   # Edit .env and add your Alpaca API keys
   ```
   Get your keys at: https://app.alpaca.markets/

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   # Or with uv (faster): uv pip install -r requirements.txt
   ```

4. **Start the bot:**
   ```bash
   python bot.py
   ```
   Or use the included launcher script: `./run.sh`

5. **For unattended server operation:** See `DEPLOY.md` for cron and systemd setup examples that auto-restart the bot on reboot or failure.

6. **Monitor logs:** The bot writes structured logs via loguru. Check the `logs/` directory.

**Security reminder:** Your `.env` file will contain your API keys. The included `.gitignore` will prevent accidentally committing it to git. Never share your `.env` file.

**Paper trading note:** The bot defaults to paper trading mode (`ALPACA_PAPER=true` in your `.env`). To switch to live trading with real money, set `ALPACA_PAPER=false` in your `.env` file — only do this when you are confident in the bot's behavior.

If you want to run the bot directly from Claude Code instead, use `/run`.
