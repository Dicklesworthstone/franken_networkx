# collaboration_weighted_projected_graph directed — batch shipped, BENCH RESULT (br-r37-c1-collabbatch)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py` (commit 42463a8ce)

Shipped a construction-tax batch (per-edge add_edge -> add_edges_from) for the
directed fallback. DEFERRED bench (run after disk recovered, pinned taskset -c 2,
directed bipartite 150x150 / 2400 edges):

- collaboration_weighted_projected_graph(directed): **0.7x** — the batch is BYTE-EXACT
  but ~0-gain. cProfile/analysis: the bottleneck is NOT the construction but the
  O(edges) weight loop's repeated per-access `B[u]` / `B[nbr]` / `pred[v]` /
  `len(B[n])` AtlasView crossings.

PARITY-LOCKED — snapshot rejected: I tried snapshotting succ/pred adjacency to Python
sets once (the usual lever); it measured **1.11x** but BROKE byte-exact parity
(968/1000 exact-float, 497/500 at 1e-12). Root cause: nx computes the edge weight as
`sum(1/(deg-1) for n in set(B[u]) & set(pred[v]))` over FRESH sets, and the
float-summation order is the set-intersection iteration order of those exact set
objects. Cached snapshot sets produce a different intersection order -> tiny float
divergences (the [[reference_parity_blocked_by_set_order]] class). The weight loop
therefore CANNOT be snapshotted byte-exactly; the directed projection is
weight-computation-bound and parity-locked to nx's fresh-set order.

Verdict: keep the byte-exact construction batch (cleaner, not a regression); the 0.7x
residual is the floor. A real win would need nx to change its summation, or a native
kernel reproducing CPython set-intersection order — not worth it for this niche fn.
