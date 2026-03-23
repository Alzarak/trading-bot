#!/usr/bin/env bash
# SessionStart hook: Install Python dependencies if requirements.txt changed.
# Uses SHA256 hash comparison to skip unnecessary reinstalls.
set -e

# Ensure uv is in PATH (may be in user-level install dirs)
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

# Base directory: ~/.claude/trading-bot/ (installed by npx @alzarak/trading-bot)
INSTALL_DIR="$HOME/.claude/trading-bot"

# Data directory: project-level trading-bot/ folder
DATA_DIR="$(pwd)/trading-bot"
if [ ! -d "$DATA_DIR" ]; then
  DATA_DIR="$INSTALL_DIR"
fi

VENV_DIR="${DATA_DIR}/venv"
REQ_FILE="${INSTALL_DIR}/requirements.txt"
REQ_HASH_FILE="${DATA_DIR}/requirements.txt.sha256"

# Ensure data directory exists
mkdir -p "${DATA_DIR}"

# Guard: requirements.txt must exist before we try to hash it
if [ ! -f "${REQ_FILE}" ]; then
  echo "[trading-bot] requirements.txt not found at ${REQ_FILE}, skipping dependency install."
  exit 0
fi

# Compute current hash
CURRENT_HASH=$(sha256sum "${REQ_FILE}" | awk '{print $1}')
STORED_HASH=$(cat "${REQ_HASH_FILE}" 2>/dev/null || echo "")

if [ "${CURRENT_HASH}" != "${STORED_HASH}" ]; then
  echo "[trading-bot] Dependencies changed, installing..."

  # Check Python 3.12+ is available
  PYTHON_VERSION=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1)
  PYTHON_MAJOR=$(echo "${PYTHON_VERSION}" | cut -d. -f1)
  PYTHON_MINOR=$(echo "${PYTHON_VERSION}" | cut -d. -f2)

  if [ -z "${PYTHON_VERSION}" ] || [ "${PYTHON_MAJOR}" -lt 3 ] || ([ "${PYTHON_MAJOR}" -eq 3 ] && [ "${PYTHON_MINOR}" -lt 12 ]); then
    echo "[trading-bot] ERROR: Python 3.12+ required (found: ${PYTHON_VERSION:-none})"
    echo "[trading-bot] Install Python 3.12+: https://www.python.org/downloads/"
    exit 1
  fi

  # Check uv is available
  if ! command -v uv &> /dev/null; then
    echo "[trading-bot] ERROR: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi

  uv venv "${VENV_DIR}" --python python3 --quiet 2>/dev/null || uv venv "${VENV_DIR}" --quiet
  uv pip install -r "${REQ_FILE}" --python "${VENV_DIR}/bin/python" --quiet
  echo "${CURRENT_HASH}" > "${REQ_HASH_FILE}"
  echo "[trading-bot] Dependencies installed successfully."
else
  echo "[trading-bot] Dependencies up to date."
fi
