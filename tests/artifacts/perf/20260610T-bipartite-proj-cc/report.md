# perf(bipartite.projected_graph): de-delegate, in-process

br-r37-c1-mlfma

## Problem
`bipartite.projected_graph` delegated to nx: it ran nx's algorithm on the fnx
graph `B` (through fnx's slow per-access adjacency views) and then rebuilt the
result with `_from_nx_graph`. Split at 150×120 (3012 result edges):
nx-algo-on-fnx-views 5.07 ms + `_from_nx_graph` **7.90 ms (61%)** = 13 ms.
**3.9–4.2× slower than nx.**

## Lever (one)
De-delegate the common case (simple undirected fnx `Graph`, no multigraph):
snapshot `B`'s adjacency ONCE via the native key-only binding
(`_native_adjacency_keys`), then build the fnx projection directly — for each
node `u` in `nodes`, join it to every second-neighbour `{v for nbr in adj[u] for
v in adj[nbr] if v != u}`. No nx round-trip, no `_from_nx_graph` conversion; node
attrs (`B.nodes[n]`) and graph attrs (`B.graph`) are copied as nx does. Directed
/ multigraph / nx-typed `B` keep the delegation path. The projection's edge set
is what matters (the parity tests compare sorted edges).

Touched: `python/franken_networkx/bipartite.py`. Python-only.

## Proof (nx-exact)
`harness_proof.py`: 22 cases — bipartite gnp ×10 seeds × both partitions, plus
string-labelled bipartite and a single-node projection. Compared nodes+attrs,
sorted edges, and graph dict **== nx, 0 mismatches**.
Golden sha256 (== nx):
`82da444c2642c7c5062233300c2eb36881e6a2dccff3ff636642ebe2b2efe8bd`
pytest -k "projected/bipartite": **445 passed**.

## Timing (warm interleaved min-of-5, backend disabled, random_graph(a,b,p))
| input | baseline fnx | nx | base ratio | new fnx | new ratio | self-speedup |
|-------|-------------:|---:|-----------:|--------:|----------:|-------------:|
| 150×120 | 13.08 ms | 3.30 ms | 3.89× | 5.35 ms | 1.62× | 2.4× |
| 250×200 | 39.14 ms | 9.25 ms | 4.12× | 14.58 ms | 1.58× | 2.7× |
| 400×300 | 96.85 ms | 23.19 ms | 4.23× | 35.31 ms | 1.52× | 2.7× |

3.9–4.2× slower → 1.5–1.6× (2.4–2.7× self-speedup). The eliminated cost is the
`_from_nx_graph` conversion + slow-view algorithm; the residual 1.5× is the fnx
construction of the (thousands-of-edges) result graph.

## Score
Impact: high (2.4–2.7× self-speedup on a core bipartite primitive; eliminates the
double-conversion delegation tax). Confidence: high (byte-identical golden sha,
0/22 incl. string/single/both-partitions, 445 tests). Effort: low (de-delegate
one wrapper, Python-only). Score >> 2.0.
