# br-r37-c1-w3yng validation summary

## Passed

- `rch exec -- .venv/bin/python -m py_compile tests/artifacts/perf/20260603T-node-connectivity-native/bench_node_connectivity.py`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- cargo fmt -p fnx-algorithms --check`
- `rch exec -- cargo check -p fnx-algorithms`
- `rch exec -- cargo test -p fnx-algorithms node_connectivity`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_graph_metrics_expansion.py tests/python/test_connectivity.py tests/python/test_connectivity_empty_graph_parity.py tests/python/test_self_loop_connectivity_eulerian_parity.py -q -k 'node_connectivity'`
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`

## UBS

`ubs crates/fnx-algorithms/src/lib.rs tests/artifacts/perf/20260603T-node-connectivity-native/bench_node_connectivity.py` exited nonzero due pre-existing project-wide findings in the large Rust source file. The reported critical sample is at `crates/fnx-algorithms/src/lib.rs:30858`, outside this change. Formatter, clippy, cargo check/test, and Python parity all pass for the touched surface.

## Reprofile note

The next dominant profile target remains native `_fnx.node_connectivity` on graph connectivity workloads. The reported DiGraph generators checked in this pass did not reproduce a FNX-vs-NX slowdown; subsequent passes should attack the directed pair-ordering/max-flow path with a graph shape that reproduces the cc bead numbers or a new profile-backed artifact.
