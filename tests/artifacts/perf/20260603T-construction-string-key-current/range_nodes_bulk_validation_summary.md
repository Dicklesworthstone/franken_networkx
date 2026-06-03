# Range Node Bulk Validation Summary

## Passed

- `cargo fmt -p fnx-classes --check`
- `cargo fmt -p fnx-python --check`
- `rch exec -- cargo check -p fnx-classes --all-targets`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
- `rch exec -- cargo test -p fnx-classes extend_nodes_unrecorded -- --nocapture`: `1 passed`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_node_key_canonicalization_parity.py tests/python/test_attribute_access_parity.py tests/python/test_review_mode_regression_lock.py -q -k 'node_key_type_parity or graph_iteration_detects_batch_node_mutations or graph_iteration_detects_add_edge_creating_new_node or attribute'`: `144 passed, 431 deselected`

## Workspace-Scoped Note

`cargo fmt --check` at workspace scope was not used as commit evidence because it reported unrelated peer formatting diffs in `crates/fnx-conformance/tests/metamorphic_relations_gate.rs` and `crates/fnx-readwrite/src/lib.rs`. Touched-crate formatting passed and no unrelated files were formatted or rewritten.

## UBS

`timeout 240s ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/lib.rs python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-construction-string-key-current/bench_construction.py` exited `124`.

The log shows the shadow workspace was prepared, Python and Rust scanners started, and the Rust scanner finished in `15s`; no findings were emitted before the Python scan hit the timeout boundary.
