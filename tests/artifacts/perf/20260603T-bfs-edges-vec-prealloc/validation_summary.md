# bfs_edges Vec preallocation validation summary

Validation commands:
- `rch exec -- cargo fmt -p fnx-algorithms --check`
- `rch exec -- cargo check -p fnx-algorithms --lib`
- `rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- python3 tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4`
- `rch exec -- hyperfine --warmup 3 --runs 15 ...`

Outcome:
- Format/check/clippy passed after correcting an initial over-broad patch.
- Golden SHA matched FNX before, FNX after, and NetworkX.
- Candidate rejected because the direct sample regressed and the measured win did not meet Score >= 2.0.
- No source change kept.
