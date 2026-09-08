#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v rch >/dev/null 2>&1; then
  mkdir -p "$HOME/.local/bin"
  echo '#!/usr/bin/env bash' > "$HOME/.local/bin/rch"
  echo 'if [[ "$1" == "exec" && "$2" == "--" ]]; then shift 2; exec "$@"; fi' >> "$HOME/.local/bin/rch"
  echo 'if [[ "$1" == "status" || "$1" == "doctor" ]]; then echo "rch (CI shim: local execution)"; exit 0; fi' >> "$HOME/.local/bin/rch"
  echo 'exec "$@"' >> "$HOME/.local/bin/rch"
  chmod +x "$HOME/.local/bin/rch"
  export PATH="$HOME/.local/bin:$PATH"
fi

bash ./scripts/run_e2e_script_pack_gate.sh
