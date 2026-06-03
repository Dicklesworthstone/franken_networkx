# bfs_tree child-unique insertion validation summary

Status: kept candidate.

Commands:
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl nx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m cProfile -s cumulative tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- hyperfine --warmup 3 --runs 15 --export-json tests/artifacts/perf/20260603T-bfs-tree-child-unique-insert/hyperfine_baseline.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 10 --n 3000 --m 4 --graph-seed 42 >/dev/null'`
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_traversal.py tests/python/test_sort_neighbors_parity.py tests/python/test_traversal_coding_minors_conformance.py tests/python/test_attribute_access_parity.py -q -k 'bfs_tree or bfs_edges'`
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo fmt --package fnx-python --check`
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
- `ubs crates/fnx-python/src/algorithms.rs tests/artifacts/perf/20260603T-bfs-tree-child-unique-insert/alien_recommendation_card.md tests/artifacts/perf/20260603T-bfs-tree-child-unique-insert/isomorphism_proof.md tests/artifacts/perf/20260603T-bfs-tree-child-unique-insert/benchmark_report.md tests/artifacts/perf/20260603T-bfs-tree-child-unique-insert/validation_summary.md`
- `sha256sum -c tests/artifacts/perf/20260603T-bfs-tree-child-unique-insert/artifact_sha256.txt`

Results:
- Direct FNX mean improved `0.007174899580422789s -> 0.006850865441374481s`.
- Hyperfine mean improved `0.48092092222666677s -> 0.46374436361333343s`; confirm
  `0.4777153325066667s`.
- Golden SHA stayed
  `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- Focused BFS parity passed: `22 passed, 256 deselected`.
- `cargo check -p fnx-python --features pyo3/abi3-py310` passed.
- `cargo fmt --package fnx-python --check` passed.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
  failed on an unrelated pre-existing warning in `crates/fnx-python/src/lib.rs:3309`
  (`clippy::needless_borrow` on `Some(&dict_arg)`). The touched file
  `crates/fnx-python/src/algorithms.rs` was not implicated.
- `ubs` exited `0` on the touched Rust file plus evidence docs, with `0`
  critical issues. It reported broad pre-existing warnings in `algorithms.rs`;
  see `ubs_changed.log`.
- Artifact checksum verification passed; see `artifact_sha256_check.txt`.
