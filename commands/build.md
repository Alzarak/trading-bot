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

1. **Copy the directory to your server:**
   ```bash
   scp -r {output_dir} user@your-server:/path/to/trading-bot
   ```
   Or run it locally from the output directory.

2. **Set up your API credentials:**
   Create a `.env` file in the output directory:
   ```
   ALPACA_API_KEY=your_key_here
   ALPACA_SECRET_KEY=your_secret_here
   ALPACA_PAPER=true
   ```
   Get your API keys at: https://app.alpaca.markets/

3. **Install dependencies on your server:**
   ```bash
   pip install alpaca-py==0.43.2 pandas-ta==0.4.71b0 pandas numpy APScheduler loguru python-dotenv
   ```

4. **Run the bot:**
   ```bash
   cd trading-bot-standalone
   python bot.py
   ```

5. **Monitor logs:** The bot writes trade logs to `trades_YYYY-MM-DD.log` in the same directory.

If you want to run the bot directly from Claude Code instead, use `/run`.
