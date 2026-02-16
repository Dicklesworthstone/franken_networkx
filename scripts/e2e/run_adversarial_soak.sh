#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python3 ./scripts/run_e2e_script_pack.py \
  --scenario adversarial_soak \
  --passes 2 \
  --soak-cycles 4 \
  --soak-checkpoint-interval-ms 15000
