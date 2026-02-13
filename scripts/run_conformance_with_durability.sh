#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/7] Capturing oracle-backed fixtures..."
./scripts/capture_oracle_fixtures.py

echo "[2/7] Running conformance harness..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke

REPORT_PATH="artifacts/conformance/latest/smoke_report.json"
LOG_PATH="artifacts/conformance/latest/structured_logs.jsonl"
SIDECAR_PATH="artifacts/conformance/latest/smoke_report.raptorq.json"
LOG_SIDECAR_PATH="artifacts/conformance/latest/structured_logs.raptorq.json"
RECOVERED_PATH="artifacts/conformance/latest/smoke_report.recovered.json"
LOG_RECOVERED_PATH="artifacts/conformance/latest/structured_logs.recovered.json"
PIPELINE_REPORT_PATH="artifacts/conformance/latest/durability_pipeline_report.json"

echo "[3/7] Generating durability sidecar for report..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  generate "$REPORT_PATH" "$SIDECAR_PATH" "smoke_report" "conformance_report" 1400 6

echo "[4/7] Generating durability sidecar for structured logs..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  generate "$LOG_PATH" "$LOG_SIDECAR_PATH" "structured_logs" "conformance_logs" 1400 6

echo "[5/7] Running scrub verification..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  scrub "$REPORT_PATH" "$SIDECAR_PATH"

echo "[6/7] Running decode drill for report..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  decode-drill "$SIDECAR_PATH" "$RECOVERED_PATH"

echo "[7/7] Running decode drill for structured logs..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  decode-drill "$LOG_SIDECAR_PATH" "$LOG_RECOVERED_PATH"

echo "Pipeline complete:"
echo "  report:   $REPORT_PATH"
echo "  logs:     $LOG_PATH"
echo "  sidecar:  $SIDECAR_PATH"
echo "  log_sidecar:$LOG_SIDECAR_PATH"
echo "  recovered:$RECOVERED_PATH"
echo "  log_recovered:$LOG_RECOVERED_PATH"

python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

report_path = Path("artifacts/conformance/latest/durability_pipeline_report.json")
entries = [
    {
        "artifact_path": "artifacts/conformance/latest/smoke_report.json",
        "sidecar_path": "artifacts/conformance/latest/smoke_report.raptorq.json",
        "recovered_path": "artifacts/conformance/latest/smoke_report.recovered.json",
    },
    {
        "artifact_path": "artifacts/conformance/latest/structured_logs.jsonl",
        "sidecar_path": "artifacts/conformance/latest/structured_logs.raptorq.json",
        "recovered_path": "artifacts/conformance/latest/structured_logs.recovered.json",
    },
]

materialized = []
for item in entries:
    sidecar = json.loads(Path(item["sidecar_path"]).read_text(encoding="utf-8"))
    materialized.append(
        {
            **item,
            "artifact_id": sidecar.get("artifact_id"),
            "artifact_type": sidecar.get("artifact_type"),
            "source_hash": sidecar.get("source_hash"),
            "scrub_status": sidecar.get("scrub", {}).get("status"),
            "decode_proof_count": len(sidecar.get("decode_proofs", [])),
            "repair_symbols": sidecar.get("raptorq", {}).get("repair_symbols"),
            "packet_count": len(sidecar.get("raptorq", {}).get("packets_b64", [])),
        }
    )

payload = {
    "suite": "conformance",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "entries": materialized,
}
report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"  durability_report:{report_path}")
PY
