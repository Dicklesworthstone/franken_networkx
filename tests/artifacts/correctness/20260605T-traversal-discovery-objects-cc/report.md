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
