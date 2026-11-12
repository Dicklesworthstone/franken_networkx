# perf(closeness/harmonic_centrality): parallel independent-per-source BFS

## Lever
`closeness_centrality` and `harmonic_centrality` ran a single-threaded reverse-BFS
per source. Each source's score is a **pure function of its own BFS** — no
cross-source accumulation — so the per-source passes fan out over rayon workers
(reused `CentralityBfsScratch` via `map_init`) with **zero ordering or
float-summation-order concern**; results collect in source order. Harmonic's
`1/d` additions stay in BFS pop order per source, so byte-identical to
sequential. Gated `n>=500`; smaller graphs use the same per-source helper
sequentially. Shared `reverse_adjacency` + `closeness_source`/`harmonic_source`
helpers; `distance` switched to an `i64` `-1` sentinel.

## Proof (byte-exact vs current fnx)
`sha256` of the full score dict (sorted `repr(node)→repr(score)`):

| case | closeness | harmonic |
|------|-----------|----------|
| BA(2000,4) undirected | f303d28551 ✓ | adaed92da8 ✓ |
| BA(3000,4) undirected | 911f48642d ✓ | 75a9393c3f ✓ |
| gnp(1200,.01) directed | ✓ | ✓ |

All 8 byte-identical. 55 Rust centrality unit tests + 205 Python
closeness/harmonic tests pass.

## Benchmark (warm min-of-N, release, 64-core)
| case | closeness | harmonic |
|------|-----------|----------|
| BA(2000,4) | 96.0→7.4 ms (**13.0x**) | 89.3→6.1 ms (**14.7x**) |
| BA(3000,4) | 232.9→12.1 ms (**19.2x**) | 221.9→11.9 ms (**18.7x**) |
| directed(1200) | 10.2x | 7.8–8.3x |

## Score
Impact high (two heavy O(V·(V+E)) ops, 13–19x absolute, byte-exact), Confidence
high (golden sha256 + full suite), Effort low (one coherent transformation,
trivially correct since per-source independent). Score ≫ 2.0.
