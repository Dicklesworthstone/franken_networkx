# Perf WIN (code-only) — bfs_tree / dfs_tree skip redundant _from_nx_graph (br-r37-c1-tcnoconv)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/traversal.py`
- DISK-CRITICAL turn: code-only, NO cargo/compile. Parity + conformance via existing install.

Same redundant-conversion lever as contracted_* / transitive_*: `nx.bfs_tree(fnx_G)`
and `nx.dfs_tree(fnx_G)` already resolve to an fnx-native DiGraph (fnx is a
registered backend for these), so the subsequent unconditional `_from_nx_graph` was
a pure redundant O(V+E) re-conversion of an already-fnx, already-nx-byte-exact tree.
Return the already-fnx result directly via the shared `_fnx_result_or_convert`
helper (isinstance-gated; genuine nx-typed inputs still convert).

These two are far more commonly used than the niche threshold/prufer constructors,
so this is the higher-impact node in the vein.

## Parity (existing install, no build) — ORDER-SENSITIVE (tree discovery order)
- fnx.traversal.bfs_tree vs nx-on-nx: 2000/2000 (directed/undirected, reverse,
  depth_limit, node order + BFS edge-discovery order + attrs, returns fnx.DiGraph).
- fnx.traversal.dfs_tree vs nx-on-nx: 2000/2000 (depth_limit, DFS order, fnx.DiGraph).
- pytest -k 'bfs_tree or dfs_tree or traversal': 916 passed.

## Perf
BENCH DEFERRED (disk-critical). Win = skip the whole _from_nx_graph conversion per
bfs_tree/dfs_tree call. Measure when disk recovers.
