# VERIFICATION — O(E) edges(data=True) presence-check lever: status after mining

- Agent: `BlackThrush` · 2026-06-21 · MEASURED

## Lever (recap): replace `any/all(X in attrs for ... in G.edges(data=True))` O(E) Python walks
with a native MIRROR-AWARE check. SHIPPED: pagerank (graph_has_edge_attr) 0.74x->6.41x
(57e0e737c); edge_connectivity (7699a80b4). `_graph_has_any_attrs` already routes to the native
graph_has_any_attrs (only the partial-build fallback walks).

## Remaining instances — BLOCKED (native weight-checks are INNER-ONLY = lazy-mirror buggy)
- `is_weighted` (18636): native `_fnx.is_weighted` is 600x faster (537us->0.9us) BUT WRONG —
  returns False for an all-weighted graph whose weights were Python-set post-construction
  (`G[u][v]['weight']=1`, lives in the mirror; native reads inner only). It is DORMANT (no
  callers; the Python path uses to_dict_of_dicts, mirror-correct), so a latent buggy binding, not
  a live bug. Cannot route to it without a mirror-aware native fix.
- `is_negatively_weighted` (18687): native `graph_has_negative_edge_weight` is ALSO inner-only
  (False on a Python-set negative). It IS used correctly elsewhere
  (`_has_negative_edge_weight_for_dijkstra` SYNCS mirror->inner first, so dijkstra's negative-
  weight rejection is correct — verified: fnx + nx both raise ValueError on a Python-set negative).
  Routing the public is_negatively_weighted to it would need the sync (O(E)) -> only marginal vs
  the Python walk, and adds a surprising inner-mutation side-effect to a read-only query.

## Conclusion
The SAFE, high-value presence-check lever is mined out (pagerank was the big one). The residual
instances are gated by the native weight-checks' inner-only lazy-mirror limitation. The clean
follow-up is to make `is_weighted`/`graph_has_negative_edge_weight` MIRROR-AWARE (inner OR mirror,
the pattern already applied to graph_has_edge_attr this session) in the binding — but that file
(fnx-python/algorithms.rs) currently holds a peer's uncommitted WIP, so deferred. No regression,
nothing to ship here; recorded so the next pass starts from the right place.
