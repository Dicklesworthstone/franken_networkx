# br-r37-c1-emdlw — community.k_clique_communities

## Problem
Not overridden — `k_clique_communities` is `@nx._dispatchable`, so the
`from networkx... import *` re-export converted the WHOLE fnx graph to nx
(`_fnx_to_nx`, attrs and all) on every call (~78% of runtime in cProfile),
~2x slower than nx on a sparse n=300 graph. On dense graphs nx's own
percolation step is additionally O(#cliques²) and explodes to seconds.

## Levers (two)
1. **No whole-graph conversion.** The algorithm only needs `G`'s maximal
   cliques; everything after is graph-free. Compute them with fnx's native
   `find_cliques` (already nx-order) — removes the `_fnx_to_nx` tax.
2. **Union-find over (k-1)-subsets instead of an nx.Graph + connected_components.**
   nx builds a percolation graph with one node per clique and an edge per
   adjacent pair (cliques sharing ≥ k-1 nodes), then BFS — O(#cliques²) on
   dense inputs. Two maximal cliques of size ≥ k percolate **iff** they share
   ≥ k-1 nodes **iff** they share a common (k-1)-node subset; unioning all
   cliques mapping to the same (k-1)-subset yields the identical components in
   near-linear time.

Byte-identical to nx: components are emitted in lowest-clique-index order
(matching `connected_components`, which starts each component at the
lowest-index unvisited percolation-graph node = clique order), each community
is the `frozenset` union of its cliques, and the `k<2` `NetworkXError` is
preserved (raised lazily on first iteration, as nx's generator does).

Pure-Python change in `community.py`. No Rust change.

## Result (interleaved min-of-N, same host window; before = nx dispatch+convert path)
| n   | density | before (ms) | after (ms) | nx (ms)  | self-speedup | after vs nx |
|-----|---------|-------------|------------|----------|--------------|-------------|
| 300 | 0.04    | 6.49        | 2.72       | 3.50     | 2.39x        | 0.78x (1.3x faster) |
| 500 | 0.05    | 60.12       | 16.44      | 49.42    | 3.66x        | 0.33x (3.0x faster) |
| 150 | 0.25    | 521.9       | 20.50      | 498.5    | 25.5x        | 0.041x (24x faster) |
| 120 | 0.35    | 2241.1      | 36.23      | 2210.0   | 61.9x        | 0.016x (61x faster) |
|  80 | 0.50    | 6272.6      | 44.17      | 6207.8   | 142.0x       | 0.007x (141x faster) |

The win grows with density: the union-find percolation replaces nx's
O(#cliques²) clique-graph construction with a near-linear (k-1)-subset merge.

## Proof
- Golden sha256 over the order-sensitive community stream: **before == after
  == nx**, identical in every row of the table (`proof.json`).
- `proto_unionfind.py`: 1920 cases (sizes/seeds × k=2..5) + dense stress
  (p up to 0.5) vs nx — 0 fails.
- `verify_fnx_parity.py`: 1222 fnx-vs-nx(converted) cases incl. string-keyed,
  cliques-provided, and the k<2 lazy-raise contract — 0 fails.
- `tests/python/test_community_*`: 51 passed, 1 skipped.
