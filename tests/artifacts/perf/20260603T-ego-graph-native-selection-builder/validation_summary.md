# br-r37-c1-0nkch Validation Summary

## rch Commands

- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-ego-graph-r2-current/bench_ego_graph_r2.py sample --impl fnx --n 3000 --m 4 --seed 42 --repeats 50`
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-ego-graph-r2-current/bench_ego_graph_r2.py sample --impl nx --n 3000 --m 4 --seed 42 --repeats 50`
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-ego-graph-r2-current/bench_ego_graph_r2.py profile --impl fnx --n 3000 --m 4 --seed 42 --repeats 20`
- `rch exec -- hyperfine --warmup 5 --runs 25 --export-json tests/artifacts/perf/20260603T-ego-graph-native-selection-builder/hyperfine_baseline.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-ego-graph-r2-current/bench_ego_graph_r2.py sample --impl fnx --n 3000 --m 4 --seed 42 --repeats 9 >/dev/null'`
- `rch exec -- hyperfine --warmup 5 --runs 25 --export-json tests/artifacts/perf/20260603T-ego-graph-native-selection-builder/hyperfine_after.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-ego-graph-r2-current/bench_ego_graph_r2.py sample --impl fnx --n 3000 --m 4 --seed 42 --repeats 9 >/dev/null'`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_ego_graph_node_order_parity.py tests/python/test_native_replacements_parity.py::TestEgoGraph tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx -q`
- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_ego_graph_node_order_parity.py`

## Results

- Baseline FNX direct mean: `0.03204226841917261s`.
- NetworkX direct mean: `0.022998212501988746s`.
- Candidate FNX direct mean: `0.03422747532371431s`.
- Baseline hyperfine mean: `0.62744617802s`.
- Candidate hyperfine mean: `0.7039144615200001s`.
- Golden digest unchanged: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## Source Restoration

- `rg -n "_native_ego_graph_r2|native_ego" crates/fnx-python/src/lib.rs python/franken_networkx/__init__.py tests/python/test_ego_graph_node_order_parity.py` returned no matches.
- `git diff -- tests/python/test_ego_graph_node_order_parity.py` returned empty.
- Restored FNX direct mean: `0.03105362699861871s`.

## Next Primitive

Do not repeat `ego_graph` materialization micro-levers. The next profile-backed attack should move to a fundamentally different primitive: native CSR/frontier graph kernels for a traversal or centrality gap, or a result representation that avoids Python-visible graph construction entirely until observation.
