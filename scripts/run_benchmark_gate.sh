#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v rch >/dev/null 2>&1; then
  CARGO_WRAPPER="${CARGO_WRAPPER:-rch exec -- cargo}"
  CARGO_RUNNER=(rch exec -- env CARGO_TARGET_DIR=target-codex cargo)
else
  CARGO_WRAPPER="${CARGO_WRAPPER:-cargo}"
  CARGO_RUNNER=(env CARGO_TARGET_DIR=target-codex cargo)
fi

if [[ -n "${FNX_PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$FNX_PYTHON_BIN"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

MATRIX_ARTIFACT="artifacts/perf/phase2c/perf_baseline_matrix_v1.json"
MATRIX_EVENTS="artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl"
HOTSPOT_BACKLOG="artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json"
ISOMORPHISM_REPORT="artifacts/perf/phase2c/isomorphism_harness_report_v1.json"
REGRESSION_REPORT="artifacts/perf/phase2c/perf_regression_gate_report_v1.json"
SLO_THRESHOLDS="artifacts/perf/slo_thresholds.json"
SLO_REPORT="artifacts/perf/latest/slo_gate_report_v1.json"
BASELINE_COMPARATOR="artifacts/perf/latest/perf_baseline_matrix_baseline_comparator_v1.json"
LATEST_ARTIFACT="artifacts/perf/latest/perf_baseline_matrix_v1.json"
SIDECAR="artifacts/perf/latest/perf_baseline_matrix_v1.raptorq.json"
RECOVERED="artifacts/perf/latest/perf_baseline_matrix_v1.recovered.json"
PIPELINE_REPORT="artifacts/perf/latest/durability_pipeline_report.json"

mkdir -p "$(dirname "$LATEST_ARTIFACT")"
if [[ ! -f "$MATRIX_ARTIFACT" ]]; then
  echo "missing baseline matrix artifact: $MATRIX_ARTIFACT" >&2
  exit 1
fi
cp "$MATRIX_ARTIFACT" "$BASELINE_COMPARATOR"

echo "[1/4] Running phase2c performance baseline matrix..."
./scripts/run_perf_baseline_matrix.py \
  --artifact "$MATRIX_ARTIFACT" \
  --events-jsonl "$MATRIX_EVENTS" \
  --runs 5 \
  --warmup 1 \
  --target-dir target-codex \
  --cargo-wrapper "$CARGO_WRAPPER"

./scripts/generate_perf_hotspot_backlog.py \
  --matrix "$MATRIX_ARTIFACT" \
  --events "$MATRIX_EVENTS" \
  --output "$HOTSPOT_BACKLOG"

python3 scripts/run_perf_isomorphism_harness.py \
  --matrix "$MATRIX_ARTIFACT" \
  --report "$ISOMORPHISM_REPORT"

cp "$MATRIX_ARTIFACT" "$LATEST_ARTIFACT"

python3 scripts/run_perf_regression_gate.py \
  --baseline "$BASELINE_COMPARATOR" \
  --candidate "$LATEST_ARTIFACT" \
  --hotspot-backlog "$HOTSPOT_BACKLOG" \
  --report "$REGRESSION_REPORT"

echo "[2/4] Running perf SLO gate..."
python3 scripts/run_perf_slo_gate.py \
  --slo-thresholds "$SLO_THRESHOLDS" \
  --matrix "$LATEST_ARTIFACT" \
  --regression-report "$REGRESSION_REPORT" \
  --python-bin "$PYTHON_BIN" \
  --report "$SLO_REPORT"

echo "[3/4] Generating sidecar for baseline matrix artifact..."
"${CARGO_RUNNER[@]}" run -q -p fnx-durability --bin fnx-durability -- \
  generate "$LATEST_ARTIFACT" "$SIDECAR" "phase2c_perf_baseline_matrix_v1" "benchmark_report" 1400 6

echo "[4/4] Decode drill for baseline matrix artifact..."
"${CARGO_RUNNER[@]}" run -q -p fnx-durability --bin fnx-durability -- \
  decode-drill "$SIDECAR" "$RECOVERED"

echo "Benchmark gate complete:"
echo "  artifact:   $LATEST_ARTIFACT"
echo "  slo_report: $SLO_REPORT"
echo "  sidecar:    $SIDECAR"
echo "  recovered:  $RECOVERED"

python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

artifact_path = Path("artifacts/perf/latest/perf_baseline_matrix_v1.json")
sidecar_path = Path("artifacts/perf/latest/perf_baseline_matrix_v1.raptorq.json")
artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
report = {
    "suite": "benchmark",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "entries": [
        {
            "artifact_path": str(artifact_path),
            "baseline_comparator_path": "artifacts/perf/latest/perf_baseline_matrix_baseline_comparator_v1.json",
            "sidecar_path": str(sidecar_path),
            "recovered_path": "artifacts/perf/latest/perf_baseline_matrix_v1.recovered.json",
            "matrix_id": artifact.get("matrix_id"),
            "scenario_count": artifact.get("scenario_count"),
            "events_path": artifact.get("events_path"),
            "hotspot_backlog_path": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            "isomorphism_report_path": "artifacts/perf/phase2c/isomorphism_harness_report_v1.json",
            "regression_report_path": "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
            "slo_thresholds_path": "artifacts/perf/slo_thresholds.json",
            "slo_report_path": "artifacts/perf/latest/slo_gate_report_v1.json",
            "environment_fingerprint": artifact.get("environment_fingerprint"),
            "artifact_id": payload.get("artifact_id"),
            "artifact_type": payload.get("artifact_type"),
            "source_hash": payload.get("source_hash"),
            "scrub_status": payload.get("scrub", {}).get("status"),
            "decode_proof_count": len(payload.get("decode_proofs", [])),
            "repair_symbols": payload.get("raptorq", {}).get("repair_symbols"),
            "packet_count": len(payload.get("raptorq", {}).get("packets_b64", [])),
        }
    ],
}

report_path = Path("artifacts/perf/latest/durability_pipeline_report.json")
report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"  durability_report:{report_path}")
PY
