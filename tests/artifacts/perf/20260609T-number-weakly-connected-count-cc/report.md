# number_weakly_connected_components: integer component-count BFS — 11x slower -> 4.4x FASTER (br-r37-c1-weakcount)

## Problem
number_weakly_connected_components(digraph) was `weakly_connected_components(dg).len()`,
materialising EVERY weakly-connected component as a Vec of String node NAMES (plus a
String-keyed visited set) just to count them -> 11x slower than nx. Same anti-pattern
as is_weakly_connected (br-r37-c1-weakconn).

## Lever
Count components with an integer BFS over the undirected projection (successors_indices
u predecessors_indices, by index) + Vec<bool> visited. No String node sets, no per-
component Vec materialisation. O(|V|+|E|).

## Proof
- Parity vs nx 0/200 (50 seeds x {1,2,5} components); empty=0, 5-isolated=5;
  pytest -k weakly_connected 31 passed.
- n=3000 deg8 (min-of-15): 11x slower -> 0.22x = 4.4x FASTER (0.51ms vs nx 2.27ms).
