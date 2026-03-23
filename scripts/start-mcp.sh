#!/bin/bash
# Wrapper script to launch the Alpaca MCP server with credentials from .env
# Used by: claude mcp add alpaca ... -- bash start-mcp.sh

# Resolve paths: try the user's project directory (pwd) first,
# then fall back to the script's own location (plugin source/cache)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(pwd)"

# Find the .env file: user's project first, then plugin directory
if [ -f "$PROJECT_DIR/trading-bot/.env" ]; then
  ENV_FILE="$PROJECT_DIR/trading-bot/.env"
elif [ -f "$PROJECT_DIR/.env" ]; then
  ENV_FILE="$PROJECT_DIR/.env"
elif [ -f "$PLUGIN_ROOT/trading-bot/.env" ]; then
  ENV_FILE="$PLUGIN_ROOT/trading-bot/.env"
elif [ -f "$PLUGIN_ROOT/.env" ]; then
  ENV_FILE="$PLUGIN_ROOT/.env"
else
  echo "No .env file found. Add your Alpaca keys to $PROJECT_DIR/trading-bot/.env" >&2
  exit 1
fi

# Export all vars from .env (set -a makes source'd vars auto-export)
set -a
source "$ENV_FILE"
set +a

# Map ALPACA_PAPER to ALPACA_PAPER_TRADE (MCP server uses a different env var)
if [ -n "${ALPACA_PAPER:-}" ]; then
  export ALPACA_PAPER_TRADE="${ALPACA_PAPER}"
fi

exec uvx alpaca-mcp-server serve
