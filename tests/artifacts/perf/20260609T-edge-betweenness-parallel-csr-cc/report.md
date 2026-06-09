# perf(edge_betweenness_centrality): integer-CSR + parallel Brandes — br-r37-c1-0xt21 followup

## Lever
The edge-Brandes kernel was the unoptimized sibling of node betweenness:
- per-step `HashMap<(String,String), f64>` accumulation — rebuilt a canonical
  `(u,v)` **String pair** (2 allocs + tuple hash) on every dependency edge;
- String adjacency walk (`neighbors_iter` + `get_node_index().unwrap()`) per
  neighbor instead of precomputed integer adjacency;
- per-source `predecessors/sigma/distance/dependency` re-allocation;
- single-threaded.

One coherent transformation: **integer-CSR adjacency carrying canonical edge ids
+ parallel Brandes over sources with strict-source-order reduction**.
`adjacency[v]` yields `(w, edge_id)` directly, so the hot dependency loop does
`delta[edge_id] += contribution` — no string build, no hash lookup. Each source
produces a dense per-edge delta vector (O(|E|) bulk, fanned over rayon workers
with a reused `EdgeBrandesScratch`); deltas are reduced into the global score in
strict source order (chunked to cap delta memory ~64 MiB), so float summation
order — and the result — is byte-for-byte identical to the sequential path.
Undirected edges canonicalized by node **string** order (indices follow
insertion order) so emitted `(left,right)` endpoints match the prior output.
Gated `n>=500`; smaller graphs use the same integer kernel sequentially.

## Proof (byte-exact vs current fnx)
`sha256` of the full edge-score dict (canonical sorted edge tuple → `repr(score)`):

| case | baseline sha | after sha | match |
|------|--------------|-----------|-------|
| BA(1500,4) undirected | 590c12d72c2f | 590c12d72c2f | ✓ |
| BA(2500,4) undirected | 594a7ca87627 | 594a7ca87627 | ✓ |
| gnp(800,.01) directed | 58789073ad87 | 58789073ad87 | ✓ |

4 Rust unit tests + 33 Python edge_betweenness tests (incl. key-order parity vs
nx) pass.

## Benchmark (warm min-of-N, release, 64-core)
| case | baseline | after | speedup |
|------|----------|-------|---------|
| BA(1500,4) undirected | 1246.2 ms | 33.9 ms | **36.7x** |
| BA(2500,4) undirected | 3715.2 ms | 75.0 ms | **49.6x** |
| gnp(800,.01) directed | 320.5 ms | 16.1 ms | **19.9x** |

## Score
Impact very high (one of the heaviest O(V·E) ops, 19–50x absolute, byte-exact),
Confidence high (golden sha256 + full suite), Effort low (one coherent kernel
rewrite, isolated). Score ≫ 2.0.
