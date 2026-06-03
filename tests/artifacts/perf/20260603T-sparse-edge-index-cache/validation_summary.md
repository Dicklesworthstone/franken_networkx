# Validation Summary

Bead: `br-r37-c1-5lpag`

Passed:

- `rch exec -- cargo check -p fnx-python --all-targets`
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
- `rch exec -- rustfmt --edition 2024 --check crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`
- `rch exec -- cargo test -p fnx-classes edge_storage_order_index_iter_tracks_mutations`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_native_weighted_parity.py tests/python/test_to_scipy_sparse_default_native_parity.py -q`
- `timeout 180 ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`
- `sha256sum -c artifact_sha256.txt`

Notes:

- `cargo fmt --check -p fnx-classes -p fnx-python` still fails on unrelated
  pre-existing formatting in `crates/fnx-python/src/digraph.rs` and
  `crates/fnx-python/src/readwrite.rs`; the touched Rust files pass rustfmt
  with edition 2024.
- First post-change pytest attempt correctly refused to run because the installed
  extension was older than Rust sources after the clippy fix. Rebuilt with
  `maturin develop --release --features pyo3/abi3-py310`; retry passed.
