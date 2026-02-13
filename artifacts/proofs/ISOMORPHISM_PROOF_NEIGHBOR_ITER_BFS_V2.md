# Isomorphism Proof - Neighbor Iterator Allocation Lever (BFS/Traversal)

Date: 2026-02-13

Optimization lever:
- Replace per-call `Graph::neighbors()` temporary `Vec<&str>` allocation with `Graph::neighbors_iter()` and `Graph::neighbor_count()` in traversal-heavy paths.

Changed code surface:
- `crates/fnx-classes/src/lib.rs`
- `crates/fnx-algorithms/src/lib.rs`

Behavior-isomorphism claim:
- For identical graph inputs, strict/hardened mode semantics, deterministic neighbor order, shortest path outputs, connected component outputs, and centrality values are unchanged.

Evidence:
1. Determinism and API-level behavior tests
- `cargo test --workspace` passed, including:
  - `fnx_algorithms::tests::bfs_shortest_path_uses_deterministic_neighbor_order`
  - `fnx_algorithms::tests::connected_components_are_deterministic_and_partitioned`
  - `fnx_algorithms::tests::closeness_centrality_*`
  - `fnx_classes::tests::neighbors_iter_preserves_deterministic_order`
  - `fnx_classes::tests::neighbor_count_matches_neighbors_len`

2. Conformance harness integrity
- `cargo test -p fnx-conformance -- --nocapture` passed.
- Smoke fixture differential reports remain zero-drift for baseline fixtures.

3. Safety/compatibility gates
- `cargo check --all-targets` passed.
- `cargo clippy --all-targets -- -D warnings` passed.
- `cargo bench` completed with no benchmark regressions in correctness surfaces.

Performance evidence:
- Pre artifact: `artifacts/perf/phase2c/bfs_percentiles_pre_neighbor_iter.json`
- Post artifact: `artifacts/perf/phase2c/bfs_percentiles_post_neighbor_iter.json`
- Delta report: `artifacts/perf/phase2c/BFS_NEIGHBOR_ITER_DELTA.md`
- Machine delta: `artifacts/perf/phase2c/bfs_neighbor_iter_delta.json`

Conclusion:
- The lever preserves behavior under existing unit + conformance evidence while reducing mean/p50 latency in the benchmark scenario. p95/p99 should continue to be observed in subsequent optimization passes.
