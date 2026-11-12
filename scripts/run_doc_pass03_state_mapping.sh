#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/docs/latest"
STEPS_JSONL="$OUT_DIR/doc_pass03_e2e_steps_v1.jsonl"
REPORT_JSON="$OUT_DIR/doc_pass03_e2e_report_v1.json"

mkdir -p "$OUT_DIR"
: > "$STEPS_JSONL"

RUN_ID="doc-pass03-$(date -u +%Y%m%dT%H%M%SZ)"

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

append_step() {
  local step_id="$1"
  local step_label="$2"
  local cmd="$3"
  local status="$4"
  local reason="$5"
  local start_ms="$6"
  local end_ms="$7"
  local duration_ms="$8"
  local log_path="$9"
  python3 - "$STEPS_JSONL" "$RUN_ID" "$step_id" "$step_label" "$cmd" "$status" "$reason" "$start_ms" "$end_ms" "$duration_ms" "$log_path" <<'PY'
import json
import sys

(
    steps_path,
    run_id,
    step_id,
    step_label,
    command,
    status,
    reason,
    start_ms,
    end_ms,
    duration_ms,
    log_path,
) = sys.argv[1:]

row = {
    "schema_version": "1.0.0",
    "run_id": run_id,
    "step_id": step_id,
    "step_label": step_label,
    "command": command,
    "status": status,
    "reason_code": reason if reason else None,
    "start_unix_ms": int(start_ms),
    "end_unix_ms": int(end_ms),
    "duration_ms": int(duration_ms),
    "artifact_log_path": log_path,
}
with open(steps_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
PY
}

run_step() {
  local step_id="$1"
  local step_label="$2"
  local cmd="$3"
  local slug
  slug="$(echo "$step_label" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_')"
  local log_path="$OUT_DIR/${step_id}_${slug}.log"
  local start_ms end_ms duration_ms status reason
  start_ms="$(now_ms)"

  if bash -lc "$cmd" >"$log_path" 2>&1; then
    status="passed"
    reason=""
  else
    status="failed"
    reason="command_failed"
  fi

  end_ms="$(now_ms)"
  duration_ms=$((end_ms - start_ms))
  append_step "$step_id" "$step_label" "$cmd" "$status" "$reason" "$start_ms" "$end_ms" "$duration_ms" "$log_path"

  if [[ "$status" != "passed" ]]; then
    echo "step failed: $step_id ($step_label) -> $log_path"
    return 1
  fi
}

TOTAL_STEPS=3
STEP=1

echo "[$STEP/$TOTAL_STEPS] Generating DOC-PASS-03 state mapping artifact..."
run_step "step-$STEP" "generate_doc_pass03_state_mapping" "./scripts/generate_doc_pass03_state_mapping.py"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Validating DOC-PASS-03 state mapping artifact..."
run_step "step-$STEP" "validate_doc_pass03_state_mapping" "./scripts/validate_doc_pass03_state_mapping.py --output $OUT_DIR/doc_pass03_state_mapping_validation_v1.json"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running targeted DOC-PASS-03 gate test..."
run_step "step-$STEP" "cargo_test_doc_pass03_gate" "CARGO_TARGET_DIR=target-codex cargo test -q -p fnx-conformance --test doc_pass03_data_model_gate -- --nocapture"

python3 - "$STEPS_JSONL" "$REPORT_JSON" "$RUN_ID" <<'PY'
import json
import sys
from datetime import datetime, timezone

steps_path, report_path, run_id = sys.argv[1:]
with open(steps_path, "r", encoding="utf-8") as f:
    steps = [json.loads(line) for line in f if line.strip()]
failed = [step for step in steps if step["status"] != "passed"]

report = {
    "schema_version": "1.0.0",
    "report_id": "doc-pass03-e2e-report-v1",
    "run_id": run_id,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "step_count": len(steps),
    "failed_step_count": len(failed),
    "status": "pass" if not failed else "fail",
    "steps_log_path": steps_path,
    "failed_step_ids": [step["step_id"] for step in failed],
}
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
    f.write("\n")
PY

echo "DOC-PASS-03 e2e complete:"
echo "  steps:  $STEPS_JSONL"
echo "  report: $REPORT_JSON"
