# MultiGraph bare edges() native fast path, 2973x (br-r37-c1-mgedges)

## Root cause
`MG.edges()` (no args) returns `_LiveMultiEdgeCallView`, whose `__iter__` routed
the DIRECTED (MultiDiGraph) case to the native edge view (br-r37-c1-tmuly) but
left the undirected MultiGraph case on `_walk()` — a pure-Python triple-loop over
`graph.adj[source].items()` (the MultiAdjacencyView lambda chain). ~7000x slower
than nx.

## Lever
`_LiveMultiEdgeCallView.__iter__` now materializes the (u, v) 2-tuples from the
native `_native_edge_view_list(False, False, None)` (added in c0309bdd9) for the
undirected case — one tuple per parallel edge, node-major canonical-dedup order
identical to `_walk()`. Still wrapped in `_FailFastEdgeIterator` (live-view
size-change guard preserved).

## Isomorphism
`_native_edge_view_list(False, ...)` yields (u, v) per (node, neighbor, key) with
canonical-edge_key dedup — the same logic as `_walk()`'s `frozenset((source,
target)), key` marker, so each parallel edge appears once per key and reverse
orientations collapse. Golden 0-mismatch vs nx over MultiGraph x 4 seeds x
self-loops on/off (value + length + containment):

    mismatches=0
    BARE_GOLDEN 427d68ac21e53b2be9f93d54e6462a89e05244618ac1761a44e049184449d782

2025 multigraph/edges/multiedge pytest pass (the 1 failure,
test_to_edgelist_view_type, is pre-existing on HEAD — fails with this change
stashed).

## Benchmark (MultiGraph on a 900-edge graph over 300 nodes, median)

    MG.edges() bare  before: 3386.140 ms   after: 1.139 ms   -> 2973x

Pure-Python (the native builder already shipped in c0309bdd9). Completes the
MultiGraph edges family (data/keys path c0309bdd9 + bare-iter here). Bead filing
deferred (.beads reserved by JadeWolf).
