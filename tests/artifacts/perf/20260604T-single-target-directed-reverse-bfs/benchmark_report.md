# Directed Single-Target Shortest-Path-Length Reverse BFS

## Target

- Beads: `br-r37-c1-a0nl0`, concrete target `br-r37-c1-cnndw`.
- Workload: `single_target_shortest_path_length(DiGraph, target=4999)` on a 5000-node directed graph with ordered forward jumps.
- Baseline profile: 200 FNX calls took `7.029s`; `single_target_shortest_path_length` spent `7.014s`, dominated by `999000` Python `_single_target_shortest_path_neighbors` / `G.predecessors` calls.
- Lever: route directed length calls through native safe-Rust reverse BFS and return discovery-order pairs, preserving Python dict insertion order.

## Baseline

- Golden means: FNX `0.010690407899285976s`, NetworkX `0.0013469151017488912s`; FNX/NX `7.9369574855943785`.
- Process hyperfine: FNX `0.5578142148000002s`, NetworkX `0.33258318400000003s`.
- Golden digest: `e6f4e822e915eb779243605c7de6c6185f141c64b15cc0bf444836f13db4df7c`.

## After

- Golden means: FNX `0.0014611557630511622s`, NetworkX `0.002009193933918141s`; FNX/NX `0.7272348071456466`.
- Target-section delta: FNX is `7.32x` faster than baseline and `1.38x` faster than same-run NetworkX.
- Process hyperfine: FNX `0.40271347856000006s`, NetworkX `0.33923066916s`; FNX process command is `1.39x` faster than baseline.
- After profile: 200 FNX calls took `0.449s`, with the raw `_fnx.single_target_shortest_path_length` call at `0.437s`; the Python predecessor loop is gone.
- Golden digest: `e6f4e822e915eb779243605c7de6c6185f141c64b15cc0bf444836f13db4df7c`.

## Validation

- `cargo fmt -p fnx-algorithms -p fnx-python --check`: passed.
- `rch exec -- cargo check -p fnx-algorithms --all-targets`: passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed after the binding branch type fix.
- `rch exec -- cargo test -p fnx-algorithms single_target_shortest_path_length_directed -- --nocapture`: passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile ...`: passed.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_single_target_spl_parity.py tests/python/test_shortest_path.py tests/python/test_shortest_path_algorithms.py -q -k single_target`: 5 passed, 151 deselected.
- `timeout 240s ubs --only=rust crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs`: nonzero only on the pre-existing `lib.rs:32094` integer group comparison false-context secret finding, outside the touched reverse-BFS hunk; no reverse-BFS-specific critical finding.
- `timeout 180s` and `timeout 600s ubs --only=python python/franken_networkx/__init__.py ...`: scanner timed out while scanning the large Python module; no finding was emitted before either timeout.

## Score

- Impact `4` x Confidence `5` / Effort `1` = `20.0`.
- Verdict: PRODUCTIVE; keep.
