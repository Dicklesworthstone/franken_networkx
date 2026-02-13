# Method Stack Status (2026-02-13)

## 1. alien-artifact-coding

Produced:
- decision-theoretic action selector and explicit loss matrices:
  - `crates/fnx-runtime/src/lib.rs`
- evidence ledger with machine-readable records:
  - `crates/fnx-runtime/src/lib.rs`
  - `crates/fnx-classes/src/lib.rs`
  - `crates/fnx-dispatch/src/lib.rs`
  - `crates/fnx-convert/src/lib.rs`
  - `crates/fnx-readwrite/src/lib.rs`
  - `crates/fnx-generators/src/lib.rs`
  - `crates/fnx-conformance/src/lib.rs`

## 2. extreme-software-optimization

Produced:
- opportunity matrix:
  - `artifacts/perf/OPPORTUNITY_MATRIX.md`
- first baseline benchmark:
  - `artifacts/perf/BASELINE_BFS_V1.md`
- behavior-isomorphism proof artifact:
  - `artifacts/proofs/ISOMORPHISM_PROOF_GRAPH_CORE_V1.md`
- optimization harness extension:
  - `scripts/run_conformance_with_durability.sh`
- percentile benchmark gate extension:
  - `scripts/run_benchmark_percentiles.py`
  - `scripts/run_benchmark_gate.sh`
  - `artifacts/perf/latest/bfs_percentiles.json`
- algorithm breadth with complexity-witness artifacts:
  - `crates/fnx-algorithms/src/lib.rs`
  - `crates/fnx-conformance/fixtures/generated/components_connected_strict.json`
- centrality witness + parity artifacts:
  - `crates/fnx-algorithms/src/lib.rs`
  - `crates/fnx-conformance/fixtures/generated/centrality_degree_strict.json`
  - `crates/fnx-conformance/fixtures/generated/centrality_closeness_strict.json`

## 3. RaptorQ-everywhere durability

Produced:
- dedicated durability crate with RaptorQ sidecar generation:
  - `crates/fnx-durability/src/lib.rs`
- scrub verification + recovery:
  - `crates/fnx-durability/src/lib.rs`
- decode proof drill:
  - `crates/fnx-durability/src/lib.rs`
- generated artifacts:
  - `artifacts/conformance/latest/smoke_report.raptorq.json`
  - `artifacts/conformance/latest/smoke_report.recovered.json`
  - `artifacts/perf/latest/bfs_percentiles.raptorq.json`
  - `artifacts/perf/latest/bfs_percentiles.recovered.json`

## 4. frankenlibc/frankenfs security-compatibility doctrine

Produced:
- strict/hardened compatibility mode split:
  - `crates/fnx-runtime/src/lib.rs`
- fail-closed handling on unknown incompatible metadata:
  - `crates/fnx-runtime/src/lib.rs`
  - `crates/fnx-classes/src/lib.rs`
- fail-closed dispatch/conversion/readwrite behavior:
  - `crates/fnx-dispatch/src/lib.rs`
  - `crates/fnx-convert/src/lib.rs`
  - `crates/fnx-readwrite/src/lib.rs`
- fail-closed/clamped generator admission controls:
  - `crates/fnx-generators/src/lib.rs`
- cycle-order compatibility tightening for generator parity:
  - `crates/fnx-generators/src/lib.rs`
- revision-aware view cache invalidation:
  - `crates/fnx-classes/src/lib.rs`
  - `crates/fnx-views/src/lib.rs`
- compatibility status tracking:
  - `FEATURE_PARITY.md`
