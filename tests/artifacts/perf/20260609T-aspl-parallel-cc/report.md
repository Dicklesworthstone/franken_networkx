# perf(average_shortest_path_length): parallel all-pairs BFS

## Lever
`average_shortest_path_length` (+ `_directed`) ran a single-threaded per-source
BFS over integer adjacency. The result is `sum(d(u,v)) / (n(n-1))` — and the
distance **sum is an integer**, so reducing per-source sums in any order is
byte-identical to the sequential accumulation (no float-order concern at all).
Fan the per-source BFS out over rayon workers (reused `AsplScratch` via
`map_init`); shared `aspl_bfs_source` / `aspl_finalize` / `aspl_run_sources`
helpers. Disconnected (undirected) / not-strongly-connected (directed) graphs —
any source not reaching all `n` nodes — yield `INFINITY` exactly as before (the
Python wrapper raises `NetworkXError`). Gated `n>=500`; smaller graphs run the
same helper sequentially.

## Proof (exact value vs current fnx)
Full `repr(float)` of the result:

| case | baseline | after | match |
|------|----------|-------|-------|
| BA(2000,4) undirected | 3.409777388694347 | 3.409777388694347 | ✓ |
| BA(3500,4) undirected | 3.5921079492099786 | 3.5921079492099786 | ✓ |
| gnp(900,.02)+cycle directed | 2.6411308861698184 | 2.6411308861698184 | ✓ |

Exact. Disconnected undirected + not-SC directed both raise `NetworkXError`
(matches nx); small n=50 sequential path exact vs nx (diff 0.0); 24 Python
average_shortest_path tests pass.

## Benchmark (warm min-of-N, release, 64-core)
| case | baseline | after | speedup |
|------|----------|-------|---------|
| BA(2000,4) undirected | 77.6 ms | 3.4 ms | **23.0x** |
| BA(3500,4) undirected | 263.9 ms | 10.2 ms | **25.8x** |
| gnp(900,.02) directed | 21.3 ms | 1.9–2.6 ms | **8–11x** |

## Score
Impact high (heavy O(V·(V+E)) op, 8–26x absolute, exact), Confidence high (exact
value + disconnected parity + full suite), Effort low (one coherent
transformation; integer sum → trivially order-invariant). Score ≫ 2.0.
