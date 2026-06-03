# Validation Summary: sparse typed arrays read edge attrs once

Bead: `br-r37-c1-04z53.34`

## Build And Lint

- `rch exec -- rustfmt --edition 2024 --check crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_sparse_edge_once cargo check -p fnx-classes --lib`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_sparse_edge_once cargo check -p fnx-python --lib --features pyo3/abi3-py310`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_sparse_edge_once cargo clippy -p fnx-classes --lib -- -D warnings`: passed after removing a redundant `#[must_use]`.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_sparse_edge_once cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_sparse_edge_once maturin develop --release --features pyo3/abi3-py310`: passed.

Note: `cargo fmt -p fnx-classes -p fnx-python --check` was attempted first and failed on unrelated peer edits in `crates/fnx-python/src/digraph.rs`; touched-file `rustfmt --check` passed.

## Tests

- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_native_weighted_parity.py tests/python/test_to_scipy_sparse_default_native_parity.py -q`: `303 passed`.

## Static Scan

- `timeout 180s ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`: exit 0, zero critical issues; broad pre-existing warnings recorded in `ubs_rust.log`.

## Artifact Integrity

See `artifact_sha256.txt` and `artifact_sha256_check.txt`.
