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
