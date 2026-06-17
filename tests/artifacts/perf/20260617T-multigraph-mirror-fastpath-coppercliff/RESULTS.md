# MultiGraph mirror fast path rejection

Bead: `br-r37-c1-salvt`

Target: `MultiGraph._native_edge_view_list(data=True, keys=True)` in the
`multigraph_attr` construction/digest benchmark.

Lever tried: in the `data=True` path, check for an existing live edge-attribute
mirror before falling back to `ensure_edge_py_attrs`.

Outcome: rejected and source reverted.

Behavior proof:

- Golden digest stayed
  `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`.
- Focused parity passed: `171 passed` for
  `tests/python/test_attribute_access_parity.py` and
  `tests/python/test_add_edges_attr_batch_parity.py`.
- The lever did not touch edge ordering/orientation, floating-point arithmetic,
  RNG, nbunch fallback, or non-string data-key fallback paths.

Performance evidence:

- Survey FNX median regressed from `0.018026061006821692s` to
  `0.01859719498315826s`.
- Survey FNX/NX ratio changed from `1.1925310588824065` to
  `1.1887640632966436`, but that ratio change came with slower FNX and slower
  NX timings.
- Focused profile total regressed from `9.728s` to `9.979s`.
- `_MultiGraphEdgeView.__call__` regressed from `1.575s` to `1.691s`.
- `_native_edge_view_list` regressed from `1.505s` to `1.607s`.
- Hyperfine FNX loop50 mean improved from `2.66799986692s` to
  `2.5823831992s`, but did not outweigh the direct survey/profile regression.

Validation commands run before rejection:

- `cargo fmt --check`
- `cargo check -p fnx-python --all-targets`
- `maturin develop --release --features pyo3/abi3-py310`
- `.venv/bin/python -m pytest tests/python/test_attribute_access_parity.py tests/python/test_add_edges_attr_batch_parity.py -q`

Conclusion: source reverted. The next attack should avoid extra branch work in
the tuple-emission loop and move deeper, likely toward an index-space edge-view
primitive or construction-side mirror layout.
