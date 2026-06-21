# NEGATIVE EVIDENCE — to_directed()/to_undirected() drop edge attrs on a batch-built graph when called FIRST (deep storage inconsistency)

- Agent: `BlackThrush` · 2026-06-21 · (no code change — 2 attempted fixes reverted)

## The bug (real, pre-existing, narrow trigger)
On a graph built `G.add_nodes_from(nodes); G.add_edges_from(edges, data=True)` with EDGE attrs,
calling `G.to_directed()` (Graph->DiGraph) or `D.to_undirected()` (DiGraph->Graph) as the FIRST
op silently DROPS the edge attributes (result edges have no 'weight'). Any prior materializing
read (`list(G.edges(data=True))`, `dict(G.degree(weight=))`) fixes it. copy/reverse/compose/
union/cartesian_product/convert_node_labels are all FINE — only these two conversions drop.

## Why my fixes did NOT work (the deep part)
The batch weights are reachable via `G.edges(data=True)` and `get_edge_data` (first read), so
SOMETHING holds them — but as first-op, ALL of these returned EMPTY for the same edges:
  - `edges_ordered().attrs` (the walk's pair_attrs, keyed via adj_indices) — Graph.to_directed
  - `inner.edge_attrs(left,right)` (node-map index lookup) — my to_directed fix
  - `edge_py_attrs` mirror AND `snapshot.attrs` inner — my to_undirected fix
i.e. the index space the conversion walks (adj_indices) and the attr maps (self.edges /
edge_py_attrs) are out of sync until a materializing read rebuilds them. Tried (all reverted):
(1) edges_ordered: build pair_attrs from `self.edges.iter()` directly — still empty;
(2) to_directed: `inner.edge_attrs(u,v)` — still empty;
(3) to_undirected: mirror-or-`snapshot.attrs` fallback — still empty.

## Conclusion / follow-up
Root is in the BATCH CONSTRUCTION path (extend_edges_*_unrecorded): it populates adj_indices
and the lazy mirror such that the inner `edges`/`edge_index_endpoints`/adj_indices are
mutually consistent ONLY after a materializing read. The clean fix is to make batch
construction populate `self.edges` (the authoritative attr IndexMap) in lock-step, OR have the
conversions force-materialize first. Needs a focused dive into the unrecorded-extend kernels
(shared fnx-classes territory). Documented so the next session starts from the right place,
not the wrong (graph_has_* / edges_ordered) layer. Build note: rch toolchain re-staled the
cargo cache repeatedly this turn; full `cargo clean` each time.
