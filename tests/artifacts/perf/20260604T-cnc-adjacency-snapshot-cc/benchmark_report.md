# common_neighbor_centrality — snapshot adjacency to sets, kill per-pair PyO3 tax (br-r37-c1-cncadj)

## Problem
nx's `common_neighbor_centrality` (CCPA) scores every node pair in `ebunch`; the default
ebunch is *all* O(V^2) non-edges. nx scores each with `len(nx.common_neighbors(G, u, v))`
over native dict sets. fnx mirrored the structure but called `fnx.common_neighbors(G, u, v)`
per pair — each re-walks the String-keyed PyO3 adjacency (~3.8x slower per call). On n=400
(75,790 non-edges) the common-neighbors loop alone was 487ms (vs nx 125ms), making the whole
function **~2.3x SLOWER than nx** (476ms vs 196ms). The all-pairs `shortest_path_length` dict
was already fast (fnx 17.6ms vs nx 51.6ms) — not the bottleneck.

## Lever (ONE)
Snapshot the adjacency to Python sets ONCE — `adj = {n: set(nbrs) for n, nbrs in G.adjacency()}`
— then compute `(adj[u] & adj[v]) - {u, v}` in the hot loop instead of calling the per-pair
PyO3 `common_neighbors` wrapper. One O(V+E) pass replaces ~V^2 String-keyed adjacency walks.

## Behavior parity (isomorphism proof)
`(adj[u] & adj[v]) - {u, v}` is byte-identical to nx's
`{w for w in G[u] if w in G[v] and w not in (u, v)}` (the `-{u, v}` reproduces nx's
self-loop / existing-edge ebunch exclusion). All scores are the same float expression.

- Sweep: 80 random graphs (n 4..35, ~30% string-relabelled, self-loops on 1/6) × alpha
  {0.8, 1, 0.0, 0.5, 0.99} = **400/400 exact** (scores AND (u,v) yield order). Plus explicit
  ebunch incl. existing edges, missing-node NodeNotFound, directed/multigraph rejection.
- Golden sha256: `66902d90839f3650b59d966f7026529c6b19b915076e60d38af6e92e0a04790f`.
- Tests: `pytest -k "common_neighbor or link_pred or prediction"` → 403 passed.

## Benchmark (warm min-of-4, ms)
| n (gnp p=0.05) | networkx | fnx before | fnx after | after vs nx |
|----------------|----------|-----------|-----------|-------------|
| 300            | 97.9     | ~227*     | 41.8      | **2.34x**   |
| 400            | 197.0    | 476       | 83.1      | **2.37x**   |

*before ≈ 2.3x slower than nx. After: 2.34-2.37x FASTER (~5.3x self-speedup on n=400).

## Score
Impact: high (2.3x-slower -> 2.37x-faster swing, large absolute ms). Confidence: high
(byte-exact, 400-case golden incl self-loops/string keys/all alphas, 403 tests). Effort: low
(one Python snapshot, no Rust change). → Score >> 2.0.
