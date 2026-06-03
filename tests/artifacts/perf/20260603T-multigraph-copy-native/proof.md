# MultiGraph/MultiDiGraph copy() native fast path (br-r37-c1-8uh84)

## Root cause
`MultiGraph.copy()` / `MultiDiGraph.copy()` route to
`_copy_preserving_insertion_order`, whose multigraph branch rebuilds the clone
via `result.add_edges_from((u, v, key, dict(attrs)) for u, v, key, attrs in
self.edges(keys=True, data=True))`. Walking `self.edges(keys=True, data=True)`
materializes the MultiAdjacencyView lambda chain (`__init__.py:1222/1156`
`_atlas` lambdas) per edge and feeds it into `add_edges_from` — ~1123x
(undirected) / ~95x (directed) slower than networkx (cProfile: 16.3s of 17.6s in
the AtlasView `<lambda>` at `__init__.py:1222`).

The native `copy()` was bypassed for a documented reason — it iterates the
`node_key_map` *HashMap*, which scrambles node insertion order (verified:
`[4, 0, 30, 31, 8, ...]` instead of `[0, 1, 2, 3, ...]`).

## Lever
Added `PyMultiGraph::_native_copy` / `PyMultiDiGraph::_native_copy`: an
insertion-order-preserving native clone that iterates `nodes_ordered()` for node
order and `edges_ordered()` for edge order + public endpoint orientation,
shallow-copying the live node/edge/graph attr dicts (`dict.copy()` — new dict,
shared values). `_copy_preserving_insertion_order` routes to it for exact
`MultiGraph` / `MultiDiGraph` (gated on `type(self) in (...)` so subclasses and
filtered subgraph views keep the generic rebuild).

## Isomorphism
The native clone reproduces nx's shallow-copy contract (br-r37-c1-3tlkj): edge
attr value containers are SHARED (`c[u][v][k]['data'] is g[u][v][k]['data']`)
while the attr dict itself is new and structural mutations are independent
(`c.add_edge(999,998)` does not touch the original). Golden over
MultiGraph + MultiDiGraph x 3 seeds x self-loops on/off, int/float/list/missing
weights, out-of-order nodes + node attrs + nested graph attrs — comparing node
order+attrs, edge order+keys+attrs+orientation, graph attrs, type, n/m vs
networkx:

    mismatches=0
    COPY_GOLDEN 07f1600cd32a87ee276e7b27fd45b5e0f8882606f1da91305912cc52af8ede6b

1861 copy/multigraph/pickle pytest cases and `clippy -D warnings` pass.

## Benchmark (copy() on a 900-edge graph over 300 nodes, median)

    MultiGraph    before: 6241.585 ms   after: 5.557 ms   -> 1123x
    MultiDiGraph  before:  502.649 ms   after: 5.279 ms   ->   95x

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.

## Out of scope (filed separately)
- `subgraph().copy()` still uses the generic path (filtered view is not the exact
  type). It mismatches nx for MultiDiGraph because the subgraph *filtered view*
  node order diverges from nx — a pre-existing bug confirmed identical with and
  without this change. Filed br-r37-c1-brsv7.
- The ~2x residual vs nx (5.5ms vs ~2.7ms) is the `py_dict_to_attr_map` per-edge
  round-trip into the inner Rust graph (the documented clone tax).
