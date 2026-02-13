#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ARTIFACT="artifacts/perf/latest/bfs_percentiles.json"
SIDECAR="artifacts/perf/latest/bfs_percentiles.raptorq.json"
RECOVERED="artifacts/perf/latest/bfs_percentiles.recovered.json"

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
