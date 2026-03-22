#!/bin/bash
# PreToolUse hook — intercepts Bash calls that invoke order submission scripts.
# Reads tool_input JSON from stdin. Denies if circuit breaker flag exists.
# IMPORTANT: All debug output to stderr (>&2). Only JSON decisions to stdout.
set -euo pipefail

INPUT=$(cat /dev/stdin)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only gate commands that invoke our trading scripts with order patterns
if ! echo "$COMMAND" | grep -qE "(submit_order|place_order|execute_trade|bot\.py.*--(order|trade|submit))"; then
  exit 0  # Not an order command — allow
fi

echo "Intercepted order command: $COMMAND" >&2

# Check circuit breaker flag file (written by risk_manager.py)
CB_FLAG="${CLAUDE_PLUGIN_DATA:-/tmp}/circuit_breaker.flag"
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

# Check PDT trades count (lightweight file-based check)
PDT_FILE="${CLAUDE_PLUGIN_DATA:-/tmp}/pdt_trades.json"
if [ -f "$PDT_FILE" ]; then
  # Count trades in last 7 days
  CUTOFF=$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d 2>/dev/null || echo "")
  if [ -n "$CUTOFF" ]; then
    COUNT=$(jq --arg cutoff "$CUTOFF" '[.[] | select(.date >= $cutoff)] | length' "$PDT_FILE" 2>/dev/null || echo "0")
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
fi

exit 0  # All checks passed — allow
