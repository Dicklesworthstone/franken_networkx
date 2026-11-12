# P0 CORRECTNESS FIX — fnx->nx conversion silently DROPPED edge attrs on int-batch graphs (every delegated weighted algo ran UNWEIGHTED)

- Agent: `BlackThrush` · 2026-06-21 · MEASURED · backend.py only

## The bug (BROAD, found via multi_source_dijkstra)
`G = fnx.Graph(); G.add_edges_from(int_edges_with_weights)` then ANY nx-DELEGATED weighted
function returned WRONG results as first-op: multi_source_dijkstra gave ~UNWEIGHTED distances
(58/60 distances too small). Root: `_fnx_to_nx` (the delegation conversion) builds edges via
`_native_fnx_to_nx_adjacency`, which reads ONLY the lazy `edge_py_attrs` MIRROR. A freshly
batch-built INT-node graph leaves that mirror UNMATERIALIZED (the inner Rust AttrMaps hold the
weights) -> conversion emits 0/120 weighted edges -> nx runs unweighted. Isolated:
add_edges_from (int) BROKEN; constructor `fnx.Graph(edges)` / string nodes / per-edge add_edge /
any prior materializing read = CORRECT. dijkstra_path_length (native, not delegated) was always
correct — only the DELEGATION path corrupts.

## Fix (backend.py _fnx_to_nx)
Before the bulk `_native_fnx_to_nx_adjacency` read, force the edge mirror to materialise from
the inner (`for _ in fg.edges(data=True): pass` — the display-key path get_edge_data/dijkstra
already use correctly). Gated on `type in (Graph,DiGraph)` + `number_of_edges()` +
`graph_has_any_attrs` (inner-aware) so attr-less conversions (check_planarity, BFS/DFS) stay on
the untouched fast path.

## Verified
multi_source_dijkstra int-batch 20/20 match nx (was 0/20). Conformance: dijkstra/shortest_path/
multi_source/weighted/steiner/astar/bellman 3643 passed 0 failed; voronoi/convert/compose/union/
to_*/relabel/product 2713 passed 0 failed.

## Regression (small, bounded, non-competitive)
The materialize pass costs ~0.445ms for 1500 edges (~13% of the 3.324ms conversion), paid only
by ATTR'd simple-graph DELEGATED conversions. These are non-competitive paths (delegated because
fnx can't beat nx); no shipped fnx WIN delegates via _fnx_to_nx (wins are native). Correctness of
a P0 wrong-result bug >> 0.445ms on a delegated path. FOLLOW-UP to eliminate it entirely: make
the native `fnx_to_nx_adjacency` read the inner AttrMap when the mirror misses (no Python
materialize) — pending a rebuild + verifying inner.edge_attrs resolves with neighbors_iter keys.

## Still open (separate, niche): to_directed/to_undirected (native methods, NOT this conversion)
remain 0/220 on int-batch — they walk edges_ordered directly; tracked in
20260621T-to-directed-lazykey-diagnosis-cc.

## UPDATE — regression ELIMINATED (tighter post-bulk gate)
Replaced the pre-bulk unconditional materialize with a POST-bulk detector: do the bulk read,
then materialize+re-read ONLY when `graph_has_any_attrs` is True yet the bulk came back with NO
edge attrs (`not any(attrs ...)`, which EARLY-EXITS on the first non-empty attr). A normal
already-materialised graph now pays an O(1) probe, not an O(E) pass: _fnx_to_nx of a materialised
1500-edge weighted graph 3.32+0.45 -> 2.69ms (no redundant work). Correctness unchanged
(multi_source int-batch 20/20); conformance 4907 passed 0 failed. NO net regression now.
