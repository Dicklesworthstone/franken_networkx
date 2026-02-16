#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/e2e/latest"
STEPS_JSONL="$OUT_DIR/e2e_script_pack_steps_v1.jsonl"
REPORT_JSON="$OUT_DIR/e2e_script_pack_gate_report_v1.json"
BUNDLE_INDEX_JSON="$OUT_DIR/e2e_script_pack_bundle_index_v1.json"

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

TOTAL_STEPS=4
STEP=1

echo "[$STEP/$TOTAL_STEPS] Running deterministic E2E script pack (core + asupersync recovery/fault scenarios)..."
run_step "step-$STEP" "run_e2e_script_pack" "python3 ./scripts/run_e2e_script_pack.py --scenario all --passes 2 --clear-output --gate-step-id step-1"
STEP=$((STEP + 1))

echo "Preparing bundle index artifact for gate assertions..."
python3 - "$OUT_DIR/e2e_script_pack_events_v1.jsonl" "$BUNDLE_INDEX_JSON" "$RUN_ID" <<'PY'
import json
import sys
from datetime import datetime, timezone

events_path, bundle_index_path, run_id = sys.argv[1:]
with open(events_path, "r", encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

PROFILE_FIRST_ARTIFACTS = {
    "baseline": "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    "hotspot": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
    "delta": "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
}
OPTIMIZATION_LEVER_POLICY = {
    "rule": "exactly_one_optimization_lever_per_change",
    "evidence_path": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
}
ALIEN_UPLIFT_CONTRACT_CARD = {
    "ev_score": 2.22,
    "baseline_comparator": "legacy_networkx/main@python3.12",
    "expected_value_statement": (
        "Deterministic failure envelopes + artifact index linkage reduce replay triage ambiguity."
    ),
}
DECISION_THEORETIC_RUNTIME_CONTRACT = {
    "states": ["accept", "validate", "fail_closed"],
    "actions": ["ingest_event", "publish_artifact_index", "emit_failure_envelope", "fail_closed"],
    "loss_model": (
        "Minimize expected replay divergence and diagnostic ambiguity while preserving deterministic ordering."
    ),
    "loss_budget": {
        "max_expected_loss": 0.02,
        "max_replay_loss": 0.0,
        "max_data_loss": 0.0,
    },
    "safe_mode_fallback": {
        "trigger_thresholds": {
            "missing_forensics_fields": 1,
            "artifact_index_resolution_failures": 1,
            "unexpected_failure_reason_codes": 1,
        },
        "fallback_action": "emit fail-closed diagnostics and halt publication of readiness artifacts",
        "budgeted_recovery_window_ms": 30000,
    },
}
ISOMORPHISM_PROOF_ARTIFACTS = [
    "artifacts/perf/phase2c/isomorphism_harness_report_v1.json",
    "artifacts/perf/phase2c/isomorphism_golden_signatures_v1.json",
]
STRUCTURED_LOGGING_EVIDENCE = [
    "artifacts/conformance/latest/structured_logs.jsonl",
    "artifacts/e2e/latest/e2e_script_pack_steps_v1.jsonl",
    "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
]
DEFAULT_RETENTION_POLICY = {
    "policy_id": "e2e-latest-retention-v1",
    "min_retention_days": 14,
    "storage_root": "artifacts/e2e/latest",
}


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


index_rows = {}
failure_index = []
gate_step_id = next(
    (
        row.get("gate_step_id")
        for row in events
        if isinstance(row.get("gate_step_id"), str) and row["gate_step_id"].strip()
    ),
    "step-1",
)
forensics_index_path = next(
    (
        row.get("forensics_index_path")
        for row in events
        if isinstance(row.get("forensics_index_path"), str) and row["forensics_index_path"].strip()
    ),
    bundle_index_path,
)
retention_policy = next(
    (row.get("retention_policy") for row in events if isinstance(row.get("retention_policy"), dict)),
    DEFAULT_RETENTION_POLICY,
)
for row in events:
    scenario_id = row["scenario_id"]
    pass_label = row["pass_label"]
    packet_id = row["packet_id"]
    evidence_refs = row.get("evidence_refs", {})
    index_rows.setdefault(
        scenario_id,
        {
            "scenario_id": scenario_id,
            "packet_id": packet_id,
            "bundle_id": row["bundle_id"],
            "stable_fingerprint": row["stable_fingerprint"],
            "gate_step_id": row.get("gate_step_id"),
            "forensics_index_path": row.get("forensics_index_path"),
            "retention_policy": row.get("retention_policy"),
            "manifests": {},
            "failure_envelopes": {},
            "parity_perf_raptorq_evidence": evidence_refs,
        },
    )
    index_rows[scenario_id]["manifests"][pass_label] = row["bundle_manifest_path"]
    index_rows[scenario_id]["failure_envelopes"][pass_label] = row["failure_envelope_path"]

    failure_envelope = load_json(row["failure_envelope_path"])
    if failure_envelope.get("status") == "failed":
        failure_index.append(
            {
                "scenario_id": scenario_id,
                "pass_label": pass_label,
                "reason_code": failure_envelope.get("reason_code"),
                "failure_envelope_path": row["failure_envelope_path"],
                "replay_bundle_manifest_path": failure_envelope.get(
                    "replay_bundle_manifest_path", row["bundle_manifest_path"]
                ),
                "gate_step_id": failure_envelope.get("gate_step_id", row.get("gate_step_id")),
                "forensics_index_path": failure_envelope.get(
                    "forensics_index_path", row.get("forensics_index_path")
                ),
                "retention_policy": failure_envelope.get(
                    "retention_policy", row.get("retention_policy")
                ),
                "replay_command": failure_envelope.get("replay_command"),
                "forensics_links": failure_envelope.get("forensics_links"),
                "parity_perf_raptorq_evidence": evidence_refs,
            }
        )

rows = []
for scenario_id in sorted(index_rows):
    row = index_rows[scenario_id]
    row["manifests"] = {
        pass_label: row["manifests"][pass_label] for pass_label in sorted(row["manifests"])
    }
    row["failure_envelopes"] = {
        pass_label: row["failure_envelopes"][pass_label]
        for pass_label in sorted(row["failure_envelopes"])
    }
    rows.append(row)

bundle_index = {
    "schema_version": "1.0.0",
    "artifact_id": "e2e-script-pack-bundle-index-v1",
    "run_id": run_id,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "gate_step_id": gate_step_id,
    "forensics_index_path": forensics_index_path,
    "retention_policy": retention_policy,
    "scenario_count": len(index_rows),
    "rows": rows,
    "failure_count": len(failure_index),
    "failure_index": sorted(
        failure_index,
        key=lambda row: (row["scenario_id"], row["pass_label"]),
    ),
    "profile_first_artifacts": PROFILE_FIRST_ARTIFACTS,
    "optimization_lever_policy": OPTIMIZATION_LEVER_POLICY,
    "alien_uplift_contract_card": ALIEN_UPLIFT_CONTRACT_CARD,
    "decision_theoretic_runtime_contract": DECISION_THEORETIC_RUNTIME_CONTRACT,
    "isomorphism_proof_artifacts": ISOMORPHISM_PROOF_ARTIFACTS,
    "structured_logging_evidence": STRUCTURED_LOGGING_EVIDENCE,
}
with open(bundle_index_path, "w", encoding="utf-8") as f:
    json.dump(bundle_index, f, indent=2)
    f.write("\n")
PY

echo "[$STEP/$TOTAL_STEPS] Validating E2E script pack artifacts..."
run_step "step-$STEP" "validate_e2e_script_pack" "python3 ./scripts/validate_e2e_script_pack.py --output $OUT_DIR/e2e_script_pack_validation_v1.json"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running replay drill from asupersync sidecar-mismatch baseline bundle manifest..."
run_step "step-$STEP" "replay_e2e_bundle_manifest" "python3 ./scripts/run_e2e_script_pack.py --replay-manifest $OUT_DIR/bundles/asupersync_sidecar_mismatch/baseline/bundle_manifest_v1.json --output-dir $OUT_DIR"
STEP=$((STEP + 1))

echo "[$STEP/$TOTAL_STEPS] Running targeted E2E script pack gate test..."
run_step "step-$STEP" "cargo_test_e2e_script_pack_gate" "rch exec -- cargo test -q -p fnx-conformance --test e2e_script_pack_gate -- --nocapture"

python3 - "$STEPS_JSONL" "$REPORT_JSON" "$BUNDLE_INDEX_JSON" "$RUN_ID" <<'PY'
import json
import sys
from datetime import datetime, timezone

steps_path, report_path, bundle_index_path, run_id = sys.argv[1:]
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
    "bundle_index_path": bundle_index_path,
    "failed_step_ids": [step["step_id"] for step in failed],
}
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
    f.write("\n")
PY

echo "E2E script pack gate complete:"
echo "  steps:  $STEPS_JSONL"
echo "  report: $REPORT_JSON"
echo "  bundles: $BUNDLE_INDEX_JSON"
