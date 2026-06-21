# FOLLOW-UP RECIPE (proven) — to_directed/to_undirected drop edge attrs on int-batch; fix = materialize-first

- Agent: `BlackThrush` · 2026-06-21 · recipe VERIFIED, integration deferred (low-risk scoping)

## Status
The BROAD variant of this bug — the fnx->nx DELEGATION conversion dropping edge attrs on int
add_edges_from graphs (corrupting multi_source_dijkstra + every delegated weighted algo) — is
FIXED (c42cc7e28 / fa905a41d, backend.py _fnx_to_nx). The NICHE variant remains: the native
methods `Graph.to_directed()` and `DiGraph.to_undirected()` still drop edge attrs on a first-op
int-batch graph (they walk edges_ordered / the lazy mirror, both of which miss on int-batch).

## Proven fix recipe
Materialising the edge mirror first makes the native conversion correct:
    G = fnx.Graph(); G.add_edges_from(int_edges_with_weights)
    list(G.edges(data=True))          # materialise mirror via the display-key path
    D = G.to_directed()               # -> 220/220 weighted (VERIFIED this turn; 0/220 without)
The fnx wrappers already exist and are Python-assignable:
  Graph.to_directed   = _graph_to_directed_with_view(_GRAPH_TO_DIRECTED)        (~40529)
  DiGraph.to_undirected = _directed_to_undirected_with_view(_DIGRAPH_TO_UNDIRECTED) (~40412/40534)
Integration: add a gated materialise (`if number_of_edges() and graph_has_any_attrs(self): for _
in self.edges(data=True): pass`) at the top of each wrapper, OR a self-correcting POST-check
(run native, redo only if the result came back all-empty-attr — `not any(d for _,_,d in
R.edges(data=True))`, O(1) early-exit for normal graphs => zero regression). The post-check is
preferred (the wrappers are optimised; pre-emptive materialise would regress non-lazy attr'd
conversions). Deferred from this turn ONLY because the four wrappers have multiple return points
(as_view, native deepcopy, multi/simple branches) and the broad fix already closed the
high-impact surface; integrating carefully > risking the wrappers at session end.

## Root (the real cure)
Both this and the delegation bug stem from int add_edges_from leaving self.edges reachable via
the DISPLAY-key path (get_edge_data/dijkstra/edges(data=True)) but NOT the CANONICAL/index path
(edges_ordered, inner.edge_attrs by neighbors_iter keys). Curing the construction key
consistency (qq6hi sibling) removes the need for any materialise workaround. See
20260621T-to-directed-lazykey-diagnosis-cc + reference_lazy_key_canonical_divergence.

## IMPLEMENTED (not deferred after all)
Shipped `_materialize_attrs_before_convert` wrapping Graph/DiGraph .to_directed/.to_undirected
(__init__.py ~40543). Self-correcting post-check: run the native conversion, and ONLY if it
returned with NO edge attrs while `graph_has_any_attrs(self)` is True, materialise the mirror
(`for _ in self.edges(data=True): pass`) and redo. `functools.wraps(method)` + an explicit
`__signature__` copy keep the nx-matching signature (the signature-parity tests read it).
VERIFIED: to_directed + to_undirected int-batch 30/30 match nx (was 0/30); signatures identical;
conformance to_directed/to_undirected/convert/reverse/copy 5708 passed 0 failed.
Cost profile: edge-attr'd materialised graph -> O(1) early-exit probe (no regression); attr-less
-> gate skips (no regression); int-batch lazy -> one redo (the fix). KNOWN narrow regression:
a NODE-attr-only graph (node attrs, no edge attrs) pays one wasted redo (~2x) because
graph_has_any_attrs can't distinguish node-only from edge-dropped; chose correctness-everywhere
over a first-edge probe that would miss heterogeneous edge attrs. Multigraphs skip (None gate).
