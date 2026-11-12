# Optimization Round: Graph Kernel Clone Elision

## Change
- Lever 1 (fnx-algorithms): switched BFS-family traversals to borrowed node IDs (`&str`) to reduce transient allocation and clone churn.
- Lever 2 (fnx-classes hot path): in `add_edge_with_attrs`, short-circuit node auto-creation for already-present nodes and remove edge-attr check clone path.

## Hotspot Evidence
- Profile constraint: `cargo flamegraph` blocked by `perf_event_paranoid=4` in this environment.
- Baseline benchmark command:
  - `hyperfine --warmup 3 --runs 10 'CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-algorithms --example bfs_baseline'`
  - before: mean `240.1 ms`
  - after:  mean `214.5 ms`
  - delta: `-10.7%`
- Release benchmark command:
  - `hyperfine --warmup 3 --runs 10 'CARGO_TARGET_DIR=target-codex cargo run --release -q -p fnx-algorithms --example bfs_baseline'`
  - before: mean `127.3 ms`
  - after:  mean `122.3 ms`
  - delta: `-3.9%`

## Isomorphism Proof
- Ordering preserved: yes; traversal still uses deterministic insertion order from `IndexSet` adjacency.
- Tie-breaking unchanged: yes; neighbor visitation order unchanged, shortest-path choice unchanged.
- Floating-point: unchanged formulas for centrality scores.
- RNG seeds: N/A.
- Golden output:
  - `sha256sum -c artifacts/perf/proof/golden_checksums.txt` (expected pass)

## Validation Commands
- `cargo fmt --check`
- `cargo test -p fnx-classes -p fnx-algorithms`
- `cargo check --all-targets`

## Rollback
- `git revert <optimization-commit-sha>`
