# is_weakly_connected: single integer BFS — 12x slower -> 4.9x FASTER (br-r37-c1-weakconn)

## Problem
is_weakly_connected(digraph) was `number_weakly_connected_components(digraph) == 1`,
which builds EVERY weakly-connected component as a Vec of String node names (O(|V|)
String allocs) just to test for a single component -> 12x slower than nx. It also
gated the has_eulerian_path directed path-case (the residual from br-r37-c1-eulerpathdir).

## Lever
A single integer BFS over the UNDIRECTED projection (successors_indices ∪
predecessors_indices, by index) from node 0 — weakly connected iff it reaches all
nodes. O(|V|+|E|), zero String allocs, no component materialisation.

## Proof
- Parity vs nx 0/153 (50 seeds x {1,2,3} weak components + single-node / 2-node /
  isolated edge cases); pytest -k weakly_connected 54 passed.
- is_weakly_connected n=3000 deg8: 12x slower -> 0.21x = 4.9x FASTER (0.49ms vs nx
  2.37ms). Cascade: has_eulerian_path directed PATH case n=3000 2.6x slower ->
  9.6x FASTER.
