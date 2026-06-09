# perf(betweenness_centrality): parallel Brandes (rayon over sources) — br-r37-c1-0xt21

## Lever
Single-threaded Brandes was the heaviest common O(V·E) centrality op. Fan the
per-source BFS + dependency-accumulation passes out over rayon workers, then
**reduce the per-source delta vectors into the global score in strict source
order**. nx accumulates `centrality[w] += delta` over sources `s = 0..n`;
replaying the reduction in that exact order keeps the float summation order — and
therefore the result — byte-for-byte identical to the sequential path.

- Each worker reuses a `BrandesScratch` (via `map_init`) — same allocation
  profile as the sequential loop.
- Sources chunked to cap peak delta memory at ~64 MiB; order preserved within
  and across chunks (collected `Vec` is already source-ordered).
- Gated at `n >= 500`; smaller graphs keep the unchanged sequential path.
- Covers undirected + directed (shared `betweenness_centrality_generic<G>`),
  and normalized / endpoints / unnormalized.

## Proof (byte-exact vs current fnx)
`sha256` of the full score dict (canonical sorted `repr(node)→repr(score)`):

| case | baseline sha | after sha | match |
|------|--------------|-----------|-------|
| n2000 normalized   | a584a758bd17 | a584a758bd17 | ✓ |
| n2000 endpoints    | fe28088b9477 | fe28088b9477 | ✓ |
| n2000 unnormalized | 990ec22b08b5 | 990ec22b08b5 | ✓ |
| n3000 normalized   | f5869953b313 | f5869953b313 | ✓ |
| n3000 endpoints    | 448cc999beb4 | 448cc999beb4 | ✓ |
| n3000 unnormalized | 483564bcb75d | 483564bcb75d | ✓ |

All 6 byte-identical. vs genuine networkx: max abs diff 1e-17…1e-19 (ULP);
directed graphs at the threshold boundary (n=499 seq / 500/501 par) consistent.
Test suites: 110 `betweenness_centrality` Python tests pass; 16 edge/group
betweenness parity tests pass.

## Benchmark (warm min-of-N, BA(n,4), release)
| case | baseline | after | speedup |
|------|----------|-------|---------|
| n=2000 normalized | 233.1 ms | 22.3 ms | **10.45x** |
| n=3000 normalized | 547.7 ms | 42.7 ms | **12.83x** |

(64-core host; absolute-cost reduction on top of an already-faster-than-nx kernel.)

## Score
Impact high (heaviest common O(V·E) op, 10–13x absolute), Confidence high
(byte-exact golden sha + ULP nx parity + full suite), Effort low (one lever,
isolated parallel path, sequential path untouched). Score ≫ 2.0.
