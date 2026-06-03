# Validation summary

Bead: `br-r37-c1-04z53.35`

## Commands

- `rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl nx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- hyperfine --warmup 3 --runs 15 --export-json tests/artifacts/perf/20260603T-bfs-tree-inner-capacity/hyperfine_baseline.json '.venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 5 --n 3000 --m 4 --graph-seed 42'`
- `rch exec -- rustfmt --edition 2024 --check crates/fnx-classes/src/digraph.rs crates/fnx-python/src/digraph.rs crates/fnx-python/src/algorithms.rs`
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_bfs_tree_inner_capacity cargo check -p fnx-classes --lib`
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_bfs_tree_inner_capacity cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_bfs_tree_inner_capacity maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- hyperfine --warmup 3 --runs 15 --export-json tests/artifacts/perf/20260603T-bfs-tree-inner-capacity/hyperfine_after.json '.venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 5 --n 3000 --m 4 --graph-seed 42'`
- `rch exec -- env CARGO_TARGET_DIR=/tmp/rch_target_fnx_bfs_tree_inner_capacity_restore maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_traversal.py tests/python/test_sort_neighbors_parity.py tests/python/test_traversal_coding_minors_conformance.py tests/python/test_attribute_access_parity.py -q -k 'bfs_tree or bfs_edges'`

## Results

- Candidate output SHA matched baseline fnx and NetworkX:
  `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- Focused restored traversal parity: `22 passed, 256 deselected`.
- `git diff HEAD -- crates/fnx-classes/src/digraph.rs crates/fnx-python/src/algorithms.rs crates/fnx-python/src/digraph.rs` was empty after source restoration.
- Candidate rejected; no source change kept.
