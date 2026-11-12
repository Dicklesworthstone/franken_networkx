# MultiGraph borrowed view iterator rejection

Bead: `br-r37-c1-bnhyh`

Target: `MultiGraph.edges(keys=True, data=True)` in the `multigraph_attr`
construction/digest benchmark.

Lever tried: add a `fnx-classes` borrowed, first-traversed-orientation edge
iterator and route `PyMultiGraph._native_edge_view_list` through it to remove
the binding loop's cloned canonical dedup keys.

Outcome: rejected and source reverted.

Behavior proof:

- Golden digest stayed
  `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`.
- Focused parity passed: `171 passed` for
  `tests/python/test_attribute_access_parity.py` and
  `tests/python/test_add_edges_attr_batch_parity.py`.
- The lever did not touch floating-point arithmetic, RNG, nbunch fallback, or
  non-string data-key fallback paths.

Performance evidence:

- Survey FNX median regressed from `0.018817687989212573s` to
  `0.02017399697797373s`.
- Survey FNX/NX ratio regressed from `1.1888106900384323` to
  `1.285594052438882`.
- Focused profile total regressed from `9.557s` to `10.298s`.
- `_MultiGraphEdgeView.__call__` regressed from `1.574s` to `1.752s`.
- `_native_edge_view_list` regressed from `1.504s` to `1.675s`.
- Hyperfine FNX loop50 mean improved only from `2.58895539146s` to
  `2.53377830306s`, which did not outweigh the direct survey/profile
  regression.

Validation commands run before rejection:

- `cargo fmt --check`
- `cargo check -p fnx-classes -p fnx-python --all-targets`
- `maturin develop --release --features pyo3/abi3-py310`
- `.venv/bin/python -m pytest tests/python/test_attribute_access_parity.py tests/python/test_add_edges_attr_batch_parity.py -q`

Conclusion: source reverted. The next MultiGraph attack should avoid this
owned-endpoint materialization shape and target either live attr mirror lookup or
a true index-space view primitive.
