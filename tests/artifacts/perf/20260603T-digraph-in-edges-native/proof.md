# DiGraph in_edges() native fast path (br-r37-c1-inedges)

## Root cause
`DiGraph.in_edges()` / `in_edges(data=True)` / `in_edges(data=<key>)`
(`_digraph_in_edges`) walked `self.pred[target].items()` per target — the
DiAdjacencyView lambda chain — building the in-edge list in pure Python.
~176x (no-data) / ~50x (data=True) / ~34x (data=<key>) slower than nx.

## Lever
Added three PyDiGraph native methods iterating node-major over predecessors
(`for target in nodes_ordered(): for source in predecessors(target)`), matching
nx's in_edges order (verified):
- `_native_in_edges_no_data` -> (source, target)
- `_native_in_edges_with_data` -> (source, target, attrs) reusing the live edge
  dict; marks edges dirty (weight-mutation re-sync, cf edges(data=True)).
- `_native_in_edges_data_key(key, default)` -> (source, target, attrs.get(key,
  default)), a read-only value.
`_digraph_in_edges` routes the `nbunch is None` path to them, GATED on
`type(self) is DiGraph` exact — conversion views (`_DirectedGraphConversionView`,
a DiGraph subclass whose inner is empty and whose edges are computed from a
wrapped undirected graph) and SubgraphViews inherit this method but must keep the
Python pred-walk (their inner is not the source of truth).

## Isomorphism
Same node x predecessor order as nx (verified); data=True dict identity-shared
with `G[s][t]` (verified `d is G[s][t]` + mutation visible + dirty re-sync).
Golden 0-mismatch vs nx over DiGraph x 4 seeds x self-loops x {no-data, data=True,
data='w' (default None/0), missing-key default 7} + nbunch path; the to_directed
view + subgraph paths keep exact parity (gate):

    mismatches=0
    INEDGES_GOLDEN 8c0de9d1ff5b1a7940f91066a7fb4c277bff9b4dafa874792403730db8176d06

2271 in_edges/edges/digraph/to_directed-view/edge-attr-sync pytest cases and
`clippy -D warnings` pass.

## Benchmark (DiGraph on a 900-edge graph over 300 nodes, median)

    in_edges()           before: 9.057 ms   after: 0.231 ms   -> 39.2x
    in_edges(data=True)  before: 4.456 ms   after: 0.226 ms   -> 19.7x
    in_edges(data='w')   before: 4.509 ms   after: 0.245 ms   -> 18.4x

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5. Completes the
DiGraph edges-view family (out-edges pu8hk/1tmzs + in-edges here).
Bead filing deferred (.beads reserved by JadeWolf).
