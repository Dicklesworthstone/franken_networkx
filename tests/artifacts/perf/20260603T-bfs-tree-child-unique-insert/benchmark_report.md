# bfs_tree child-unique insertion benchmark report

Bead: `br-r37-c1-04z53.42`

Environment:
- Baseline and candidate release extensions built with
  `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`.
- Bench harness:
  `tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py`.
- Workload: `sample --impl fnx --op bfs_tree --repeat 50 --n 3000 --m 4
  --graph-seed 42`.

Direct sample:

| Run | Mean seconds | p50 seconds | SHA |
| --- | ---: | ---: | --- |
| FNX baseline | `0.007174899580422789` | `0.006816975015681237` | `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64` |
| NetworkX baseline | `0.004935632842243649` | `0.004750382999191061` | `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64` |
| FNX after | `0.006850865441374481` | `0.006786541023757309` | `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64` |

Direct delta:
- FNX speedup: `1.0473x`.
- Residual vs NetworkX mean shrank from `1.4537x` to `1.3759x`.

Hyperfine process benchmark:

| Run | Mean seconds | Median seconds | Stddev |
| --- | ---: | ---: | ---: |
| Baseline | `0.48092092222666677` | `0.47455179476000003` | `0.027473678023905525` |
| After | `0.46374436361333343` | `0.46927279668000005` | `0.020339941769687474` |
| After confirm | `0.4777153325066667` | `0.46502464904` | `0.024179308180195935` |

Hyperfine delta:
- First after speedup: `1.0370x`.
- Confirmed speedup: `1.0061x`.

cProfile:
- Baseline native `_fnx.bfs_tree`: `0.365s / 50 calls`.
- After native `_fnx.bfs_tree`: `0.340s / 50 calls`.

Decision:
- Kept. Score `4.0 = Impact 2 * Confidence 2 / Effort 1`, above the `2.0`
  threshold.
