#!/bin/bash
# Wrapper script to launch the Alpaca MCP server with credentials from .env
# Used by: claude mcp add alpaca ... -- bash start-mcp.sh

# Resolve paths relative to this script's location (inside the plugin)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find the .env file: plugin's trading-bot/ subfolder first, then plugin root
if [ -f "$PLUGIN_ROOT/trading-bot/.env" ]; then
  ENV_FILE="$PLUGIN_ROOT/trading-bot/.env"
elif [ -f "$PLUGIN_ROOT/.env" ]; then
  ENV_FILE="$PLUGIN_ROOT/.env"
else
  echo "No .env file found. Add your Alpaca keys to $PLUGIN_ROOT/trading-bot/.env" >&2
  exit 1
fi

# Export vars from .env (skip comments and blank lines)
set -a
grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' | while IFS='=' read -r key value; do
  export "$key=$value"
done
set +a

# Source it directly too (handles quoting edge cases)
source "$ENV_FILE"

# Map ALPACA_PAPER to ALPACA_PAPER_TRADE (MCP server uses a different env var)
if [ -n "${ALPACA_PAPER:-}" ]; then
  export ALPACA_PAPER_TRADE="${ALPACA_PAPER}"
fi

exec uvx alpaca-mcp-server serve
