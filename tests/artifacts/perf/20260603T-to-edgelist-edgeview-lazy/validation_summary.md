# br-r37-c1-gl3nq Validation Summary

## Build and lint

- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: pass.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: pass.
- `rustfmt --edition 2024 --check crates/fnx-python/src/readwrite.rs`: pass.

## Python checks

- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_conversion.py tests/artifacts/perf/20260603T-to-edgelist-edgeview-lazy/bench_to_edgelist.py`: pass.
- `.venv/bin/python -m pytest tests/python/test_conversion.py::TestEdgelist -q`: 5 passed.

## Behavior proof

- Baseline golden SHA and after golden SHA match exactly: `f749a0821055e92da035534a0c2c564f4a3d7f44da6ca82f410a50d2a26e653d`.
- `sha256sum -c artifact_sha256.txt`: pass after final manifest refresh.

## UBS

- `timeout 120s ubs --only=rust crates/fnx-python/src/readwrite.rs`: exit 0; existing file-wide warnings only, no critical issues.
- `timeout 120s ubs tests/artifacts/perf/20260603T-to-edgelist-edgeview-lazy/bench_to_edgelist.py`: exit 0; no critical or warning issues.
- `timeout 120s ubs tests/python/test_conversion.py`: exit 1; known pre-existing file-wide test findings remain. The new edgelist test was written without pytest `assert` statements and is not referenced by the final UBS output.
- `timeout 120s ubs python/franken_networkx/__init__.py`: exit 124 timeout on generated large file; partial output captured in `ubs_init.txt`.
