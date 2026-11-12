# MultiDiGraph native all-edge list keep

Bead: `br-r37-c1-5838s`

Target: `MultiDiGraph.edges(keys=True, data=True)` in the `multidigraph_attr`
construction/digest benchmark.

Lever: add a direct `PyMultiDiGraph._native_edge_view_list` all-edge helper and
route `nbunch=None` common `data` modes through it, avoiding the previous
Python pass that drained a native `NodeIterator` into a second list.

Outcome: kept.

Behavior proof:

- Golden digest stayed
  `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.
- Ordering remains node-major, successor-order, key-order for directed
  MultiDiGraph edge views.
- The change does not touch floating-point arithmetic, RNG, nbunch filtering,
  explicit `data=None`, or non-string data-key fallback paths.
- Focused parity passed: `171 passed` for
  `tests/python/test_attribute_access_parity.py` and
  `tests/python/test_add_edges_attr_batch_parity.py`.

Performance evidence:

- Survey FNX median improved from `0.021502784045878798s` to
  `0.019556010025553405s`.
- Survey FNX/NX ratio improved from `1.321691092754138` to
  `1.2475870900281825`.
- Focused profile total improved from `9.297s` to `8.956s`.
- `_digest_graph` improved from `5.631s` to `5.420s`.
- `_MultiDiGraphEdgeView.__call__` improved from `0.881s` to `0.837s`.
- Hyperfine FNX loop50 mean improved from `2.6109681297600003s` to
  `2.5431759298400003s`.

Score: Impact `2.0` x Confidence `2.0` / Effort `1.0` = `4.0`; keep.

Validation commands:

- `cargo fmt --check`
- `cargo check -p fnx-python --all-targets`
- `maturin develop --release --features pyo3/abi3-py310`
- `.venv/bin/python -m pytest tests/python/test_attribute_access_parity.py tests/python/test_add_edges_attr_batch_parity.py -q`
- `cargo clippy -p fnx-python --all-targets -- -D warnings`
