# Validation Summary

Bead: `br-r37-c1-epg5e`

## Commands

Baseline:

```bash
rch exec -- maturin develop --release --features pyo3/abi3-py310
rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42
rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl nx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42
rch exec -- .venv/bin/python -m cProfile -o tests/artifacts/perf/20260603T-bfs-tree-frontier-direct/profile_baseline_bfs_tree_fnx.prof tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42
rch exec -- hyperfine --warmup 5 --runs 25 --export-json tests/artifacts/perf/20260603T-bfs-tree-frontier-direct/hyperfine_baseline_bfs_tree_fnx.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 20 --n 3000 --m 4 --graph-seed 42 >/dev/null'
```

After:

```bash
.venv/bin/python -m py_compile python/franken_networkx/__init__.py
rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42
rch exec -- .venv/bin/python -m cProfile -o tests/artifacts/perf/20260603T-bfs-tree-frontier-direct/profile_after_bfs_tree_fnx.prof tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42
rch exec -- hyperfine --warmup 5 --runs 25 --export-json tests/artifacts/perf/20260603T-bfs-tree-frontier-direct/hyperfine_after_bfs_tree_fnx.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 20 --n 3000 --m 4 --graph-seed 42 >/dev/null'
rch exec -- .venv/bin/python -m pytest tests/python/test_review_mode_regression_lock.py -q -k 'edge_view_iteration or edge_data_view_iteration or exhausted_edge_view_iterators'
rch exec -- .venv/bin/python -m pytest tests/python/test_digraph_edge_iteration_order_parity.py tests/python/test_edges_data_view_liveness_parity.py tests/python/test_edges_nbunch_order_parity.py -q
timeout 300s ubs python/franken_networkx/__init__.py
```

## Results

- Python compile: passed.
- Edge-view mutation tests: `4 passed, 427 deselected`.
- Edge view order/liveness/nbunch tests: `29 passed`.
- UBS on the generated `python/franken_networkx/__init__.py` timed out after 300s while scanning Python; log captured in `ubs_python_init.log`.
- Raw `bfs_tree()` direct timing: neutral (`0.006609352779341862s -> 0.006662167000467889s`).
- Observed-output profile total: `1.875s -> 1.169s`.
- Observed-output hyperfine mean: `0.6330912347600001s -> 0.58701323932s`.
- Golden SHA unchanged: `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.

## Residual

The next `bfs_tree()` construction pass should not repeat seq guards or direct indexed result building. The remaining construction profile is still native `_fnx.bfs_tree`; a deeper result-representation primitive or native tree-storage specialization is required.
