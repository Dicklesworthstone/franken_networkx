#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INDEX_URL="${INDEX_URL:-}"
EXTRA_INDEX_URL="${EXTRA_INDEX_URL:-}"
DIST_DIR="${DIST_DIR:-}"
PACKAGE_NAME="${PACKAGE_NAME:-franken-networkx}"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi
VENV_DIR="${VENV_DIR:-.venv-pypi-smoke}"

rm -rf "$VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
if [[ -f "$VENV_DIR/bin/activate" ]]; then
  source "$VENV_DIR/bin/activate"
elif [[ -f "$VENV_DIR/Scripts/activate" ]]; then
  source "$VENV_DIR/Scripts/activate"
else
  echo "Error: cannot find venv activation script"
  exit 1
fi

python -m pip install --upgrade pip

install_cmd=(python -m pip install)
if [[ -n "$INDEX_URL" ]]; then
  install_cmd+=(--index-url "$INDEX_URL")
fi
if [[ -n "$EXTRA_INDEX_URL" ]]; then
  install_cmd+=(--extra-index-url "$EXTRA_INDEX_URL")
fi
if [[ -n "$DIST_DIR" ]]; then
  install_cmd+=(--find-links "$DIST_DIR")
fi
install_cmd+=("$PACKAGE_NAME")

"${install_cmd[@]}"

python - <<'PY'
import franken_networkx as fnx

graph = fnx.path_graph(5)
path = fnx.shortest_path(graph, 0, 4)
assert path == [0, 1, 2, 3, 4], path
print("smoke_ok", path)
PY
