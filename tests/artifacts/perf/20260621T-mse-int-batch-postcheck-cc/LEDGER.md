# FIX — minimum_spanning_edges(data=True) int-batch weight-drop (buffered post-check) + int-batch class status

- Agent: `BlackThrush` · 2026-06-21 · MEASURED · __init__.py only

## Fixed
`minimum_spanning_edges(G, weight=..., data=True)` on a fresh int-node add_edges_from graph
selected the UNWEIGHTED MST and emitted edges with EMPTY data (KeyError on d['weight']). The
kruskal path is already EAGER (list_iterator), so buffer it and apply the to_directed-style
post-check: if the source has attrs yet every emitted edge has empty data, materialise the mirror
(display-key path) and redo. VERIFIED: int-batch mse total fnx 89 == nx 89 (was KeyError/wrong);
perf held at 1.44x (no regression — the kruskal result is already materialised); conformance
spanning/mst/kruskal/prim/boruvka 1419 passed 0 failed.

## int-batch edge-attr-drop CLASS — status after this session
A comprehensive int-batch weighted sweep (40-node weighted graph, fnx.Graph()+add_edges_from)
now passes for: minimum/maximum_spanning_tree, minimum_spanning_edges(data=True),
max/min_weight_matching, dijkstra/johnson/bellman/astar/floyd, max_flow/min_cut,
pagerank/eigenvector/katz/closeness/betweenness/global_reaching, to_numpy/adjacency_matrix,
degree(weight), to_directed/to_undirected, and the fnx->nx delegation conversion. The
shortest-path / flow / centrality families were NEVER affected (they read the inner correctly);
only the lazy-mirror-reading kernels (conversions + kruskal spanning) were, and all are now
post-check-fixed (non-regressing).

## Remaining residual (narrow)
`minimum_spanning_edges(..., data=False)` on int-batch can still select the unweighted edge SET
— with data=False there are no attr dicts to probe for the lazy-drop, and a pre-emptive
materialise would regress the 1.44x win. Needs the real cure: int-batch construction key
consistency (the native `_try_add_attr_edges_from_batch` mis-keys self.edges vs the
canonical/display resolution — qq6hi sibling, reference_lazy_key_canonical_divergence). Until
then data=False mse-direct on a fresh int-batch graph is the lone uncovered case.
