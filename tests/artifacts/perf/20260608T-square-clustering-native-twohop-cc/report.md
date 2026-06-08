# square_clustering: native integer-CSR two-hop kernel (br-r37-c1-sqclfast)

## Problem
`square_clustering(G)` for simple undirected graphs ran a pure-Python port of
NetworkX's optimized (Lind/Zhang) two-hop algorithm — Python `set` algebra over
raw neighbor rows. Measured at **parity** with nx (1.01x), i.e. no win: the
neighbor-set intersections dominate and are identical Python work in both libs.

## Lever (ONE)
Port the *same* two-hop algorithm to a native integer-CSR kernel
(`fnx_algorithms::square_clustering_pairs`): build integer adjacency rows
(self-loops dropped), and replace every `set & set` / `in` test with O(1)
monotonic stamp-array membership. Kernel returns exact integer
`(squares, potential)` per node in insertion order; the binding
(`square_clustering_fast`) reproduces nx's `squares/potential if potential>0
else 0` byte-for-byte (preserving int-`0` vs float). Python wrapper routes the
`nodes is None and type(G) is Graph` case to it; subset/single-node/multigraph/
SubgraphView/DiGraph keep the Python path.

## Proof (behavior parity — absolute)
- 60 random graphs (n 5..120, incl. self-loops), identical edge sequence:
  **0 mismatches** (values, key order, and int/float types).
- Golden sha256 over fixed 6-graph corpus: fnx == nx
  `b950b4ee2f9599ab55c2919e9e57f357905ae8f8fe19a34d83c52d86ad50ca56`.
- Edge cases (empty/single/K5/subset/single-node-arg/DiGraph) all match nx.
- `pytest -k "square_clust or cluster"`: 485 passed, 6 skipped.

## Result (median-of-9, warm)
| n, m        | nx        | fnx (after) | speedup vs nx |
|-------------|-----------|-------------|---------------|
| 1500, 7500  | 61.09 ms  | 2.37 ms     | 25.7x         |
| 2000, 12000 | 127.10 ms | 5.19 ms     | 24.5x         |
| 800, 8000   | 133.71 ms | 5.54 ms     | 24.2x         |

Before: 1.01x (parity). After: ~24-26x faster than nx.
