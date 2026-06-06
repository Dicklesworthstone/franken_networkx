# br-r37-c1-6hpa9 — traversal DISCOVERY-object parity (batch 1)

## Class
nx traversal results carry DISCOVERY objects: the source as passed,
every discovered node as its PARENT's adjacency-row object (the z6uka
row overrides; pred rows for reverse walks). fnx bindings mapped results
through py_node_key (the node-map object), diverging on mixed
hash-equal keys (28 vs 28.0) — pre-existing across the family.

## Probe (one-liner class detector)
g.add_node(28); g.add_edge(7, 28.0); g.add_edge(28.0, 5); compare reprs
of each traversal fn vs nx. /data/tmp copy: fnx_traversal_probe.py —
11 fns diverged at HEAD (directed) + 10 (undirected).

## Fixed in this batch (GraphRef::discovery_map + disp_or_node_key)
bfs_edges (incl. reverse via pred rows), bfs_tree (reverse too),
bfs_predecessors + bfs_successors (tree stream derived from their own
output), dfs_preorder/postorder_nodes (via dfs_edges_canonical),
ancestors (reverse-BFS stream), descendants (forward stream).
[dfs_edges/dfs_tree were fixed in d7cbf073d.]

## Deliberately deferred (on the bead)
bfs_layers multi-source (kernel lacks a tree stream),
single_source_shortest_path_length + unweighted shortest_path (HOT path
— needs kernel (node, len, parent) output; bolting a second BFS walk
per call would tax every caller), descendants_at_distance.
edge_dfs/edge_bfs/generic_bfs_edges verified already matching.

## Batch 2 (this commit)
Kernels now emit the discovering parent for free:
- fnx-algorithms: single_source_shortest_path_length{_borrowed,
  _directed}_with_parents (old fns delegate, parents dropped);
  bfs_layers{,_directed}_multi_with_parents.
- sssp_length binding: dict keys = source-as-passed / parent's row
  object — and key ORDER stays BFS discovery order.
- bfs_layers binding: single + multi source via the parent-emitting
  kernels; ALSO two more nx behaviors pinned: layer 0 is
  `list(set(sources))` — CPython SET iteration order, reproduced
  exactly by building a real PySet in-process (any hash seed); and
  missing sources raise NetworkXError (binding previously skipped
  silently).
Remaining on the bead: unweighted shortest_path path-reconstruction
family (predecessor maps; same kernel addition serves it) and
descendants_at_distance.

## Batch 3 (this commit)
Unweighted shortest-path dict family:
- compute_single_source_shortest_paths{,_directed} now return the
  kernel's ORDERED Vec — the old `.collect::<HashMap>()` made the
  user-visible dict KEY ORDER nondeterministic (worse than the object
  bug: it varied run to run).
- emit_paths_dict_discovery: discovery objects derived from the paths
  themselves (a node's discovering parent is its path's second-to-last
  element — zero extra walks); applied to shortest_path (source-given +
  all-pairs, both orientations), single_source_shortest_path,
  all_pairs_shortest_path.
Residual (filed as its own bead on close): single-pair
  bidirectional_shortest_path / shortest_path(s, t) objects (nx's
  bidirectional BFS discovers from BOTH frontiers — succ rows forward,
  pred rows backward; needs the meet-point object flow replicated) and
  the target-only branch (reverse-walk discovery + per-node loop).

## Batch 4 (k4wsy) — bidirectional single-pair
TWO bugs, one fix:
- VALUE: fnx's unweighted single-pair kernels were UNIDIRECTIONAL BFS;
  nx routes through bidirectional (smaller-fringe alternation) which
  selects a different equal-length path on tie-breaks (diamond probe:
  directed nx [s,b,t] vs fnx [s,a,t]). Worse, the directed
  bidirectional route DELEGATED to nx over _fnx_to_nx — whose
  succ-major walk REORDERS pred rows, poisoning the reverse-frontier
  tie-break (filed br-r37-c1-w7nn3, blast radius = all pred-order-
  sensitive directed delegations).
