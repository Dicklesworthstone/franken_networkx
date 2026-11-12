# Perf WIN (code-only) — projected_graph DIRECTED de-delegation (br-r37-c1-bpproj extension)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-CRITICAL turn: code-only, NO cargo/compile. Parity + conformance via existing install.

`bipartite.projected_graph` already had a snapshot-adjacency fast path for the simple
UNDIRECTED fnx Graph; directed B (DiGraph) still delegated (nx algorithm through fnx's
slow per-access adjacency views + _from_nx_graph rebuild). Extended the fast-path gate
to `type(B) in (Graph, DiGraph)`: snapshot B's adjacency once via the native key-only
binding (`_native_adjacency_keys` yields SUCCESSORS for a DiGraph, exactly nx's B[u]),
build a DiGraph projection directly.

KEY: projection is UNWEIGHTED (edge existence only — two nodes joined iff they share a
common neighbour), so unlike collaboration_weighted_projected_graph there is NO
float-summation order to diverge from nx -> byte-exact. (collaboration stays delegated;
it is set-iteration-order parity-locked, see that ledger.)

## Parity (existing install, no build)
- projected_graph DIRECTED vs nx-on-nx: 1000/1000 (node order, edge order, node attrs,
  graph attrs, result type DiGraph; mixed top->bottom and bottom->top edges).
- projected_graph UNDIRECTED regression guard: 1000/1000 (fast path unchanged).
- pytest -k 'projected or projection or bipartite': 1124 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-critical). Win = skip nx build + _from_nx_graph + per-access
AtlasView for directed projections. Measure when disk recovers.
