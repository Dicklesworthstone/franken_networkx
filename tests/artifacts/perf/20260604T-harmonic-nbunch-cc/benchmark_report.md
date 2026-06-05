# harmonic_centrality(nbunch) — native single-source BFS (br-r37-c1-19lrl)

## Problem
`harmonic_centrality(G, nbunch=[few])` delegated to networkx, paying a full fnx->nx
O(V+E) graph conversion on every call just to run one BFS per nbunch node. On n=1500,
nbunch=5 that conversion dwarfed nx's compute: ~73.9ms vs nx's 2.8ms — **~26x SLOWER
than networkx** (hidden by the default whole-graph benchmark, which uses the fast Rust
all-pairs kernel).

## Lever (ONE)
For the standard unweighted, undirected case (`distance is None`, `sources is None`,
`not G.is_directed()`), networkx's algorithm reduces to: for each `v` in nbunch,
`harmonic(v) = sum over reachable u (d != 0) of 1/d(v, u)`, accumulated with a running
`+=` in `single_source_shortest_path_length(G, v)` dict order. Compute that directly on
the fnx graph using fnx's native single-source BFS — no conversion, no delegation.
Directed / distance / sources cases still delegate to networkx.

## Behavior parity (isomorphism proof)
fnx's native `single_source_shortest_path_length` emits distances in networkx's exact BFS
dict order, so the running float sum `cc += 1/d_uv` is **byte-identical** to networkx (not
merely tolerance — maxdiff 0.0). The result dict is keyed by `set(G.nbunch_iter(nbunch))`
exactly as nx does, so dict key order matches too (verified on int AND string-keyed graphs
where hash randomization makes set order non-trivial).

- Parity sweep: 44 cases — int/str keys, single/multi/scalar nbunch, disconnected,
  self-loop, isolated node, plus a directed graph confirming it still delegates exactly —
  **0 mismatches** (values AND dict key order).
- Golden sha256 over all (n, keytype, node, value) tuples:
  `78ffcf29e7eaa3218b5ea26edf96d33820a26af2409d5697743d57dd4257fd92`.
- Existing suite: `pytest -k "harmonic or centrality"` → 1217 passed, 6 skipped, 1 xpassed.

## Benchmark (min-of-11, ms)
| graph (n, p=0.02, nbunch=5) | networkx | fnx before (delegated) | fnx after | after vs nx |
|-----------------------------|----------|------------------------|-----------|-------------|
| n=800                       | 1.718    | ~40                    | 0.769     | 2.23x faster |
| n=1500                      | 2.896    | 73.9                   | 1.461     | 1.98x faster |

Before: ~26x SLOWER than nx (delegated conversion). After: ~2x FASTER than nx; ~52x faster
than the old delegated path.

## Score
Impact: high (26x-slower → 2x-faster swing; 52x self-speedup on the hot small-nbunch path).
Confidence: high (bit-exact, 44-case golden incl. string keys + key order, 1217 tests).
Effort: low (single Python fast-path, no Rust change). → Score >> 2.0.
