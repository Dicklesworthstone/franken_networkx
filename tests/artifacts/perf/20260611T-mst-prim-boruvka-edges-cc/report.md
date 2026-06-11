# perf: minimum/maximum_spanning_tree(prim/boruvka) — build from native spanning_edges

Bead: br-r37-c1-6vq1m (filed). minimum_spanning_tree / maximum_spanning_tree with
algorithm='prim' or 'boruvka' delegated the whole tree to nx (full fnx->nx conversion +
nx's algorithm), even though fnx's own minimum_spanning_edges already has a byte-exact
native Prim kernel (bb4b9ec49) and an in-process Borůvka. Measured prim 4.0-6.1x slower
than nx, boruvka 1.4-1.5x slower.

## Lever (ONE)
nx's minimum_spanning_tree is literally "assemble a graph from minimum_spanning_edges".
Do the same in fnx: build the tree from fnx's own minimum_spanning_edges(algorithm=...)
generator (native Prim / in-proc Borůvka) instead of delegating. Simple Graph + str
weight + ignore_nan=False (NaN / callable-weight / multigraph still delegate, exactly as
minimum_spanning_edges itself falls back). Also makes minimum_spanning_tree internally
CONSISTENT with minimum_spanning_edges (the delegated path could pick different tie-break
edges than fnx's own edges generator).

## Proof (byte-exact)
- Golden over a 13-graph corpus x {prim, boruvka} x {min, max} asserts EXACT edge set
  (u,v,weight sorted) == nx for every case: MST_GOLDEN_SHA=c37a20167c4fdfdace55cbf55fbd372e60da4838ce7f9361ac6bd156b038c4ef
- 266 spanning_tree conformance (exact-edge, all 3 algorithms, STRUCTURED+RANDOM fixtures)
  + 1314 spanning/mst/tree tests pass. Cost (unique optimum) matches nx at n=300/800/1500.

## Benchmark (connected_watts_strogatz, int weights, min-of-8)
| case          | nx (ms) | fnx before | fnx after | before vs nx | after vs nx  |
|---------------|---------|------------|-----------|--------------|--------------|
| prim n=800    | 3.60    | ~22 (6.1x) | 4.24      | 6.1x slower  | 1.18x slower |
| prim n=1500   | 8.16    | ~38 (4.4x) | 9.06      | 4.4x slower  | 1.11x slower |
| boruvka n=800 | 23.8    | ~32 (1.4x) | 11.68     | 1.4x slower  | 2.04x FASTER |
| boruvka n=1500| 51.3    | ~74 (1.4x) | 28.39     | 1.4x slower  | 1.85x FASTER |

prim ~4-6x slower -> ~1.1-1.2x (3-5x self-speedup); boruvka 1.4x slower -> ~2x FASTER.
Byte-exact, pure-Python.
MST_GOLDEN_SHA=c37a20167c4fdfdace55cbf55fbd372e60da4838ce7f9361ac6bd156b038c4ef
