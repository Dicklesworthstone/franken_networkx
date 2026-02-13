#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ARTIFACT="artifacts/perf/latest/bfs_percentiles.json"
SIDECAR="artifacts/perf/latest/bfs_percentiles.raptorq.json"
RECOVERED="artifacts/perf/latest/bfs_percentiles.recovered.json"
PIPELINE_REPORT="artifacts/perf/latest/durability_pipeline_report.json"

echo "[1/3] Running percentile benchmark gate..."
./scripts/run_benchmark_percentiles.py \
  --command "CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-algorithms --example bfs_baseline" \
  --artifact "$ARTIFACT" \
  --runs 7 \
  --warmup 2 \
  --p95-budget-ms 500 \
  --p99-budget-ms 700

echo "[2/3] Generating sidecar for benchmark artifact..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  generate "$ARTIFACT" "$SIDECAR" "bfs_percentiles" "benchmark_report" 1400 6

echo "[3/3] Decode drill for benchmark artifact..."
CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-durability --bin fnx-durability -- \
  decode-drill "$SIDECAR" "$RECOVERED"

echo "Benchmark gate complete:"
echo "  artifact:  $ARTIFACT"
echo "  sidecar:   $SIDECAR"
echo "  recovered: $RECOVERED"

python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

sidecar_path = Path("artifacts/perf/latest/bfs_percentiles.raptorq.json")
payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
report = {
    "suite": "benchmark",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "entries": [
        {
            "artifact_path": "artifacts/perf/latest/bfs_percentiles.json",
            "sidecar_path": str(sidecar_path),
            "recovered_path": "artifacts/perf/latest/bfs_percentiles.recovered.json",
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
