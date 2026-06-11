# perf: weighted wiener_index — snapshot adjacency once (byte-exact)

Bead: br-r37-c1-lli0b. wiener_index(weight=...) ran a pure-Python per-source
Dijkstra calling G.neighbors + G.get_edge_data INSIDE the hot loop = O(V*E)
AdjacencyView wrapper round-trips -> ~5.5x slower than nx (786ms vs 141ms, n=300).

## Lever (ONE)
Snapshot the (Python-visible, weight-mutation-fresh) adjacency ONCE into a plain
dict, then run the IDENTICAL BFS/Dijkstra over it (O(E) build). Same per-source
order, same neighbour order, same float-sum order => byte-exact with nx AND the old
path. Multigraph parallel-edge min-weight and the negative-weight ValueError kept.

(Rejected: routing through native all_pairs_dijkstra_path_length is ~3x faster than
nx but sums distances in a different order -> float ULP divergence, NOT byte-exact;
verified native_eq=False on watts/geo corpora while the snapshot matched nx exactly.)

## Proof (byte-exact)
- Golden over 6 cases (watts/BA/geo weighted simple, directed strongly-connected,
  multigraph weighted with min-parallel semantics, unweighted multigraph) compares
  repr() (exact float bit pattern) of fnx vs nx — all equal; SHA UNCHANGED vs
  baseline: ec0d5ee16073faf5ee4c35b16c8c51a03998dc56658855455dc32167cd871960
- Focused pytest (wiener): 461 passed.

## Benchmark (weighted, watts-strogatz n=300, min-of-7)
| metric          | value             |
|-----------------|-------------------|
| nx              | 141 ms            |
| fnx before      | 786 ms (5.56x slower) |
| fnx after       | 138-140 ms (~parity, 0.98x) |

~5.6x self-speedup; 5.56x-slower-than-nx -> nx parity, byte-exact. Pure-Python.
