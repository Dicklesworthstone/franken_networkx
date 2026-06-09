# is_bipartite: integer 2-coloring (bool only) — 16x slower -> 8.3x FASTER (br-r37-c1-bipartidx)

## Problem
is_bipartite(graph) called bipartite_sets(graph), which for a yes/no answer built a
String-keyed color map, SORTED all node names, and produced two Vec<String> partition
outputs -> 16x slower than nx.

## Lever
Dedicated integer 2-coloring DFS over the CSR adjacency (neighbors_indices) with a
Vec<i8> color array. Bipartiteness is traversal-order-invariant so no sort and no set
materialisation. A self-loop colors a node adjacent to itself -> not bipartite
(matches nx's odd cycle). bipartite_sets (which needs the partitions) is untouched.

## Proof
- Parity vs nx 0/85 (bipartite/random graphs + isolated, self-loop, even/odd cycle,
  disconnected-mixed, string-node cases); bipartite.sets() still correct; pytest -k
  bipartite 441 passed.
- n=4000 (min-of-15): 16x slower -> 0.14x = 8.3x FASTER (0.50ms vs nx 4.16ms).
