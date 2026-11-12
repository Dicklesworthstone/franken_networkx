# Validation summary

Bead: `br-r37-c1-04z53.36`

## Commands

- `rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl nx --op ego_graph_r2 --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- hyperfine --warmup 3 --runs 15 --export-json tests/artifacts/perf/20260603T-ego-graph-batch-empty-nodes/hyperfine_baseline.json '.venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 5 --n 3000 --m 4 --graph-seed 42'`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- hyperfine --warmup 3 --runs 15 --export-json tests/artifacts/perf/20260603T-ego-graph-batch-empty-nodes/hyperfine_after.json '.venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 5 --n 3000 --m 4 --graph-seed 42'`
- `rch exec -- hyperfine --warmup 5 --runs 25 --export-json tests/artifacts/perf/20260603T-ego-graph-batch-empty-nodes/hyperfine_after_confirm.json '.venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 5 --n 3000 --m 4 --graph-seed 42'`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx tests/python/test_review_mode_regression_lock.py::test_ego_graph_missing_source_and_nan_radius_match_nx tests/python/test_ego_graph_node_order_parity.py -q`

## Results

- Candidate output SHA matched baseline fnx and NetworkX:
  `8195242bb15c80fa50c2ad2d1daf43699828f5dadf578d8ac6c22754dddc7849`.
- Restored `py_compile` passed.
- Focused restored ego-graph parity: `12 passed`.
- The target hunk in `python/franken_networkx/__init__.py` no longer differed
  from `HEAD` after source restoration.
- Candidate rejected; no source change kept.
