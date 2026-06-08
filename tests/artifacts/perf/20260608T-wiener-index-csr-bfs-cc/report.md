# wiener_index: integer-CSR BFS (br-r37-c1-wiener-csr)

## Problem
`wiener_index(G)` (unweighted) routed to the native kernel yet sat at PARITY
with nx (~1.06x, 55ms @ n=400/m=3000). The native BFS walked
`graph.neighbors(name)` then `get_node_index(name)` — a String hash lookup PER
EDGE PER SOURCE (the String-keyed adjacency tax). `global_efficiency` /
`average_shortest_path_length` already avoid this via integer CSR rows.

## Lever (ONE)
Swap the String-keyed BFS for integer-CSR BFS: `graph.neighbors_indices(u)` /
`digraph.successors_indices(u)` return the integer adjacency row directly, so
the per-source BFS is pure index work (reused `dist`/`queue` buffers, no
per-source alloc). BFS distances are independent of neighbour visit order, so
the summed scalar is byte-exact.

## Proof (behavior parity — absolute)
- 60 random graphs (undirected/directed, self-loops, disconnected→inf):
  0 mismatches (value AND int-vs-float type).
- Golden sha256 over a 12-entry corpus (undirected+directed): fnx == nx
  (`075ddee0...`).
- `pytest -k wiener`: 461 passed.

## Result (median-of-5)
| n, m, dir         | nx        | fnx (after) | speedup vs nx |
|-------------------|-----------|-------------|---------------|
| 400, 3000, undir  | 57.28 ms  | 4.75 ms     | 12.05x        |
| 800, 6000, undir  | 274.10 ms | 16.34 ms    | 16.78x        |
| 400, 3000, dir    | 62.43 ms  | 3.35 ms     | 18.63x        |

Before: ~1.06x (parity). After: 12-18.6x faster than nx.
