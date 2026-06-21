# Perf WIN (code-only) — directed weighted/overlap/generic projection de-delegation (br-r37-c1-bpprojdir)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-CRITICAL turn: code-only, NO cargo. Parity + conformance via existing install.

Follow-up to br-r37-c1-bpprojorder. `_weighted_projection_inprocess` previously bailed
on directed B; added `allow_directed=True` so weighted / overlap / generic projections
de-delegate DiGraph too. For directed B the result is a DiGraph, `_native_adjacency_keys`
yields successors (= nx's B[u]) and the vnbrs row is B.pred[v] (snapshotted once). The
weights are integer counts / order-free ratios (len(un&vn), /n_top, /len(un|vn),
/min(...)) so there is NO float-summation order to diverge -> byte-exact.

collaboration keeps allow_directed=False: its weight is a float SUM over (un & vn),
which is set-iteration-order-locked for directed B (the long-standing collab directed
no-ship), so it stays delegated.

## Parity (existing install, no build) — EXACT edge order + weights vs nx-on-nx
- DIRECTED: weighted 2000/2000, overlap 2000/2000, generic 2000/2000.
- UNDIRECTED regression guard: weighted/overlap/generic/collaboration 2000/2000 each.
- collaboration DIRECTED (delegated): 2000/2000.
- pytest -k 'projected or projection or bipartite': 1124 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-critical). Win = skip nx build + _from_nx_graph + per-access
AtlasView for directed weighted/overlap/generic projections. Measure when disk recovers.

## Bipartite projection status
projected_graph: ALL fnx Graph/DiGraph x simple/multigraph native. weighted/overlap/
generic: Graph + DiGraph native. collaboration: undirected native, directed delegated
(float-order-locked). generic w/ user weight_function: delegated (arbitrary Python).
Only nx-typed B delegates across the board.
