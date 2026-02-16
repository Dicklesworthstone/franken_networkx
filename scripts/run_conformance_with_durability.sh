#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TOTAL_STEPS=17
step=1

echo "[$step/$TOTAL_STEPS] Capturing oracle-backed fixtures..."
./scripts/capture_oracle_fixtures.py
step=$((step + 1))

echo "[$step/$TOTAL_STEPS] Running conformance harness..."
rch exec -- env CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke
step=$((step + 1))

REPORT_PATH="artifacts/conformance/latest/smoke_report.json"
LOG_PATH="artifacts/conformance/latest/structured_logs.jsonl"
NORMALIZATION_PATH="artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
MATRIX_PATH="artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json"
SIDECAR_PATH="artifacts/conformance/latest/smoke_report.raptorq.json"
LOG_SIDECAR_PATH="artifacts/conformance/latest/structured_logs.raptorq.json"
NORMALIZATION_SIDECAR_PATH="artifacts/conformance/latest/structured_log_emitter_normalization_report.raptorq.json"
MATRIX_SIDECAR_PATH="artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.raptorq.json"
RECOVERED_PATH="artifacts/conformance/latest/smoke_report.recovered.json"
LOG_RECOVERED_PATH="artifacts/conformance/latest/structured_logs.recovered.json"
NORMALIZATION_RECOVERED_PATH="artifacts/conformance/latest/structured_log_emitter_normalization_report.recovered.json"
MATRIX_RECOVERED_PATH="artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.recovered.json"
PIPELINE_REPORT_PATH="artifacts/conformance/latest/durability_pipeline_report.json"
RELIABILITY_REPORT_PATH="artifacts/conformance/latest/reliability_budget_report_v1.json"
FLAKE_QUARANTINE_PATH="artifacts/conformance/latest/flake_quarantine_v1.json"
RELIABILITY_VALIDATION_PATH="artifacts/conformance/latest/reliability_budget_gate_validation_v1.json"
FINAL_GATE_REPORT_PATH="artifacts/conformance/latest/logging_final_gate_report_v1.json"
FINAL_CHECKLIST_PATH="artifacts/conformance/latest/logging_release_checklist_v1.md"

ARTIFACT_SPECS=(
  "$REPORT_PATH|$SIDECAR_PATH|$RECOVERED_PATH|smoke_report|conformance_report"
  "$LOG_PATH|$LOG_SIDECAR_PATH|$LOG_RECOVERED_PATH|structured_logs|conformance_logs"
  "$NORMALIZATION_PATH|$NORMALIZATION_SIDECAR_PATH|$NORMALIZATION_RECOVERED_PATH|structured_log_emitter_normalization_report|conformance_logs"
  "$MATRIX_PATH|$MATRIX_SIDECAR_PATH|$MATRIX_RECOVERED_PATH|telemetry_dependent_unblock_matrix_v1|conformance_logs"
)

for spec in "${ARTIFACT_SPECS[@]}"; do
  IFS='|' read -r artifact_path sidecar_path _recovered_path artifact_id artifact_type <<< "$spec"
  echo "[$step/$TOTAL_STEPS] Generating durability sidecar for $artifact_id..."
  rch exec -- env CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
    generate "$artifact_path" "$sidecar_path" "$artifact_id" "$artifact_type" 1400 6
  step=$((step + 1))
done

for spec in "${ARTIFACT_SPECS[@]}"; do
  IFS='|' read -r artifact_path sidecar_path _recovered_path artifact_id _artifact_type <<< "$spec"
  echo "[$step/$TOTAL_STEPS] Running scrub verification for $artifact_id..."
  rch exec -- env CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
    scrub "$artifact_path" "$sidecar_path"
  step=$((step + 1))
done

for spec in "${ARTIFACT_SPECS[@]}"; do
  IFS='|' read -r _artifact_path sidecar_path recovered_path artifact_id _artifact_type <<< "$spec"
  echo "[$step/$TOTAL_STEPS] Running decode drill for $artifact_id..."
  rch exec -- env CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
    decode-drill "$sidecar_path" "$recovered_path"
  step=$((step + 1))
done

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
    {
        "artifact_path": "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
        "sidecar_path": "artifacts/conformance/latest/structured_log_emitter_normalization_report.raptorq.json",
        "recovered_path": "artifacts/conformance/latest/structured_log_emitter_normalization_report.recovered.json",
    },
    {
        "artifact_path": "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json",
        "sidecar_path": "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.raptorq.json",
        "recovered_path": "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.recovered.json",
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

echo "[$step/$TOTAL_STEPS] Generating reliability budget gate artifacts..."
python3 ./scripts/generate_reliability_budget_gate_report.py
step=$((step + 1))

echo "[$step/$TOTAL_STEPS] Validating reliability budget gate artifacts..."
python3 ./scripts/validate_reliability_budget_gate.py --output "$RELIABILITY_VALIDATION_PATH"
step=$((step + 1))

echo "[$step/$TOTAL_STEPS] Generating final logging gate report..."
python3 ./scripts/generate_logging_gate_report.py

echo "Pipeline complete:"
echo "  report:   $REPORT_PATH"
echo "  logs:     $LOG_PATH"
echo "  normalization:$NORMALIZATION_PATH"
echo "  unblock_matrix:$MATRIX_PATH"
echo "  sidecar:  $SIDECAR_PATH"
echo "  log_sidecar:$LOG_SIDECAR_PATH"
echo "  normalization_sidecar:$NORMALIZATION_SIDECAR_PATH"
echo "  unblock_matrix_sidecar:$MATRIX_SIDECAR_PATH"
echo "  recovered:$RECOVERED_PATH"
echo "  log_recovered:$LOG_RECOVERED_PATH"
echo "  normalization_recovered:$NORMALIZATION_RECOVERED_PATH"
echo "  unblock_matrix_recovered:$MATRIX_RECOVERED_PATH"
echo "  durability_report:$PIPELINE_REPORT_PATH"
echo "  reliability_report:$RELIABILITY_REPORT_PATH"
echo "  flake_quarantine:$FLAKE_QUARANTINE_PATH"
echo "  reliability_validation:$RELIABILITY_VALIDATION_PATH"
echo "  final_gate_report:$FINAL_GATE_REPORT_PATH"
echo "  final_release_checklist:$FINAL_CHECKLIST_PATH"
