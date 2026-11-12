# Validation Summary

Bead: `br-r37-c1-5lpag`

Passed:

- `rch exec -- cargo check -p fnx-classes`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`
- `rustfmt --edition 2024 --check crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`
- `rch exec -- cargo test -p fnx-classes edge_storage_order_index_iter_tracks_mutations`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_native_weighted_parity.py -q` (`296 passed`)
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_default_native_parity.py -q` (`7 passed`)
- `timeout 180 ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`
- `sha256sum -c artifact_sha256.txt`

Notes:

- The first post-change `rch exec -- maturin develop --release --features
  pyo3/abi3-py310` failed with an `rch`/maturin copy-path error after waiting
  on the build directory lock. The same command retried in
  `maturin_develop_after_retry.rch.log` passed and installed the release
  extension.
- UBS reported zero critical issues. Its remaining warnings are broad existing
  inventory in the two large Rust files.
