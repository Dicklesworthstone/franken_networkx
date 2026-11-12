# Perf lever (code-only, bench deferred) — from_prufer_sequence native decode (br-r37-c1-prufernative)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/tree.py`
- DISK-LOW turn: code-only, no build/bench. Parity verified with existing install.

`tree.from_prufer_sequence` delegated: `nx_result = _nx_tree.from_prufer_sequence(seq);
return _from_nx_graph(nx_result)` — i.e. build an intermediate networkx graph
(per-edge add_edge) THEN pay `_from_nx_graph` (the O(V+E) fnx<-nx conversion +
adjacency-row alignment, separately measured at ~5x nx.Graph(edges)).

Lever: decode the Prüfer sequence DIRECTLY into an fnx Graph, replicating nx's exact
algorithm verbatim (remaining-degree Counter, smallest-available-leaf scan, final
two-orphan join, v-range validation), then build via one add_nodes_from + one
add_edges_from. Skips BOTH the nx graph build and the conversion — the proven
graph-returning-constructor lever ([[reference_from_nx_graph_double_build]]).

## Parity (existing install, no build)

- 3000 random valid Prüfer sequences (n=2..40): byte-exact node order, edge order,
  graph attrs.
- 500 to_prufer -> from_prufer round-trips: byte-exact.
- empty sequence (n=2) -> edge (0,1); invalid values -> NetworkXError (3 cases match
  nx); returns fnx.Graph. 0 mismatches.

## Perf

BENCH DEFERRED (disk-low). Confident win: the delegated path built an nx graph +
ran `_from_nx_graph`; the native decode skips both (same lever as the from_* /
relabel double-build wins, 2.5x+). Measure when disk recovers.
