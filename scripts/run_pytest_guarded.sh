#!/usr/bin/env bash
# scripts/run_pytest_guarded.sh — Safe, memory-guarded pytest runner for FrankenNetworkX.
#
# Prevents runaway memory leaks or infinite loops from threatening host stability (ts1).
# 1. Enforces OS virtual address space limit (ulimit -v).
# 2. Enforces maximum execution timeout.
# 3. Monitors system PSI (pressure stall info) for memory pressure.
# 4. Enforces in-process RSS memory ceiling via tests/python/conftest.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Virtual address space ceiling: default 16 GB (in KiB: 16 * 1024 * 1024 = 16777216)
VIRT_MEM_LIMIT_KB="${FNX_VIRT_MEM_LIMIT_KB:-16777216}"
# Per-session timeout: default 600s (10 minutes)
TIMEOUT_SECONDS="${FNX_TEST_TIMEOUT_SECS:-600}"
# In-process RSS limit in MB (checked by conftest.py): default 4096 MB (4 GB)
export FNX_TEST_MAX_RSS_MB="${FNX_TEST_MAX_RSS_MB:-4096}"

echo "[guarded-pytest] Setting virtual memory limit to $(( VIRT_MEM_LIMIT_KB / 1024 / 1024 )) GB..."
ulimit -v "${VIRT_MEM_LIMIT_KB}" || {
    echo "[guarded-pytest] Warning: Could not set ulimit -v (not supported on this environment)"
}

# Check system memory pressure before running
if [[ -f /proc/pressure/memory ]]; then
    PSI_SOME_10=$(awk '/some/ {split($2, a, "="); print a[2]}' /proc/pressure/memory 2>/dev/null || echo "0.0")
    echo "[guarded-pytest] Host memory PSI (10s avg): ${PSI_SOME_10}%"
fi

PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="$(which python3)"
fi

echo "[guarded-pytest] Running pytest with timeout ${TIMEOUT_SECONDS}s and RSS limit ${FNX_TEST_MAX_RSS_MB} MB..."
exec timeout --signal=KILL "${TIMEOUT_SECONDS}s" \
    "${PYTHON_BIN}" -m pytest "$@"
