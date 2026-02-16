#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/e2e/latest"
STEPS_JSONL="$OUT_DIR/e2e_script_pack_steps_v1.jsonl"
REPORT_JSON="$OUT_DIR/e2e_script_pack_gate_report_v1.json"

mkdir -p "$OUT_DIR"
: > "$STEPS_JSONL"

RUN_ID="e2e-script-pack-gate-$(date -u +%Y%m%dT%H%M%SZ)"

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

append_step() {
  local step_id="$1"
  local step_label="$2"
  local command="$3"
  local status="$4"
  local reason_code="$5"
  local start_ms="$6"
  local end_ms="$7"
  local duration_ms="$8"
  local log_path="$9"
  python3 - "$STEPS_JSONL" "$RUN_ID" "$step_id" "$step_label" "$command" "$status" "$reason_code" "$start_ms" "$end_ms" "$duration_ms" "$log_path" <<'PY'
import json
import sys

(
    steps_path,
    run_id,
    step_id,
    step_label,
    command,
    status,
    reason_code,
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
    "reason_code": reason_code if reason_code else None,
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
  local command="$3"
  local slug
  slug="$(echo "$step_label" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_')"
  local log_path="$OUT_DIR/${step_id}_${slug}.log"
  local start_ms end_ms duration_ms status reason_code
  start_ms="$(now_ms)"

  if bash -lc "$command" >"$log_path" 2>&1; then
    status="passed"
    reason_code=""
  else
    status="failed"
    reason_code="command_failed"
  fi

  end_ms="$(now_ms)"
  duration_ms=$((end_ms - start_ms))
  append_step "$step_id" "$step_label" "$command" "$status" "$reason_code" "$start_ms" "$end_ms" "$duration_ms" "$log_path"

  if [[ "$status" != "passed" ]]; then
    echo "step failed: $step_id ($step_label) -> $log_path"
    return 1
  fi
}

TOTAL_STEPS=3
STEP=1

echo "[$STEP/$TOTAL_STEPS] Running deterministic E2E script pack (happy/edge/malformed)..."
run_step "step-$STEP" "run_e2e_script_pack" "python3 ./scripts/run_e2e_script_pack.py --scenario all --passes 2 --clear-output"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Validating E2E script pack artifacts..."
run_step "step-$STEP" "validate_e2e_script_pack" "python3 ./scripts/validate_e2e_script_pack.py --output $OUT_DIR/e2e_script_pack_validation_v1.json"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running targeted E2E script pack gate test..."
run_step "step-$STEP" "cargo_test_e2e_script_pack_gate" "rch exec -- cargo test -q -p fnx-conformance --test e2e_script_pack_gate -- --nocapture"

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
    "report_id": "e2e-script-pack-gate-report-v1",
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

echo "E2E script pack gate complete:"
echo "  steps:  $STEPS_JSONL"
echo "  report: $REPORT_JSON"
