# DiGraph edges(data=True) native fast path (br-r37-c1-deg-data)

## Root cause
`DiGraph.edges(data=True)` (and `out_edges(data=True)`, same `_DiGraphEdgeView`)
walked `self._graph.succ[source].items()` per source — the DiAdjacencyView
lambda chain — materialising `(u, v, attrs)` in pure Python. ~58x slower than nx.
(The no-data path already had a native fast path, br-r37-c1-acuub; data=True did
not.)

## Lever
Added `PyDiGraph::_native_edges_with_data` building the `(u, v, attrs)` list from
`inner.edges_ordered_borrowed()` (same node x successor order as the verified
no-data fast path), reusing the live `edge_py_attrs` dict per edge. The Python
`_DiGraphEdgeView.__call__` routes its `nbunch is None and data is True` path to
it. data=False / data=str / nbunch paths unchanged.

## Isomorphism
Same edge order as nx (verified: no-data order already matches nx, with-data uses
the same traversal), and the yielded data dict is identity-shared with `G[u][v]`
(verified `d is G[u][v]` + mutation visible). Because the live dict is handed
back, the method marks edges dirty so a `d['weight']=x` mutation re-syncs to the
weighted kernel (the succ-AtlasView path did this implicitly; fixes
test_edge_attr_dirty_sync). Golden 0-mismatch vs nx over DiGraph x 4 seeds x
self-loops x edge attrs, incl. out_edges/no-data/data='w'/nbunch:

    mismatches=0
    DEDGES_GOLDEN f2427ca9908ff09735325ecf35ed2b9b21b1eb113cb978903d29f5b0c830654b

2278 edges/digraph/edge-attr-sync pytest cases and `clippy -D warnings` pass.

## Benchmark (DiGraph on a 900-edge graph over 300 nodes, median)

    edges(data=True)      before: 5.054 ms   after: 0.930 ms   -> 5.4x
    out_edges(data=True)  before: 5.099 ms   after: 0.870 ms   -> 5.9x

Opportunity Score = Impact 4 x Confidence 5 / Effort 2 = 10.
