#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/phase2c/latest"
STEPS_JSONL="$OUT_DIR/phase2c_readiness_e2e_steps_v1.jsonl"
REPORT_JSON="$OUT_DIR/phase2c_readiness_e2e_report_v1.json"

mkdir -p "$OUT_DIR"
: > "$STEPS_JSONL"

RUN_ID="phase2c-readiness-$(date -u +%Y%m%dT%H%M%SZ)"
FAIL_COUNT=0

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

append_step_json() {
  local step_id="$1"
  local step_label="$2"
  local cmd="$3"
  local status="$4"
  local reason_code="$5"
  local start_ms="$6"
  local end_ms="$7"
  local duration_ms="$8"
  local log_path="$9"
  python3 - "$STEPS_JSONL" "$RUN_ID" "$step_id" "$step_label" "$cmd" "$status" "$reason_code" "$start_ms" "$end_ms" "$duration_ms" "$log_path" <<'PY'
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
  local cmd="$3"
  local slug
  slug="$(echo "$step_label" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_')"
  local step_log="$OUT_DIR/${step_id}_${slug}.log"
  local start_ms end_ms duration_ms status reason_code
  start_ms="$(now_ms)"

  if bash -lc "$cmd" >"$step_log" 2>&1; then
    status="passed"
    reason_code=""
  else
    status="failed"
    reason_code="command_failed"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi

  end_ms="$(now_ms)"
  duration_ms=$((end_ms - start_ms))

  append_step_json "$step_id" "$step_label" "$cmd" "$status" "$reason_code" "$start_ms" "$end_ms" "$duration_ms" "$step_log"

  if [[ "$status" == "failed" ]]; then
    echo "step $step_id failed: $step_label (see $step_log)"
    return 1
  fi
}

TOTAL_STEPS=10
STEP=1

echo "[$STEP/$TOTAL_STEPS] Regenerating deterministic Phase2C packet artifacts..."
run_step "step-$STEP" "generate_packet_artifacts" "./scripts/generate_phase2c_packet_artifacts.py"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Validating packet artifact topology..."
run_step "step-$STEP" "validate_packet_artifacts" "./scripts/validate_phase2c_artifacts.py --output $OUT_DIR/phase2c_packet_artifact_validation_v1.json"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Validating security compatibility contracts..."
run_step "step-$STEP" "validate_security_contracts" "./scripts/validate_phase2c_security_contracts.py --output $OUT_DIR/phase2c_security_contract_validation_v1.json"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Validating essence extraction ledger..."
run_step "step-$STEP" "validate_essence_ledger" "./scripts/validate_phase2c_essence_ledger.py --output $OUT_DIR/phase2c_essence_ledger_validation_v1.json"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running deterministic E2E script pack gate (includes asupersync recovery/fault scenarios)..."
run_step "step-$STEP" "run_e2e_script_pack_gate" "bash ./scripts/run_e2e_script_pack_gate.sh"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running asupersync fault-injection contract gate..."
run_step "step-$STEP" "cargo_test_asupersync_fault_injection_gate" "rch exec -- cargo test -q -p fnx-conformance --test asupersync_fault_injection_gate -- --nocapture"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running asupersync adapter state-machine contract gate..."
run_step "step-$STEP" "cargo_test_asupersync_state_machine_gate" "rch exec -- cargo test -q -p fnx-conformance --test asupersync_adapter_state_machine_gate -- --nocapture"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running asupersync performance characterization gate..."
run_step "step-$STEP" "cargo_test_asupersync_performance_gate" "rch exec -- cargo test -q -p fnx-conformance --test asupersync_performance_gate -- --nocapture"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running focused readiness packet gate tests..."
run_step "step-$STEP" "cargo_test_phase2c_gate" "rch exec -- cargo test -q -p fnx-conformance --test phase2c_packet_readiness_gate -- --nocapture"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running smoke harness to emit deterministic packet logs..."
run_step "step-$STEP" "run_smoke_harness" "rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/conformance_harness_strict.json --mode strict"

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
    "report_id": "phase2c-readiness-e2e-report-v1",
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

echo "Phase2C readiness e2e complete:"
echo "  steps:  $STEPS_JSONL"
echo "  report: $REPORT_JSON"
