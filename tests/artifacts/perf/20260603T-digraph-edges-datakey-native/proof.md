# DiGraph edges(data=<key>) native fast path (br-r37-c1-deg-datakey)

## Root cause
`DiGraph.edges(data='weight')` / `out_edges(data=<key>)` (shared
`_DiGraphEdgeView`) walked `succ[source].items()` per source — the
DiAdjacencyView lambda chain — yielding `(u, v, attrs.get(key, default))` in
pure Python. ~40x slower than nx. Sibling of the edges(data=True) fast path
(br-r37-c1-pu8hk); the data=<key> path was still slow.

## Lever
Added `PyDiGraph::_native_edges_data_key(key, default)` building
`(u, v, attrs.get(key, default))` from `inner.edges_ordered_borrowed()` (same
node x successor order as the verified no-data/with-data paths), reading each
edge's value via `get_item(key)` on the live `edge_py_attrs` dict, falling back
to `default`. `_DiGraphEdgeView.__call__` routes its `nbunch is None and data
is not False/True` path to it. Yields a VALUE (not the dict) so no dirty-mark is
needed.

## Isomorphism
Same edge order as nx; `attrs.get(key, default)` semantics reproduced exactly
(`is not False`/`is not True` gating keeps the True/False sentinels on their own
paths; int/None keys route here like nx). Golden 0-mismatch vs nx over DiGraph
x 4 seeds x self-loops x {data='w' (default None/0), data='tag', missing-key
(default 7)} x edges/out_edges, with data=True/no-data/nbunch paths unchanged:

    mismatches=0
    DK_GOLDEN 14868fd443b713150eab52eb8b4e0bc1c5591cf44a3644a34fbf655d49298cf7

2278 edges/digraph/edge-attr-sync pytest cases and `clippy -D warnings` pass.

## Benchmark (DiGraph on a 900-edge graph over 300 nodes, median)

    edges(data='w')      before: 6.568 ms   after: 0.872 ms   -> 7.5x
    out_edges(data='w')  before: 5.348 ms   after: 1.033 ms   -> 5.2x

Opportunity Score = Impact 4 x Confidence 5 / Effort 2 = 10.
