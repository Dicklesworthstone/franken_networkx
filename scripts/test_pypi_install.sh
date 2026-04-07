#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INDEX_URL="${INDEX_URL:-}"
EXTRA_INDEX_URL="${EXTRA_INDEX_URL:-}"
DIST_DIR="${DIST_DIR:-}"
PACKAGE_NAME="${PACKAGE_NAME:-franken-networkx}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv-pypi-smoke}"

rm -rf "$VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

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
