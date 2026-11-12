# br-r37-c1-wkkld MultiDiGraph Keyed Data Edge View

Target: `MultiDiGraph.edges(keys=True, data=True, nbunch=None)` on freshly
constructed attributed exact-int graphs.

Lever: add a native one-pass path that reuses existing live edge attr mirrors
immutably when every edge already has a mirror. Sparse/plain edges fall back to
the existing materializing path, preserving live dict mutation semantics.

## Performance

Profile, 160 builds through the construction digest harness:

- Total profile time: `9.838s` -> `9.213s`
- `_digest_graph`: `5.983s` -> `5.534s`
- `__init__.py:2324(__call__)`: `1.106s` -> `0.784s`
- Edge-view call speedup: `1.41x`

Hyperfine loop50:

- FNX mean: `2.7428788863s` -> `2.6748955134s`
- FNX median: `2.7789429268999997s` -> `2.6697531646s`
- NetworkX mean in paired runs: `2.4674669611s` -> `2.449082137s`

Construction survey digest:

- `digests_match=true`
- Digest: `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`
- FNX/NX median ratio: `1.2468547314950265` -> `1.1360693422531318`

Score: Impact 2 x Confidence 4 / Effort 2 = 4.0.

## Correctness

Focused validation:

- `cargo fmt --check`
- `cargo check -p fnx-python --all-targets`
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py::test_multidigraph_keyed_data_view_preserves_live_attrs_for_mirrored_and_plain_edges -q`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_view_surface_mutation_parity.py -q`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_dicsr_cache_parity.py::test_digraph_ctor_bulk_absorb_and_get_edge_data_lazy -q`

Behavior invariants preserved:

- Node/source/target/key iteration order stays `inner.edges_ordered_borrowed()`.
- Existing mirrored attr dicts are returned by identity.
- Plain or sparse-mirror edges fall back to the previous materializing path, so
  mutations through returned `data=True` dicts remain live.
- Golden digest and NetworkX keyed data view output stay unchanged.
