# Isomorphism Proof: single_source_shortest_path indexed BFS

Bead: `br-r37-c1-04z53.10`

Baseline:
- fnx sample mean: 0.008288126597472 s.
- nx sample mean: 0.0015962435980327427 s.
- fnx and nx digest: `d9f9307bf79bc0ba306f70eb31e19b5ccce8943aec3738b95dcfa13dccbd7d9b`.
- hyperfine process mean: 0.56250081422 s.

After:
- fnx sample mean: 0.0018424232992401812 s.
- Sample speedup: 4.498492067968333x.
- fnx digest: `d9f9307bf79bc0ba306f70eb31e19b5ccce8943aec3738b95dcfa13dccbd7d9b`.
- hyperfine process mean: 0.47720496982 s.
- Process speedup: 1.1787404779798778x.
- cProfile native cumulative time: 0.037 s across 20 calls.

Behavior invariants:
- Ordering: BFS discovery order is preserved by pushing node indices into `discovery_order` at first visit, matching the previous result append point.
- Tie-breaking: neighbor iteration uses `Graph::neighbors_indices`, which follows the graph adjacency insertion order used by the existing indexed BFS length path.
- Floating point: none on this unweighted path-building API.
- RNG: none in the library path; benchmark graph seed is fixed at 42.
- Directed graphs: unchanged; `DiGraph` does not expose successor-index slices, so this lever only changes the profiled undirected implementation.
- Golden output: baseline fnx, baseline nx, and after fnx SHA-256 digests are identical.

Verification:
- `rch exec -- cargo fmt --package fnx-algorithms --check`: passed.
- `rch exec -- cargo test -p fnx-algorithms single_source_shortest_path -- --nocapture`: compile/test smoke passed; no Rust unit names matched the filter.
- `rch exec -- cargo check -p fnx-algorithms --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: passed.
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_single_source_shortest_bfs_order_parity.py tests/python/test_single_source_shortest_path_parity.py -q`: 20 passed.
- `timeout 180 ubs crates/fnx-algorithms/src/lib.rs tests/artifacts/perf/20260603T-single-source-shortest-path-index/alien_recommendation_card.md tests/artifacts/perf/20260603T-single-source-shortest-path-index/isomorphism_proof.md tests/artifacts/perf/20260603T-single-source-shortest-path-index/golden_sha256.txt`: exit 1 on existing broad `fnx-algorithms` inventory; clippy, cargo check, and targeted Python parity remained clean. The reported clone-in-loop example at the shortest-path location is now the unchanged directed implementation, not the optimized undirected path.
