# perf: lazy AtlasView for G[u] — O(degree) -> O(1) (br-r37-c1-njs5g)

## Lever
PyGraph.__getitem__ (G[u]) and AdjacencyView.__getitem__ (G.adj[u]) EAGERLY
materialised the whole `{neighbour: edge_attr_dict}` PyDict per call = O(degree),
where nx's `G[u]` is a lazy `AtlasView` (Mapping) = O(1). So `G[u][v]` and
`v in G[u]` — common in Python-side algorithms and user code — were O(degree)
in fnx vs O(1) in nx. It was also a PARITY bug: the materialised dict was a
SNAPSHOT (did not reflect a later `G.add_edge(u, x)`); nx's AtlasView is LIVE.

Added a faithful `AtlasView` pyclass (views.rs) mirroring
networkx.classes.coreviews.AtlasView (read-only Mapping): __getitem__ (O(1) via
has_edge + shared edge-dict, KeyError on non-neighbour), __contains__/__len__
(O(1)), __iter__/keys/items/values, get, copy ({n: self[n].copy()}), __eq__/__ne__,
__str__/__repr__/__bool__. G[u] and G.adj[u] now return it. The returned per-edge
dict is the SAME shared Py<PyDict>, so `G[u][v]['w']=x` still mutates live edge
attrs (mark_edges_dirty deferred to actual edge access, not paid on bare G[u]).

## Correctness (byte-exact + parity)
parity_proof.py: 0 mismatches vs networkx across len/iter/dict()/keys/copy/
==dict/bool/`in`/get/single-edge value/items/mutation-persistence/LIVE-view
(reflects add_edge after taking G[u])/KeyError(non-neighbour)/KeyError(missing
node)/`G.adj[u]==G[u]`. Full Python suite: see suite log.

## Perf — O(degree) -> O(1), self-speedup GROWS with degree (warm min-of-8)
sum(G[u][v]['weight']) over 6000 edges, n=500:
| avg degree | NEW (O(1) view) | OLD-equiv (materialise/access) | self-speedup |
|-----------:|----------------:|-------------------------------:|-------------:|
|        ~24 |        10.69ms  |                      111.49ms  |       10.4x  |
|        ~48 |        11.84ms  |                      197.25ms  |       16.7x  |
|       ~100 |        11.28ms  |                      377.24ms  |       33.4x  |
NEW is ~constant in degree; OLD grows linearly — the O(degree)->O(1) signature.
(vs nx still ~7-8x: the residual is the String-canonicalisation tax of the
String-keyed substrate — node_key_to_string per lookup — a separate architectural
lever, not this one. Materialisation patterns dict(G[u])/items() are unchanged.)

DiGraph/Multi* G[u] still materialise (follow-up).
