# bfs_tree indexed result construction validation summary

## Commands

- `rustfmt --edition 2024 --check crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- hyperfine --warmup 3 --runs 15 ... bfs_tree ...`

## Results

- File-scoped rustfmt check: passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- Release extension candidate build: passed.
- Candidate direct SHA: unchanged at `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- Candidate direct mean: `0.006317437958787195s`.
- Candidate hyperfine mean: `0.43277942618s`; confirm `0.43308385356000006s`.
- Candidate rejected below Score >= 2.0.
- Release extension restored after candidate removal.
- Restored FNX sample SHA: `1080bb4f9f5cb05745326b002917767f0f0693de81f277c7cb6df03e49d14b76`.

Verdict: rejected, no source kept.

