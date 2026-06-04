# all_simple_paths multigraph yield-order parity via order-preserving conversion (br-r37-c1-qpykd)

## Bug
`fnx.all_simple_paths` on a MultiGraph/MultiDiGraph delegated to networkx via
`_call_networkx_for_parity`, which converts the fnx multigraph to nx in `_fnx_to_nx`.
The multigraph branch grouped all of each node's edges together in node-iteration order:

    for u in fg:
        for v, keyed_attrs in fg[u].items():
            ... add (u, v, key) ...

This reordered parallel edges *across neighbours* relative to the original add_edge
sequence, so the converted graph's `edges(u, keys=True)` iteration differed from a
directly-built nx multigraph. networkx's `_all_simple_edge_paths` DFS iterates
`G.edges(node, keys=True)`, so the node-path YIELD ORDER diverged from nx (~9/60 random
multigraphs) — same path multiset, different sequence.

## Root cause & fix (ONE lever)
The simple-graph conversion path already emits edges via `_topo_emit_edges_by_adj` (a
per-node-queue topological order that reproduces the original add_edge adjacency, br-r37-
c1-sgnab); the multigraph path did NOT. Fix: route the multigraph conversion through the
same helper and emit all parallel keys per emitted `{u, v}` pair in their stored order:

    for u, v in _topo_emit_edges_by_adj(fg):
        G.add_edges_from((u, v, key, dict(attrs)) for key, attrs in fg[u][v].items())

This corrects the yield order for EVERY adj-dependent delegated multigraph algorithm
(all_simple_paths, BFS/DFS variants, …), not just all_simple_paths, and keeps networkx's
fast native DFS (no per-step fnx adjacency tax — a direct fnx-graph reimpl was ~70x slower
on n=12/cutoff=4, so conversion is the right substrate).

## Behavior parity (isomorphism proof)
- Conversion adjacency: 779 per-node `edges(u, keys=True)` checks (undirected + directed +
  self-loops) — converted multigraph byte-identical to a directly-built nx multigraph,
  **0 mismatches**.
- End-to-end: 4800 cases (200 random multi/di-multigraphs incl. self-loops × scalar/iterable/
  self targets × cutoffs None,0,1,2,3,5) — `fnx.all_simple_paths` == `nx.all_simple_paths`
  exactly (full yield order + raised-exception type), **0 mismatches**.
- Golden sha256 over all (graph, target, cutoff, path-list) tuples:
  `b4b09e61b07daae15bcdf9915b66a0846abf31822e96f4eeb46e461019fd79e1`.
- Suite: `pytest -k "multigraph or convert or backend or round_trip"` → 2423 passed; full
  suite 21270 passed (4 pre-existing peer failures in planarity-girth / gexf-classification /
  to_edgelist-view-type / coverage-gaps are unrelated — my change only reorders parallel-edge
  emission, which cannot affect a return type or delegation classification).

## Notes
Correctness fix (no new perf path). Conversion cost is the pre-existing delegation tax; the
multigraph topo-emit is the same O(V+E) class as the old grouped loop.
