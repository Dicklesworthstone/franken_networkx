# perf(load_centrality): integer-CSR + parallel Newman load

## Lever
Newman load centrality (`load_centrality_generic`) ran a single-threaded
per-source BFS with a per-edge `node_idx.get(w_name)` **string HashMap lookup**,
per-source allocation, and serial accumulation into the global `load[]`. Same
proven transformation as the betweenness family: **integer adjacency built once
+ parallel Brandes-style fan-out over sources** (reused `LoadScratch` via
`map_init`), each source emitting a dense `between` delta vector (`delta[s]==0.0`
by construction). Deltas are reduced into `load[]` in **strict source order**
(chunked ~64 MiB) so the global float summation order — and the result — is
byte-identical to the sequential path. The per-source equal-share
back-propagation and the `x == source` break are preserved exactly. Gated
`n>=500`; smaller graphs use the same per-source helper sequentially.

## Proof (byte-exact vs current fnx)
`sha256` of the full score dict (sorted `repr(node)→repr(score)`):

| case | baseline | after | match |
|------|----------|-------|-------|
| BA(1500,4) undirected | d7f89d7ea8 | d7f89d7ea8 | ✓ |
| BA(2500,4) undirected | ba69d23395 | ba69d23395 | ✓ |
| gnp(1000,.012) directed | debe307171 | debe307171 | ✓ |

All byte-identical. 6 Rust unit tests + 73 Python load_centrality tests pass.

## Benchmark (warm min-of-N, release, 64-core)
| case | baseline | after | speedup |
|------|----------|-------|---------|
| BA(1500,4) undirected | 884.7 ms | 18.5 ms | **47.9x** |
| BA(2500,4) undirected | 2769.3 ms | 33.5 ms | **82.7x** |
| gnp(1000,.012) directed | 483–502 ms | 26–30 ms | **17–19x** |

## Score
Impact very high (heavy O(V·E) op, 18–83x absolute, byte-exact — combines
string-tax elimination + parallelism), Confidence high (golden sha256 + full
suite), Effort low (one coherent kernel transformation). Score ≫ 2.0.
