# ego_graph trusted raw edge batch benchmark report

Bead: `br-r37-c1-04z53.41`

Environment:
- Baseline release extension rebuilt with
  `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`.
- Bench harness:
  `tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py`.
- Workload: `sample --impl fnx --op ego_graph_r2 --repeat 30 --n 3000 --m 4
  --graph-seed 42`.

Direct sample:

| Run | Mean seconds | p50 seconds | SHA |
| --- | ---: | ---: | --- |
| FNX baseline | `0.02699522003046392` | `0.0267400229931809` | `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3` |
| NetworkX baseline | `0.023283390069263988` | `0.02288582900655456` | `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3` |
| FNX after | `0.024855155232944525` | `0.024085701996227726` | `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3` |

Direct delta:
- FNX speedup: `1.0861x`.
- Residual vs NetworkX mean shrank from `1.1594x` to `1.0317x`.

Hyperfine process benchmark:

| Run | Mean seconds | Median seconds | Stddev |
| --- | ---: | ---: | ---: |
| Baseline | `0.54359138932` | `0.53879958972` | `0.020402647543278824` |
| After | `0.51429685616` | `0.5102711827599999` | `0.02707780844346179` |
| After confirm | `0.5286960480266666` | `0.52839361976` | `0.030611753306724235` |

Hyperfine delta:
- First after speedup: `1.0570x`.
- Confirmed speedup: `1.0279x`.

cProfile:
- Baseline `ego_graph`: `0.805s / 20 calls`.
- After `ego_graph`: `0.675s / 20 calls`.
- Baseline public `add_edges_from` wrapper: `0.393s / 21 calls`.
- After public `add_edges_from` wrapper no longer appears for the hot internal
  result batch; only raw native add remains in the hot path.

Decision:
- Kept. Score `6.0 = Impact 2 * Confidence 3 / Effort 1`, above the `2.0`
  threshold.
