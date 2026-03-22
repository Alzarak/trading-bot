#!/bin/bash
# PreToolUse hook — intercepts Bash calls that invoke order submission scripts.
# Reads tool_input JSON from stdin. Denies if circuit breaker flag exists.
# IMPORTANT: All debug output to stderr (>&2). Only JSON decisions to stdout.
#
# Handles two execution contexts:
#   Plugin mode:  CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA are set by Claude Code
#   Dev mode:     Both env vars are unset; fall back to script's own parent directory
set -uo pipefail

# Resolve project root: use CLAUDE_PLUGIN_ROOT when available (plugin mode),
# otherwise derive from the script's location (dev mode — script lives in hooks/).
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

# Resolve data directory: prefer project-level trading-bot/ folder,
# fall back to CLAUDE_PLUGIN_DATA (plugin mode), then .plugin-data/ (dev mode).
if [ -d "$(pwd)/trading-bot" ]; then
  DATA_DIR="$(pwd)/trading-bot"
elif [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
  DATA_DIR="${CLAUDE_PLUGIN_DATA}"
else
  DATA_DIR="${PLUGIN_ROOT}/.plugin-data"
fi

# Circuit breaker flag path (written by risk_manager.py)
CB_FLAG="${DATA_DIR}/circuit_breaker.flag"

INPUT=$(cat /dev/stdin 2>/dev/null) || true
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || true

# If we couldn't parse a command, this isn't something we need to gate
if [ -z "$COMMAND" ]; then
  exit 0
fi

# Only gate commands that invoke our trading scripts with order patterns
if ! echo "$COMMAND" | grep -qE "(submit_order|place_order|execute_trade|bot\.py.*--(order|trade|submit))"; then
  exit 0  # Not an order command — allow
fi

echo "Intercepted order command: $COMMAND" >&2

# Check circuit breaker flag file (written by risk_manager.py)
if [ -f "$CB_FLAG" ]; then
  jq -n '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": "Circuit breaker is active. All trading halted. Delete the circuit_breaker.flag file to resume."
    }
  }'
  exit 0
fi

# Check PDT trades count — try SQLite first (Phase 3+), fall back to JSON
DB_FILE="${DATA_DIR}/trading.db"
PDT_FILE="${DATA_DIR}/pdt_trades.json"
CUTOFF=$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d 2>/dev/null || echo "")

if [ -n "$CUTOFF" ]; then
  COUNT=0
  if [ -f "$DB_FILE" ]; then
    # SQLite source (preferred — Phase 3 migrates PDT data here)
    COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM day_trades WHERE date >= '$CUTOFF';" 2>/dev/null || echo "0")
  elif [ -f "$PDT_FILE" ]; then
    # JSON fallback (pre-migration)
    COUNT=$(jq --arg cutoff "$CUTOFF" '[.[] | select(.date >= $cutoff)] | length' "$PDT_FILE" 2>/dev/null || echo "0")
  fi
  if [ "$COUNT" -ge 3 ] 2>/dev/null; then
    jq -n '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "PDT limit reached (3+ day trades in rolling 7-calendar-day window). Trade blocked to prevent Pattern Day Trader designation."
      }
    }'
    exit 0
  fi
fi

exit 0  # All checks passed — allow
