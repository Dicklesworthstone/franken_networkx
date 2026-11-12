# local/global_reaching_centrality: BFS-distance fast path + skip vacuous neg-weight guard (br-r37-c1-lrcdist)

local_reaching_centrality(G, v) with weight=None was up to ~8x SLOWER than
networkx. Two costs, neither needed for weight=None:
1. `is_negatively_weighted(G, weight=None)` materialized the ENTIRE
   edges(data=True) view (~12ms at n=1500) to evaluate `any(None in data ...)`,
   which is False for every graph that does not key an edge attribute by the
   literal None object.
2. `shortest_path(G, source=v)` built full node-list paths, but the weight=None
   result only consumes BFS distances (`len(reachable)` for directed,
   `sum(1/dist)` for undirected).

Lever: (1) guard the negative-weight check with `weight is not None`; (2) use
`single_source_shortest_path_length` (distances, identical BFS-discovery order)
instead of `shortest_path`. Same fast path proven for global_reaching_centrality
(br-r37-c1-04z53). The guard is also applied to global_reaching_centrality.

Proof: golden sha256 over fnx.local_reaching_centrality (055bf58b...) and
fnx.global_reaching_centrality (97623c71...) on a 120-graph directed+undirected
corpus IDENTICAL before and after; 1987/1987 value parity vs networkx; 555
reaching-related tests pass.

local_reaching_centrality, interleaved min-of-15:

| n | dir | m | nx (ms) | fnx (ms) | speedup |
|---|---|---|---|---|---|
| 600 | dir | 7156 | 0.939 | 0.352 | 2.67x |
| 600 | undir | 3571 | 0.967 | 0.102 | 9.44x |
| 1500 | dir | 22513 | 2.671 | 0.970 | 2.75x |
| 2000 | dir | 19892 | 2.873 | 1.098 | 2.62x |
| 1000 | undir | 9974 | 2.191 | 0.188 | 11.68x |

before: 0.12x-0.59x SLOWER.  after: 2.62x-11.68x FASTER.
global_reaching_centrality (sssp-bound): 1.21x -> 1.29x.
