# perf: lazy DiAtlasView for DiGraph G[u] — O(degree) -> O(1) (br-r37-c1-ozcko)

## Lever
Directed extension of ed76f46fd (simple-Graph AtlasView). PyDiGraph.__getitem__
(G[u]) and DiAdjacencyView.__getitem__ (G.succ[u] / G.pred[u]) eagerly
materialised the whole {neighbour: edge_attr_dict} PyDict per call = O(degree);
nx's G[u] is a lazy AtlasView = O(1). So G[u][v] / v in G[u] were O(out-degree)
vs O(1), and a snapshot (not live).

Added `DiAtlasView` pyclass (digraph.rs) over successors/predecessors (AdjKind),
holding Py<PyDiGraph>: O(1) __getitem__ (has_edge in the correct direction +
shared edge-dict, KeyError on non-neighbour), O(1) __contains__/__len__
(out_degree/in_degree), __iter__/keys/items/values, get, copy, __eq__/__ne__,
__str__/__repr__/__bool__. G[u] (Successors), G.succ[u] (Successors),
G.pred[u] (Predecessors) all return it, live, with the SAME shared edge dict
(G[u][v]['w']=x mutates live attrs).

## Correctness (parity)
parity_proof.py: 0 mismatches vs networkx across len/iter/dict/keys/copy/==/bool/
`in`/single-edge value/succ+pred directions/asymmetry/mutation-persistence/
LIVE-view/self-loop/KeyError(missing node)/G.adj[u]==G[u]. Full suite: see log.

## Perf — O(degree) -> O(1), self-speedup grows with out-degree (warm min-of-8)
sum(G[u][v]['weight']) over 6000 edges, n=500 (directed):
| out-degree | NEW O(1) | OLD-equiv (materialise) | self-speedup |
|-----------:|---------:|------------------------:|-------------:|
|        ~16 |  11.94ms |                 84.69ms |        7.1x  |
|        ~32 |  12.06ms |                147.08ms |       12.2x  |
|        ~70 |  12.01ms |                291.20ms |       24.2x  |
NEW ~constant in degree; OLD grows linearly. (vs nx still ~7-8x: residual is the
String-canonicalisation tax — node_key_to_string per lookup — separate lever.)

Multi* G[u] still materialise (nested {nbr:{key:attr}}) — follow-up.
