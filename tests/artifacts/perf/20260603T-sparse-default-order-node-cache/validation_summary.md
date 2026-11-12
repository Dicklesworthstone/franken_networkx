# Validation Summary: sparse default-order node cache

Bead: `br-r37-c1-04z53.33`

## Candidate Validation

- `rch exec -- cargo fmt -p fnx-python --check`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_python_sparse_node_cache cargo check -p fnx-python --lib --features pyo3/abi3-py310`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_python_sparse_node_cache cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_python_sparse_node_cache maturin develop --release --features pyo3/abi3-py310`: passed for the candidate.

## Benchmark Validation

- Direct rch after sample: completed; digest unchanged.
- Hyperfine rch after run: completed; no win.

## Restore Validation

- Source restored to remove the candidate.
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_python_sparse_node_cache maturin develop --release --features pyo3/abi3-py310`: passed from restored source.

## UBS

UBS was run on the committed artifact directory after report generation; see `ubs_artifacts.log`.
