# edges(nbunch, data) — route adj walk to to_dict_of_dicts rows

## Lever
EdgeDataView._materialize_via_adj_walk (the G.edges(nbunch, data=...) path) did
per-node graph[node].items() AtlasView access + per-edge dict(edge_data) copy —
~13x slower than nx. When the nbunch is large enough to amortize (>= 1/4 of
node_count), snapshot the whole adjacency ONCE via the native to_dict_of_dicts
kernel ({node: {nbr: live_edge_dict}}, rows iterate as a plain dict — no AtlasView
per-edge cost) and read its rows; small nbunch keeps the per-node AtlasView walk
(now yielding the live edge_data directly, no dict() copy). Undirected EdgeDataView
only (directed/multigraph use other classes).

## Correctness
edges(nbunch, data) vs nx across 250 cases (attr/attr-less x nbunch {range,small
list,sample,all,single} x data {True,False,'w','missing',None}, incl. self-loops):
0 mismatches. golden sha 5dcd6a756e28e8a7. 1268 edges/edge-view tests pass. BONUS
parity fix: data=True now yields the SAME LIVE edge dict object nx does (the old
path returned a copy) — verified mutation propagates to the graph.

## Benchmark (warm min, interleaved before/after)
| scenario                      | BEFORE    | AFTER    | self-speedup |
|-------------------------------|-----------|----------|--------------|
| attrless edges(150,data=True) | 3.492ms   | 0.477ms  | 7.3x         |
| attr edges(150,data='weight') | 3.510ms   | 0.525ms  | 6.7x         |
| small nb=[0,1,2] data=True    | 0.0943ms  | 0.0855ms | no regression|

Gap to nx narrows ~13x slower -> ~1.8x. RESIDUAL: to_dict_of_dicts builds the
WHOLE graph dict (overbuild for partial nbunch); faster-than-nx needs a native
edges(nbunch, data) kernel walking only nbunch's rows with live-dict attach.
