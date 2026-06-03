# bfs_tree lazy edge metadata rejection proof

Target: `franken_networkx.bfs_tree(Graph, 0)` on BA(8000, 4, seed=42).

Candidate behavior contract:
- Ordering preserved: BFS edge stream and `DiGraph` native insertion order were unchanged.
- Tie-breaking unchanged: traversal still used the existing `fnx_algorithms::bfs_edges` output.
- Source/depth/reverse/sort semantics unchanged: only the no-`sort_neighbors` native result representation was touched; fallback paths were unchanged.
- Floating point: N/A.
- RNG: runtime path has no RNG; benchmark graph seed stayed `42`.
- Edge data liveness: focused test covered `G[u][v]`, `succ`, `pred`, `get_edge_data`, `edges(data=True)`, and `in_edges(data=True)`.

Golden output:
- Baseline FNX SHA: `40dd5c5bbd4df6a848c51d3980210cf060943460e9809e5a6d9a6bd9231916f2`.
- Baseline NetworkX SHA: `40dd5c5bbd4df6a848c51d3980210cf060943460e9809e5a6d9a6bd9231916f2`.
- Candidate FNX SHA: `40dd5c5bbd4df6a848c51d3980210cf060943460e9809e5a6d9a6bd9231916f2`.
- Candidate NetworkX SHA: `40dd5c5bbd4df6a848c51d3980210cf060943460e9809e5a6d9a6bd9231916f2`.
- Restored FNX SHA: `40dd5c5bbd4df6a848c51d3980210cf060943460e9809e5a6d9a6bd9231916f2`.

Validation:
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`: passed for candidate and restored source.
- Focused pytest after candidate: `4 passed`.
- Source restoration check: `git diff -- crates/fnx-python/src/algorithms.rs tests/python/test_attribute_access_parity.py` returned empty.
- Source restoration check: `rg "ensure_edge_py_attrs|bfs_tree_edge_attr_dicts_materialize|lazy-edge" crates/fnx-python/src/digraph.rs crates/fnx-python/src/algorithms.rs tests/python/test_attribute_access_parity.py` returned no matches.

Verdict:
- Rejected. No candidate source or tests are retained.
