# br-r37-c1-42ulj DiGraph Attributed Construction

Target: `DiGraph.add_edges_from` on fresh exact-int `(u, v, {"weight": f64})`
construction.

Lever: store Rust edge attributes eagerly, but defer Python edge-attribute
mirror dict allocation until a view/API needs the live dict.

## Performance

Dedicated direct harness:

- Baseline FNX median: `0.00760931900003925s`
- After FNX median: `0.004824688017833978s`
- Speedup: `1.58x`
- Baseline NX median: `0.006566514959558845s`
- After NX median: `0.006931096955668181s`

Dedicated hyperfine, 120 builds per command:

- Baseline FNX mean: `1.1058389012199998s`
- After FNX mean: `0.7334569249200001s`
- Speedup: `1.51x`

Dedicated cProfile, 160 builds:

- Baseline `_try_add_edges_from_batch`: `0.771s`
- After `_try_add_edges_from_batch`: `0.553s`
- Speedup: `1.39x`

Routing survey check:

- Before `digraph_attr` FNX/NX median ratio: `1.3722682991771993`
- After `digraph_attr` FNX/NX median ratio: `1.0234311299426269`
- Digest: `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`

Score: Impact 3 x Confidence 4 / Effort 2 = 6.0.

## Correctness

Golden construction digest:

- `e603205862fdf5e9ed648d992331f9f236208d0d0bb5743ab01a1103a678c144`
- `digests_match=true`

Directed view/mutation semantics digest:

- `334a1d40c776f5539620631bb1564c19a8cb7f5b5187bc120784808a2a264bd3`
- `digests_match=true`

Focused validation:

- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_dicsr_cache_parity.py::test_digraph_ctor_bulk_absorb_and_get_edge_data_lazy tests/python/test_dicsr_cache_parity.py::test_add_edges_from_global_attr_batch tests/python/test_view_surface_mutation_parity.py tests/python/test_add_edges_attr_batch_parity.py::test_digraph_attr_batch_preserves_direction_and_mirrors -q`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q`
- `cargo fmt --check`
- `cargo check -p fnx-python --all-targets`
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-python/src/digraph.rs tests/python/test_add_edges_attr_batch_parity.py`

Known unrelated gate failure:

- `cargo test -p fnx-python --lib algorithms::tests::python_algorithm_wrappers_preserve_mode --features pyo3/abi3-py310`
- Fails in `minimum_spanning_tree` runtime-policy ledger equality. The failing
  file is not modified by this lever, and the local MST wrapper comment says
  the current mode-only fresh ledger was intentional for performance.
