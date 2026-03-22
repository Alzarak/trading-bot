#!/bin/bash
# Stop hook — checks if a trading session was active and warns about open positions.
# Uses exit 0 with JSON output for control decisions.
set -uo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-${PLUGIN_ROOT}/.plugin-data}"

DB_FILE="${DATA_DIR}/trading.db"
CB_FLAG="${DATA_DIR}/circuit_breaker.flag"

# If no database exists, no trading has occurred — allow stop
if [ ! -f "$DB_FILE" ]; then
  exit 0
fi

WARNINGS=""

# Check for circuit breaker — warn user it's still active
if [ -f "$CB_FLAG" ]; then
  WARNINGS="${WARNINGS}Circuit breaker is active. "
fi

# Check for open positions in state store
OPEN_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM positions WHERE status = 'open';" 2>/dev/null || echo "0")

if [ "$OPEN_COUNT" -gt 0 ]; then
  WARNINGS="${WARNINGS}${OPEN_COUNT} open position(s) detected — verify stop-losses are in place. "
fi

# If warnings exist, send them as context but allow stopping
if [ -n "$WARNINGS" ]; then
  echo "{\"decision\": \"allow\", \"reason\": \"${WARNINGS}\"}"
  exit 0
fi

exit 0
