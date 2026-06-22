# MDG out_edges/edges(nbunch, keys=True) — win READY but blocked by a latent wrap bug (cc)

## The win (measured, reverted pending unblock)
MDG out_edges(nbunch, keys=True) is 0.81x: the native kernel
(_native_mdg_out_edges_nbunch_no_data) GATES OUT for keys=True via
`keys && !edge_py_keys.is_empty()` — and MultiDiGraph(gnm) carries an edge_py_keys mirror, so
keys=True ALWAYS falls to the slow self.edges path. Fix: drop the edge_py_keys gate and emit the
DISPLAY key via py_edge_key(canonical, nbr, key) (falls back to the int key when no mirror) —
exactly the br-r37-c1-mdgdju recipe. MEASURED with that fix: out_edges(nb,keys=True)
**0.81x -> 1.39x (dominates)**, byte-exact incl explicit string keys (n=1500/k=750, warm).

## Why it's reverted (blocked, not ~0-gain)
Un-gating keys=True EXPOSES a LATENT BUG in my earlier route (commit bfd4e3e3e,
_MultiDiGraphEdgeView.__call__, python/franken_networkx/__init__.py ~line 2503): the keys=True
branch wraps via `_wrap_edge_data_view(nres, _OutMultiEdgeView)`, but _OutMultiEdgeView is a
_DiEdgeMethodView (needs (graph, method)), NOT a list-wrapper — so `_OutMultiEdgeView(list)` raises
TypeError. It was harmless while keys=True gated (never reached); the kernel fix triggers it
(test_multidigraph_edges_keys_view_matches_networkx, edges(nbunch=["a"],keys=True)).

The correct class is `_OutMultiEdgesKeysView` (a _MultiEdgeView subclass, list-wrapper) — exactly
what the slow path's keys=True branch uses (__init__.py ~line 2545). out_edges(nbunch) is fine
(returns the kernel list directly, no wrap) — only the EDGES route has the buggy wrap.

## Status: blocked on __init__.py (BlackThrush exclusive reservation)
Both the kernel fix (digraph.rs, mine — reverted to keep conformance GREEN) and the one-line wrap
fix (__init__.py line ~2503: _OutMultiEdgeView -> _OutMultiEdgesKeysView) must land together.
__init__.py is held by BlackThrush. When it frees: (1) wrap fix, (2) re-apply the kernel
edge_py_keys-gate drop + py_edge_key, (3) rebuild, (4) verify out_edges+edges(nb,keys=True)
dominate + the keys-view conformance test passes, (5) commit. NOTE: the latent _OutMultiEdgeView
wrap bug should be fixed regardless (it is a crash waiting for anyone who un-gates keys=True).
