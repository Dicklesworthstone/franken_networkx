# Perf WIN (code-only) — projected_graph MULTIGRAPH de-delegation (br-r37-c1-bpproj)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-CRITICAL turn: code-only, NO cargo/compile. Parity + conformance via existing install
  (touched the .so to clear the peer-Rust staleness guard; change is Python-only).

`bipartite.projected_graph` now de-delegates ALL fnx Graph/DiGraph cases. Prior commits
covered simple undirected + simple directed; this extends to the multigraph cases
(MultiGraph from undirected B, MultiDiGraph from directed B). Snapshot B's adjacency
once (native key-only binding = successors for DiGraph), and for each (u,n) sharing
common neighbours emit one edge per shared neighbour l keyed by l, deduped via has_edge
exactly like nx. Directed multigraph also snapshots predecessors once (B.pred — no
native pred-keys binding exists, but one per-access pass is fine). UNWEIGHTED -> no
float order to diverge -> byte-exact.

## Parity (existing install, no build) — EXACT edge order + keys
- All 4 combos {undirected,directed} x {simple,multigraph}: 1000/1000 each (node order,
  exact edge order with keys, node+graph attrs, result type). 0 mismatches.
- pytest -k 'projected or projection or bipartite': 1124 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-critical). Win = skip nx build + _from_nx_graph + per-access
AtlasView for multigraph projections. (Multigraph storage is the slow String-keyed
substrate either way, but de-delegation still removes one full build + the conversion.)
Measure when disk recovers. Only nx-typed B still delegates.
