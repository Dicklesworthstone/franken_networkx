# perf(clustering/triangles single-node): local-universe snapshot

br-r37-c1-triloc

## Problem
Single-node / nbunch `clustering(G, n)` and `triangles(G, n)` were O(V+E) and
scaled with graph size while nx is O(deg(n)):
- `clustering(G, 0)`: 78x slower @ n=400 -> 408x @ n=1600 (fnx 1186us->4116us,
  nx ~10-16us constant). The Python path's `_triangles_and_degree_iter_local`
  snapshotted the WHOLE graph adjacency (`{u: set(G[u]) for u in G}`) even for
  one node.
- `triangles(G, 0)`: 12x @ n=400 -> 46x @ n=1600. Called whole-graph
  `_raw_triangles(G)` then indexed one node.

## Lever (one)
Local-universe snapshot: when `nodes` is given, `_triangles_and_degree_iter_local`
snapshots only the queried nodes + their neighbors (counting triangles through u
only ever touches N(u) and the adjacency of each w in N(u)). Route
`triangles(G, nbunch)` through the same local helper (triangles(n) ==
triangle_count // 2) instead of whole-graph `_raw_triangles`. Whole-graph
(nodes=None) paths unchanged.

Touched: python/franken_networkx/__init__.py (_triangles_and_degree_iter_local,
triangles). Python-only.

## Proof (nx-exact)
444 cases: random gnp n=1..40 (+ isolated nodes) x {single-node x3, nbunch,
whole-graph} for BOTH clustering and triangles. 0 mismatches vs nx (values +
type: clustering keeps int-0/float distinction). pytest -k
"clustering or triangle or transitivity": 762 passed, 6 skipped.

## Timing
| call             | before (n=400 / n=1600) | after (n=400 / n=1600) |
|------------------|-------------------------|------------------------|
| clustering(G,0)  | 78x / 408x  (scales)    | 2.2x / 2.3x (constant) |
| triangles(G,0)   | 12x / 46x   (scales)    | 2.2x / 2.2x (constant) |

Gap no longer scales with |V|; residual ~2.2x is fixed per-call coercion +
set(G[node]) PyO3 for the local universe. (nx ~10us vs fnx ~22us, both O(deg).)

## Score
Impact: high (clustering/triangles single-node are very common; removes
O(V+E)->O(deg) blowup, 408x->2.2x). Confidence: high (0/444 vs nx, 762 tests).
Effort: low (one-file Python). Score >> 2.0.