- OBJECTS: discovery parity (succ rows forward, pred rows backward,
  endpoints as passed, meet node from the returning frontier).
Fix: bidirectional_shortest_path{,_directed}_meta kernels mirroring
networkx _bidirectional_pred_succ line by line, emitting
(node, display-parent, side); binding maps objects and now handles
directed natively (delegation + conversion tax removed);
compute_single_shortest_path{,_directed} unweighted branches switched
for value parity everywhere.
Golden battery sha 59ffd8b7 (tie diamonds, mixed keys, 30-trial random
tie-rich corpus, no-path/self-target errors): 0 failures.
Residual on bead: the target-only branch (reverse single-target walk:
key order + objects + the O(V) per-node bidirectional loop).

## Batch 5 (k4wsy close-out) — target-only branch
shortest_path(G, target=t) now runs nx's exact single_target walk: ONE
reverse level-BFS (bfs_edges_directed_reverse / bfs_edges stream) via
emit_single_target_paths_dict — key order target-first in discovery
order, reverse-tree tie-breaks (the old O(V) per-node bidirectional
loop could pick different equal-length paths AND was ~O(V·walk)),
pred-row discovery objects. Perf side-effect: directed 3k-node
sp(target) now one walk, 4.6ms vs nx 2.1ms (was V bidirectional
searches). FAMILY PROBE NOW FULLY CLEAN: 0 divergences across all 18
original probe shapes + path family + target-only.

## Batch 6 — WEIGHTED shortest-path dict family (Phase B probe)
13-form matrix (dij+bf, both orientations) found the weighted family
untouched by batches 3-5: discovery objects everywhere, bellman-ford
key order CLOBBERED by the wrapper's 62jy2 distance-re-sort (nx does
NOT sort SPFA output), and the weighted target-only branch was an O(V)
per-pair loop with non-nx tie-breaks. Fixes: emit_paths_dict_discovery
on all weighted source-given/all-pairs branches;
emit_reversed_target_paths_dict + reverse_digraph for target-only (nx
G.reverse(copy=False) semantics, ONE walk); 62jy2 re-sort removed;
single_source_dijkstra binding (feeds the path/length wrappers) and
all_pairs_dijkstra_path now map discovery objects via the FULL kernel
(distances+paths in one dijkstra). Probe: 17 divergences -> 0.

## Batch 7 — bellman-ford standalone single-source trio
single_source_bellman_ford{,_path,_path_length}: discovery objects
(SPFA relaxation parent via paths/preds-carrying kernels — the length
binding switched from the lengths-only kernel to the pred-carrying
one) + int distance coercion for all-int weights (ss_bf, ap_bf_len,
ap_dij_len wrappers). NOTE: _graph_has_nonunit_weight is a
sync-then-False shim — the raw path is the INTENDED route for all
simple weighted graphs; the br-bfignoreweight delegation comments are
stale. Residual beaded: the four all_pairs_* bindings + multi_source
seed set-order.

## Batch 8 (br-r37-c1-7hsew) — all-pairs weighted + multi-source
all_pairs_bellman_ford_path (emit_paths per source),
all_pairs_bellman_ford_path_length (binding loops the PRED-carrying
kernels), all_pairs_dijkstra_path_length + all_pairs_dijkstra
multigraph fallback (FULL kernels: paths feed disp),
all_pairs_dijkstra PACKED fast path (integer predecessors -> row
objects), multi_source_dijkstra (seeds display AS PASSED, iterating
the caller's set in-process = nx seed order at any hash seed;
finalized nodes via predecessor row objects). Probe 10 -> 0; the
ENTIRE weighted-standalone matrix from batch 7 is now clean. Golden
sha 81471ad9 incl. set/list/single seed shapes.
