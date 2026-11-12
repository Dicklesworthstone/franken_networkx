# perf(approximation.diameter): native undirected 2-sweep

br-r37-c1-1zcpr (perf portion)

## Problem
`fnx.approximation.diameter` went through the generic _ApproximationNamespace
__getattr__: converts fnx->nx (`_networkx_graph_for_parity`) then runs nx's
2-sweep, whose internal BFS dispatches BACK onto slow fnx adjacency. ~12.8x
slower than genuine nx (n=500 BA: 0.29ms nx vs 3.97ms fnx). Removing the
conversion alone does NOT help (the BFS-on-fnx-views is the cost).

## Lever (one)
Add a concrete `diameter` method that runs nx's undirected 2-sweep directly over
fnx's native integer-CSR BFS + eccentricity: `seed.choice(list(G))` ->
`single_source_shortest_path_length` (nx-discovery-order) -> last (farthest)
node -> `eccentricity(node)`. Directed (2-dSweep) keeps the delegated path.

Touched: python/franken_networkx/__init__.py (_ApproximationNamespace.diameter).

## Proof (behavior-preserving)
Byte-identical to the previous fnx result over 150 cases (BA/WS/connected-WS,
n=20..400, varied seeds), 0 mismatches. Error contracts (empty ->
NetworkXError, single -> 0, disconnected -> NetworkXError) preserved. Directed
input still returns int. pytest -k "diameter or approxim": 574 passed.
APXDIAM_SHA captured over 80 fixed-seed outputs.

## Timing (warm min-of-8, BA n=500)
| path                | ms    |
|---------------------|------:|
| genuine nx          | 0.29  |
| fnx before (convert)| 3.97  |
| fnx after (native)  | 0.107 |
=> 37x self-speedup; 12.8x slower than nx -> 2.7x FASTER than nx.

## Note
A pre-existing ~2-3% randomized divergence vs genuine nx (BFS-last-node tie-break
when multiple nodes share the max distance) is UNCHANGED by this perf lever
(present in the old converted path too). Tracked as the parity portion of
br-r37-c1-1zcpr.

## Score
Impact: high (12.8x slower -> 2.7x faster, 37x self). Confidence: high (0/150
behavior-preserving, 574 tests). Effort: low. Score >> 2.0.
