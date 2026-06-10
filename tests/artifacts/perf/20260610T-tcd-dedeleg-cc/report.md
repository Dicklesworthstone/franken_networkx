# perf(transitive_closure_dag): de-delegate, run in-process

br-r37-c1-e6yce

## Problem
`transitive_closure_dag` **delegated to NetworkX**: `_networkx_graph_for_parity(G)`
built a full fnx→nx copy, nx ran the algorithm, then `_from_nx_graph` rebuilt the
(larger) closure graph fnx-side. Measured split at n=2000 gn_graph: fnx→nx 13.5 ms
+ nx algo 23.7 ms + nx→fnx 21.8 ms = **59% of the 59 ms was the two conversions**.
Result: **2.6–3.2× slower than nx**.

It delegated (per br-r37-c1-utmy6) because nx appends each `adj[v]`'s transitive
edges in CPython **set-iteration order**, which an order-naive native port can't
reproduce.

## Lever (one)
Run nx's algorithm **in-process on the fnx DiGraph** — no nx round-trip. nx's
`transitive_closure_dag` is `TC = G.copy(); for v in reversed(topo_order):
TC.add_edges_from((v,u) for u in descendants_at_distance(TC, v, 2))`, and
`descendants_at_distance` is `set(bfs_layers(G, source)[distance])`. The key to
byte-exact order: `bfs_layers` builds each layer as a **LIST** in BFS discovery
order (`next_layer.append`), so reproducing that list and then `set(list)` gives
the identical CPython set-iteration order that `add_edges_from` consumes — and
hence identical `adj[v]` edge order. (Building the layer as a set directly
scrambles the insertion order — that was the first, rejected, attempt.) The
distance-2 BFS uses the raw Rust successor accessor (`_raw_neighbors_dispatch`),
skipping the AtlasView per-access tax.

Gated to `type(G) is DiGraph`; MultiDiGraph / SubgraphView / nx-private-storage
graphs keep the proven nx-delegation path. Cycle → `NetworkXUnfeasible` (inherited
from `topological_sort`), undirected → `NetworkXNotImplemented` (unchanged).
Python-only — no Rust rebuild.

## Proof (nx-exact)
`harness_proof.py`: 19 cases — gn_graph ×8 seeds, random DAGs ×4, chain, diamond
(multi-path), edge+graph attrs, explicit `topo_order`, empty, single node, string
labels. **0 mismatches vs nx** on an ORDERED fingerprint (nodes+attrs, edges in
adj-iteration order +attrs, graph dict).
Golden sha256 (identical to nx):
`f13d3350a58f4b3a031bdfcf4853ec07f83ed585f25d3c2e4e6e5d5c8b4bee27`

pytest -k "transitive_closure/transitive/dag": **467 passed**.

## Timing (warm min-of-7, gn_graph(n))
| n    | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|------|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 1000 |   25.13 ms   | 10.28 ms |     2.63×      |  7.65 ms | **0.74×** |    3.3×      |
| 2000 |   63.72 ms   | 20.98 ms |     3.16×      | 22.51 ms |   1.07×   |    2.8×      |
| 4000 |  132.56 ms   | 42.92 ms |     2.98×      | 55.76 ms |   1.30×   |    2.4×      |

2.6–3.2× slower → parity-to-faster (2.4–3.3× self-speedup). The residual at n=4000
is the BFS Python loop over fnx adjacency (nx pays the same over native dicts).

## Score
Impact: high (eliminates the double-conversion delegation tax on a closure
primitive; 2.4–3.3× self-speedup, now ≤ nx at small/mid sizes). Confidence: high
(byte-identical ordered golden sha, 0/19 incl. attrs/topo_order/multi-path,
467 tests). Effort: low (Python-only, mirrors nx verbatim). Score ≫ 2.0.
