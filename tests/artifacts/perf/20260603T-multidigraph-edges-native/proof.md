# MultiDiGraph edges() native fast path (br-r37-c1-tmuly)

## Root cause
Two Python view paths over MultiDiGraph's succ AtlasView walked the
MultiAdjacencyView lambda chain per element (~3000-7000x slower than nx):
- `_MultiDiGraphEdgeView.__call__` (edges(data=...)/keys=...): triple-loop over
  `self._graph.succ[source].items()`.
- `_LiveMultiEdgeCallView._walk` (the bare `G.edges()` early-return): same loop.
For a 1000-edge MultiDiGraph, list(G.edges()) took 976 ms (edges(data=True)
1366 ms). The native MultiDiGraphEdgeView (digraph.rs) already builds tuples from
inner.edges_ordered() in nx order reusing the live edge dicts, but
MultiDiGraph.edges is overridden in Python so the native view was bypassed.

## Lever
Added non-shadowed PyMultiDiGraph::_native_edge_view (existing #[pymethods], no
lib.rs change). Routed both Python paths to materialize from it: `__call__` for
data in {False,True,<str attr>}, and `_LiveMultiEdgeCallView.__iter__` for the
directed bare case. `data=None`/non-str hashable attr names keep the Python loop
(parse_view_data only handles bool/str; attrs.get(data,default) handles any
hashable -- guards the out_edges.data(None, default=7) parity test).

## Isomorphism
Native view yields byte-identical tuples for every (data, keys) variant in nx
node x target x key order, reusing the same edge attr dict objects. Golden over
plain/keys/data/keys+data/data=attr/data=attr+default/nbunch is 0-mismatch vs nx:

    MDE_GOLDEN 09ff19574caa12748b1b338594fd01f4822af735b0f2df7a58271ca5b37fbbca

1540 multidigraph/edges/edgeview pytest cases (incl. data=None edge case)
+ clippy -D warnings pass. Rebased+revalidated on origin AFTER the peer's
edgesdatakey landed (the earlier collision settled).

## Benchmark (1000-edge MultiDiGraph, median)
    list(edges())     : 976.117 ms -> 1.231 ms = 793x
    list(edges(data)) : 1365.599 ms -> 1.120 ms = 1219x
    out_edges/in_edges get the speedup for free (they call self.edges()).

Opportunity Score = Impact 5 x Confidence 5 / Effort 3 = 8.3.
