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
if command -v uv &>/dev/null; then
  uv venv --python "$PYTHON_BIN" --seed "$VENV_DIR"
else
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
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
import networkx as nx

graph = fnx.path_graph(5)
path = fnx.shortest_path(graph, 0, 4)
assert path == [0, 1, 2, 3, 4], path

# Test karate club graph
kg = fnx.karate_club_graph()
assert len(kg) == 34
assert kg.number_of_edges() == 78

# Test backend dispatch
k_nx = nx.karate_club_graph()
sp_nx = nx.shortest_path(k_nx, 0, 33, backend="franken_networkx")
assert sp_nx[0] == 0 and sp_nx[-1] == 33

print("smoke_ok", path, "karate_nodes:", len(kg), "backend_dispatch:", sp_nx)
PY

