# Validation Summary

- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed before measurement and again after check/clippy artifact retrieval.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed.
- `rch exec -- rustfmt --edition 2024 --check crates/fnx-python/src/digraph.rs`: passed.
- `rch exec -- python -m py_compile ...`: passed for `python/franken_networkx/__init__.py`, `tests/python/test_dag_extras.py`, and the fused benchmark harness.
- `rch exec -- pytest ... -k 'dag_longest_path or dag_longest_cyclic'`: passed after the fresh rebuild, `97 passed, 119 deselected`.
- UBS targeted Rust scan: no critical findings; broad pre-existing warnings in `crates/fnx-python/src/digraph.rs` were recorded in `ubs_digraph.log`.
- UBS targeted small Python scan: no critical findings; one test-file warning and normal pytest `assert` inventory recorded in `ubs_small_python.log`.
- UBS large wrapper scan: bounded run on `python/franken_networkx/__init__.py` did not complete before timeout; syntax, focused parity, and behavior proof passed.
