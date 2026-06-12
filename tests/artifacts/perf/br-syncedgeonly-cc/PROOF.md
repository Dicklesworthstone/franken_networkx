# Edge-weight-only pathfinding: edge_only sync (drop dead O(N) node-attr rebuild)

## Finding (cProfile, astar_path single-pair, n=400, 2000 calls)
`astar_path` spent 38% of its time in `_fnx_sync_attrs_to_inner` (0.088s of
0.231s). That native sync ALWAYS rebuilds every node's AttrMap from the Python
overlay (no node-dirty guard) before the edges_dirty-guarded edge sync. But A*
— and shortest_path / minimum_spanning_tree / maximum_spanning_tree — read only
EDGE weights, never node attributes, so the O(N) node rebuild is pure waste.

## Lever (one, pure-Python — method already exists)
Switch `_sync_rust_edge_attrs(G)` -> `_sync_rust_edge_attrs(G, edge_only=True)`
in the 5 edge-weight-only wrappers. `edge_only=True` routes to
`_fnx_sync_edge_attrs_to_inner`, which is `edges_dirty`-guarded (no-op on an
unmutated graph) and skips the node loop entirely. Established precedent:
`to_scipy_sparse_array` already uses this exact method for the same reason
(see lib.rs:7344 doc-comment).

## Behavior parity / golden sha256 (MY EDITS == HEAD)
04bbb6d6afce5ca490698fd3310d28914df9ca88206b13a66629e19db459b342
(astar_path/astar_path_length/shortest_path paths + min/max spanning_tree edge
sets over 20 weighted watts_strogatz graphs, HALF with post-creation weight
mutations — the exact case the sync exists for.)
Parity vs upstream nx: 120 checks (incl. post-creation `G[u][v]['weight']=`
mutation), 0 mismatches. 1613 pathfinding/MST/dijkstra/bellman/floyd tests pass.

## Speed
astar_path single-pair n=400: 113us -> 94us (~1.2x); the native astar kernel
(~66us) is the floor (~nx parity). Win scales with N/ (cheap query on a large
node set) and is negligible when the algorithm itself dominates. Modest, broad,
byte-exact removal of dead dispatch-path work across 5 weighted functions —
NOT a Score>=2.0 headline; the deep construction-substrate lever is filed
separately as br-r37-c1-sw571.
