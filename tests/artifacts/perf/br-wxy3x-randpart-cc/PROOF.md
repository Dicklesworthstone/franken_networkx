# approximation.randomized_partitioning: de-delegate (8x slower -> 1.57x faster)

## Gap (br-r37-c1-wxy3x family)
fnx.approximation.randomized_partitioning resolved via _ApproximationNamespace
__getattr__ -> nx's function, which round-tripped the graph through
_networkx_graph_for_parity + ran nx.cut_size over fnx's slow adjacency views.
~8x slower than nx (0.71ms vs 0.09ms ws-120) for an almost-no-work coin-flip.

## Lever (one, pure-Python — no rebuild)
Concrete _ApproximationNamespace.randomized_partitioning method (same pattern as
min_weighted_vertex_cover): draw the cut in-process with nx's EXACT RNG
(create_py_random_state over G.nodes() order) and use the native cut_size.

## Behavior parity
vs upstream nx: 360 checks (ws Graph x seeds {0,1,7,42} x p {0.5,0.3,0.7} +
weighted), 0 mismatches (same per-node seed.random() draws -> same cut;
cut_size order-insensitive). Directed/multigraph raise NetworkXNotImplemented
like nx's @not_implemented_for decorators.

## Speed (ws-120, min-of-N)
8x slower -> 1.57x FASTER than nx (0.71ms -> 0.057ms = 12.7x self-speedup).
