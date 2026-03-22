#!/bin/bash
# Wrapper script to launch the Alpaca MCP server with credentials from .env
# Used by: claude mcp add alpaca ... -- bash start-mcp.sh

# Find the .env file: project-level trading-bot/ first, then current directory
if [ -f "$(pwd)/trading-bot/.env" ]; then
  ENV_FILE="$(pwd)/trading-bot/.env"
elif [ -f "$(pwd)/.env" ]; then
  ENV_FILE="$(pwd)/.env"
else
  echo "No .env file found. Add your Alpaca keys to ./trading-bot/.env" >&2
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
