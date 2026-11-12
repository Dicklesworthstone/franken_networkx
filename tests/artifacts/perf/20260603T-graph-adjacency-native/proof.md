# Graph/DiGraph adjacency() native fast path (br-r37-c1-gadj)

## Root cause
`Graph.adjacency()` / `DiGraph.adjacency()` route to `_simple_graph_adjacency`,
which yielded `(node, dict(self.adj[node]))` — materialising each node's
AtlasView via the per-element lambda chain. ~153x (undirected) / ~135x
(directed) slower than networkx.

## Lever
Added `PyGraph::_native_adjacency_dict` / `PyDiGraph::_native_adjacency_dict`
(non-shadowed native methods) building the nested `{node: {nbr: attrs}}`
snapshot from inner adjacency, reusing the live `edge_py_attrs` Py<PyDict>
references. `_simple_graph_adjacency` routes to it (after the
`_FilteredGraphView` branch, which has no `_native_adjacency_dict` so the gate
is exact-graph only). Mirror of the shipped Multi adjacency() fast path
(br-r37-c1-bq1n7).

## Isomorphism
Same `{node: {nbr: attrs}}` snapshot, same node x neighbour adjacency order,
reusing the SAME edge attr dict objects: verified `dict(G.adjacency())[u][v] is
G[u][v]` and that mutating the snapshot's inner dict is visible on the graph
(shared-datadict semantics). Golden 0-mismatch vs networkx over Graph +
DiGraph x 4 seeds x self-loops on/off x mixed edge attrs, plus subgraph-view
adjacency (FilterAtlas path unchanged):

    mismatches=0
    ADJ_GOLDEN 218e99a12439bd3a7f091017962274d17b51530e6750f969fe332da9dffdc90b

754 adjacency/subgraph/readwrite pytest cases and `clippy -D warnings` pass.

## Benchmark (adjacency() on a 900-edge graph over 300 nodes, median)

    Graph    before: 7.607 ms   after: 0.322 ms   -> 23.6x
    DiGraph  before: 4.766 ms   after: 0.190 ms   -> 25.1x

(vs networkx 0.041ms: from ~153x-slower to ~8x-slower; residual is the per-edge
dict construction.) Opportunity Score = Impact 5 x Confidence 5 / Effort 2 =
12.5. generate_edgelist and other adjacency() consumers inherit the win.
