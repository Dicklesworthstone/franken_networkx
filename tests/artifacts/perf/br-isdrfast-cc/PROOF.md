# is_distance_regular — fast-reject pre-check (delegation/native-overcompute tax)

## Gap
`is_distance_regular(G)` routed to native `_raw_is_distance_regular`, which
ALWAYS computes the full intersection array (single-source BFS from every
node, O(V*(V+E))). nx short-circuits in microseconds via
`intersection_array`'s opening guard `not is_regular(G) or not is_connected(G)`.
On a non-regular graph (the overwhelming common input) fnx was ~789x SLOWER
than nx (7.89ms vs 0.01ms on connected_watts_strogatz(200,6,0.3)).

## Lever (one)
A distance-regular graph is by definition regular AND connected. Add nx's
exact cheap pre-check to the Python wrapper before the native pass:
`if not is_regular(G) or not is_connected(G): return False`.
Both predicates are exact; the native O(V*(V+E)) pass now runs only for
genuinely regular+connected candidates.

## Behavior parity / golden sha256 (MY EDITS == HEAD, ~80 graphs:
## complete/cycle/random-regular/watts/BA/petersen/icosahedral/hypercube/K44/path)
314a837a245eca36eff03e7e75ff5a8746329b2b3e52a151acb54cb4550e73ce

12-case spot check (DR-true, regular-non-DR, disconnected-regular, non-regular,
K33) vs upstream nx: 0 mismatches.

## Speed (connected_watts_strogatz(200,6,0.3), min of 50)
fnx 7.89ms -> 1.9us (~4000x self-speedup); nx 8.6us.
Result: 789x SLOWER than nx -> 4.66x FASTER than nx.

## Tests
1188 passed (distance_regular/regular/intersection/distance_measures), 0 fail.
