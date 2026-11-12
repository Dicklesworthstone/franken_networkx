# Validation Summary

Passed:
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`
- `rch exec -- rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_native_weighted_parity.py tests/python/test_to_scipy_sparse_default_native_parity.py -q` (`303 passed`)
- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `timeout 90 ubs --only=rust crates/fnx-python/src/lib.rs` (`exit 0`)

Limited:
- `timeout 180 ubs crates/fnx-python/src/lib.rs python/franken_networkx/__init__.py` timed out in the generated Python module (`exit 124`). Captured log shows Rust finished with no findings before timeout; Python produced no finding before timeout.

Artifact digest check:
- `sha256sum -c artifact_sha256.txt`
