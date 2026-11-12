# Validation Summary

## Passed

- `rch exec -- maturin develop --release --features pyo3/abi3-py310` before the
  patch: passed.
- `rch exec -- .venv/bin/python ... bench_quotient_graph.py bench --engines fnx nx`:
  baseline and after completed.
- `rch exec -- .venv/bin/python ... bench_quotient_graph.py profile`: baseline
  and after completed.
- `rch exec -- hyperfine --warmup 1 --runs 5 ...`: baseline and after completed.
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-quotient-node-metrics/validate_quotient_node_metrics.py`:
  passed.
- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_quotient_graph_default_node_data.py tests/artifacts/perf/20260603T-quotient-node-metrics/bench_quotient_graph.py tests/artifacts/perf/20260603T-quotient-node-metrics/validate_quotient_node_metrics.py`:
  passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed
  with one pre-existing warning in `crates/fnx-python/src/algorithms.rs`.
- `timeout 180s ubs --only=python tests/python/test_quotient_graph_default_node_data.py tests/artifacts/perf/20260603T-quotient-node-metrics/bench_quotient_graph.py tests/artifacts/perf/20260603T-quotient-node-metrics/validate_quotient_node_metrics.py`:
  passed with zero critical or warning issues.

## Blocked / Recorded

- After `maturin develop --release` is blocked by unrelated Rust edits in
  `crates/fnx-python/src/digraph.rs`: `E0308` and `E0277` around copied PyDict
  handling.
- Focused pytest is blocked by `tests/python/conftest.py` because the in-tree
  native extension is older than Rust sources, and the release rebuild is
  blocked as above.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings` is
  blocked by unrelated Rust warnings in `crates/fnx-python/src/algorithms.rs`
  and `crates/fnx-python/src/lib.rs`.
- `timeout 240s ubs --only=python python/franken_networkx/__init__.py` timed out
  while scanning the large generated module; this matches prior perf-pass UBS
  behavior and is captured in `ubs_python_init.log`.

## Artifact Files

- `baseline_bench.jsonl`
- `after_bench.jsonl`
- `baseline_cprofile.txt`
- `after_cprofile.txt`
- `hyperfine_baseline.json`
- `hyperfine_after.json`
- `manual_parity_after.jsonl`
- `maturin_develop_after.rch.log`
- `pytest_focused_after_blocked.rch.log`
- `cargo_check_fnx_python_after_blocked.rch.log`
- `cargo_clippy_fnx_python_after_blocked.rch.log`
- `ubs_python_small.log`
- `ubs_python_init.log`
