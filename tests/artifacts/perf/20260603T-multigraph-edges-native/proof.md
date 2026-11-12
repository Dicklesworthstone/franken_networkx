# MultiGraph edges() native fast path, ~3400-4200x (br-r37-c1-mgedges)

## Root cause
`MultiGraph.edges(keys=...)` / `edges(data=...)` (`_MultiGraphEdgeView.__call__`)
triple-looped `self._graph.adj[source].items()` then `keyed_attrs.items()` per
source — the MultiAdjacencyView lambda chain — building the edge list in pure
Python. ~10000x slower than nx (the MultiDiGraph edges path was fixed earlier,
br-r37-c1-tmuly; the undirected MultiGraph path was not).

## Lever
Added `PyMultiGraph::_native_edge_view_list(data, keys, default)` building the
all-edges list natively in nx's EXACT node-major order: `nodes_ordered()`
(source) x `neighbors` (target) x `edge_keys` (key), deduping each undirected
edge by its canonical `edge_key` (so each parallel edge is emitted once, from its
first-iterated endpoint — matching nx's `seen=frozenset({u,v}),key` marker).
Tuple shape mirrors the Python branches: `(u, v[, key][, attr])`, where attr is
the live dict (data=True), `attrs.get(key, default)` (data=<key>), or absent
(data=False). `_MultiGraphEdgeView.__call__` routes its `nbunch is None` path to
it and wraps the result in the same canonical view type
(`_MultiEdgeDataView`/`_MultiEdgeView`) for `type(...).__name__` + set-algebra
parity. data=True marks edges dirty (live dict re-sync).

## Isomorphism
Same node-major order + canonical dedup as nx (verified vs insertion order, which
differs); data=True dict identity-shared with `G[u][v][k]`. Golden 0-mismatch vs
nx over MultiGraph x 4 seeds x self-loops x {edges, keys, data, data+keys,
data='w' (default None/7), missing-key} + identity + type-name + nbunch:

    mismatches=0
    MGEDGES_GOLDEN 111f508ead4252219d5e9165736fcf62b61a7c9ed677217e9bab92cb049674b2

1959 multigraph/edges/multiedge pytest cases and `clippy -D warnings` pass.

## Benchmark (MultiGraph on a 900-edge graph over 300 nodes, median)

    edges(keys=True)  before: 4855.946 ms   after: 1.441 ms   -> 3370x
    edges(data=True)  before: 4848.730 ms   after: 1.147 ms   -> 4227x
    edges(data='w')   before: 4897.138 ms   after: 1.163 ms   -> 4211x

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5. Bead filing
deferred (.beads reserved by JadeWolf).
