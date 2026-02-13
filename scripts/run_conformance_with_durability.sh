#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Capturing oracle-backed fixtures..."
./scripts/capture_oracle_fixtures.py

echo "[2/5] Running conformance harness..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke

REPORT_PATH="artifacts/conformance/latest/smoke_report.json"
SIDECAR_PATH="artifacts/conformance/latest/smoke_report.raptorq.json"
RECOVERED_PATH="artifacts/conformance/latest/smoke_report.recovered.json"

echo "[3/5] Generating durability sidecar..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  generate "$REPORT_PATH" "$SIDECAR_PATH" "smoke_report" "conformance_report" 1400 6

echo "[4/5] Running scrub verification..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  scrub "$REPORT_PATH" "$SIDECAR_PATH"

echo "[5/5] Running decode drill..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  decode-drill "$SIDECAR_PATH" "$RECOVERED_PATH"

echo "Pipeline complete:"
echo "  report:   $REPORT_PATH"
echo "  sidecar:  $SIDECAR_PATH"
echo "  recovered:$RECOVERED_PATH"
