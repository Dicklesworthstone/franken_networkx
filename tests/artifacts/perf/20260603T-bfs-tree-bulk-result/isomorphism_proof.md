# Isomorphism Proof: BFS Tree Bulk Result Construction

Bead: `br-r37-c1-04z53.21`

## Change
Route `_fnx.bfs_tree` result construction through `DiGraph::extend_edges_unrecorded`
after the existing `fnx_algorithms::bfs_edges` traversal has produced the same
BFS tree edge stream.

## Baseline and Profile
- Target: BA(3000, 4, seed=42), `bfs_tree(Graph, 0)`.
- Baseline fnx sample mean: `0.03790626530244481s`.
- Baseline NetworkX sample mean: `0.004750026698457077s`.
- Baseline hyperfine mean: `0.7904s`.
- Profile: native `_fnx.bfs_tree` remained the dominant call.

## After
- After fnx sample mean: `0.027850108203710987s`.
- After hyperfine mean: `0.7014s`.
- Sample speedup: `1.361x`.
- Hyperfine speedup: `1.127x`.
- Output digest stayed `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c`.

## Behavior Contract
- Ordering preserved: yes. The traversal still comes from `fnx_algorithms::bfs_edges`, so BFS discovery order and edge insertion order are unchanged.
- Tie-breaking unchanged: yes. Neighbor iteration, visited marking, and first-discovery parent selection are unchanged.
- Floating-point: N/A. `bfs_tree` does not use floating-point arithmetic.
- RNG seeds: unchanged. The benchmark graph seed is fixed at 42; the library path is RNG-free.
- Node and edge attributes: unchanged for the returned BFS tree. The previous path created empty attrs for tree nodes and edges; the new path creates the same empty Python attr dicts and uses the same directed edge keys.
- Fallbacks: unchanged. Python-level `sort_neighbors` fallback and non-native exception fallback remain outside this result-construction change.

## Verification
- `sha256sum -c tests/artifacts/perf/20260603T-bfs-tree-bulk-result/artifact_sha256.txt`
- `rch exec -- cargo fmt --package fnx-python --check`
- `rch exec -- cargo check -p fnx-python --all-targets`
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_traversal.py tests/python/test_sort_neighbors_parity.py tests/python/test_traversal_coding_minors_conformance.py tests/python/test_attribute_access_parity.py -q -k 'bfs_tree or bfs_edges'`
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
