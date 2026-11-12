# dfs_edges parity blocker validation summary

Bead: `br-r37-c1-v389d`

## Commands

- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op dfs_edges --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl nx --op dfs_edges --repeat 50 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sweep --repeat 5 --n 3000 --m 4 --graph-seed 42`
- `ubs tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py`

## Results

- `py_compile`: passed.
- Patched repeat-50 `dfs_edges` SHA: FNX and NetworkX both `60cfd824e2ecc2670fc5847aa328b05199a27e3541a7a15b01ce97e0d1e9c5ac`.
- Patched repeat-5 sweep `dfs_edges` SHA: FNX and NetworkX both `0a875a840418aba6b8cb5c69e202d22e00773a6b1977035a4dc86b1869198397`.
- UBS exit: `0`.

Verdict: benchmark oracle fixed; no algorithm source change required.

