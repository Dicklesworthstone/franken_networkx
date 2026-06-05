# br-r37-c1-04z53.51 Directed Eulerian Native Path

## Target
- Workload: `eulerian_path(DiGraph path, n=2000)` from `bench_delegation_goldmines.py --case eulerian_path_directed`.
- Baseline profile: `baseline_cprofile.txt` showed the old path spending `64.190s` in `python/franken_networkx/__init__.py:eulerian_path`, including `14.886s` converting through `_networkx_graph_for_parity` / `_fnx_to_nx` and `48.739s` inside NetworkX `eulerian_path`.
- Alien primitive: direct safe-Rust reversed-Hierholzer traversal over existing `DiGraph` insertion order.

## Baseline
- Golden section mean: FNX `0.024045182805275546s`, NetworkX `0.015633572806837037s`; FNX/NX `1.5380478347700441`.
- Golden digest: `55d6e89b71f957b470c6b51d788f3fd492661e6bd22d231f513fc0916bdcd45a`.
- Hyperfine process envelope: mean `0.3666099411s`, median `0.37185615400000005s`.

## After
- Golden section mean: FNX `0.004986111339045844s`, NetworkX `0.03477448924968485s`; FNX/NX `0.14338417174857662`.
- Target-section delta: `4.82x` faster than baseline FNX, and `6.97x` faster than same-run NetworkX.
- Golden digest: `55d6e89b71f957b470c6b51d788f3fd492661e6bd22d231f513fc0916bdcd45a`.
- Amplified confirmation: FNX `0.0014723998500267043s`, NetworkX `0.015463117838662584s`; FNX/NX `0.09522011442900917`.
- Amplified target-section delta: `16.33x` faster than baseline FNX, and `10.50x` faster than same-run NetworkX.
- After cProfile: `_fnx.eulerian_path` is `2.871s` over 1000 repeats; `_call_networkx_for_parity` and `_fnx_to_nx` are no longer hot.
- Hyperfine process envelope confirm with 200 inner repeats: FNX mean `0.8950888556200001s`, NetworkX mean `3.6085282206200007s`.
- Same-run process control: FNX is `4.03x` faster than NetworkX after startup/import is amortized.

## Score
- Impact `5` x Confidence `5` / Effort `2` = `12.5`.
- Verdict: PRODUCTIVE; keep.

## Validation
- `cargo fmt -p fnx-algorithms -p fnx-python --check`: passed.
- `rch exec -- cargo check -p fnx-algorithms --all-targets`: passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- `rch exec -- cargo test -p fnx-algorithms eulerian_path_directed -- --nocapture`: 4 passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_eulerian_path_directed_parity.py tests/python/test_eulerian_conformance.py tests/python/test_self_loop_core_eulerian_parity.py -q -k eulerian_path`: 114 passed, 175 deselected.
- Combined `ubs` on touched Rust/Python files: stopped after the Rust phase completed and the Python phase remained active for several minutes.
- `ubs --only=rust crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs`: completed nonzero on broad inventory; the only critical item was a false-context non-secret integer group comparison at `crates/fnx-algorithms/src/lib.rs:32092`, outside the Eulerian path.
