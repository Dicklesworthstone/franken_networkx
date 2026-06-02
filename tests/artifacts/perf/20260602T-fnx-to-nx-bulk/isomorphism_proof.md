# Isomorphism Proof: br-r37-c1-xykjs

## Lever

Expose `_fnx.fnx_to_nx_adjacency(G)` for concrete simple `Graph` and
`DiGraph`, returning node order, adjacency order, and Python-visible edge
attribute dictionaries in one boundary crossing. Python `_fnx_to_nx`
still uses the same `_topo_emit_edges_by_adj` ordering algorithm.

## Observable Contract

- Graph type: `Graph` remains `nx.Graph`; `DiGraph` remains `nx.DiGraph`.
- Node order: native helper iterates `inner.nodes_ordered()`, matching the
  fnx insertion order consumed by the previous Python path.
- Adjacency order: native helper uses `neighbors_iter` or
  `successors_iter`, matching the previous `fg._adj.items()` order for
  concrete simple graphs.
- Edge attributes: native helper reads `edge_py_attrs`, not stale Rust
  `inner` attrs, so post-creation Python mutations remain visible.
- Node and graph attributes: unchanged Python code copies them.
- Multigraphs: unchanged Python path.
- Views/subclasses: unchanged Python path because native routing requires
  exact `type(fg) in (fnx.Graph, fnx.DiGraph)`.

## Ordering and Tie-Breaks

The emitted edge order is still produced by `_topo_emit_edges_by_adj`.
Only the queue source changes from per-node AtlasView lookups to native
neighbor lists with the same order. Algorithms sensitive to adjacency
iteration, including `greedy_color` BFS/DFS strategies, are covered by
`tests/python/test_fnx_to_nx_bulk_conversion_parity.py`.

## Floating Point

No floating-point arithmetic is introduced. Edge attribute values are
Python objects passed through as dictionaries and copied with `dict(attrs)`.

## RNG

No library RNG path changes. Benchmark graph generation uses fixed seed
`11` only for measurement reproducibility.

## Golden Digests

BA(3000, 4), 11984 edges:

- Converted graph digest before/native/upstream-build:
  `60baad123bf321cd2a0307d326aa2fa9bb3d1d528ee3d4236fc0e075bf6626c4`
- `onion_layers` result digest before/native/upstream:
  `6573e535f2d3d498d6d72f76389e7aa561a5acb88988609ce3db9f23a6c67499`

## Verification

- `rch exec -- cargo fmt --package fnx-python --check`: passed.
- `rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`:
  passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`:
  passed.
- `rch exec -- .venv/bin/python -m py_compile ...`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_fnx_to_nx_bulk_conversion_parity.py -q`:
  323 passed.
- Existing adjacency-order, attribute collision, multigraph backend,
  traversal, and backend-import slices passed.
- `timeout 180 ubs crates/fnx-python/src/algorithms.rs python/franken_networkx/backend.py tests/python/test_fnx_to_nx_bulk_conversion_parity.py tests/artifacts/perf/20260602T-fnx-to-nx-bulk/bench_fnx_to_nx_bulk.py ...`:
  exit 0.
