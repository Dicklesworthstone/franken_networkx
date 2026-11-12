# NEGATIVE EVIDENCE — approximation.steiner_tree de-delegation is PARITY-BLOCKED (order-sensitive approximation)

- Agent: `BlackThrush` · 2026-06-21 · ATTEMPTED + REVERTED (clean)

## Target
fnx.approximation.steiner_tree is delegated via the namespace __getattr__ (full fnx->nx
conversion every call) -> 0.50x (fnx 2.96ms vs nx 1.94ms, gnm 200/1000, 4 terminals). Tried the
de-delegation pattern: a concrete steiner_tree running nx's EXACT mehlhorn in-process on the fnx
graph (fnx-native multi_source_dijkstra + shortest_path for the big graph; small _nx.Graph
intermediates for tie-break-exact MSTs).

## Why it FAILED (reverted)
Steiner tree is an ORDER-SENSITIVE APPROXIMATION. mehlhorn keys on `s[v] = paths[v][0]` (the
nearest-terminal from multi_source_dijkstra) and kou on `set(terminals).pop()` — both depend on
tie-break / set-iteration order. Empirically (40 random connected_watts graphs, weighted +
unweighted, 2-5 terminals): only 21/40 edge-identical to nx, AND the fallback kou path (which
DELEGATES) ALSO diverged on 8 graphs. So the result is a VALID-but-different tree; not byte-
matchable. This is exactly [[reference_parity_blocked_by_set_order]] — must stay delegated.
Perf was 0.65x even when run in-process (the conversion is not the dominant cost; nx's algorithm
on the small terminal set is), so the upside was marginal even ignoring the parity block.

## Latent sub-finding (NOT chased)
fnx's native `multi_source_dijkstra` returns `paths` whose `paths[v][0]` (nearest source on ties)
DIVERGES from nx's for some graphs — that is what broke the mehlhorn fast path. Likely a valid
different tie-break (distances should still match); worth a separate check of whether
multi_source_dijkstra PATH parity vs nx is contractually required (conformance may only assert
distances). Filed here so it is on record, not lost.

## Conclusion
steiner_tree stays delegated. No regression (reverted clean, tree == HEAD). The connectivity /
flow / graph-transform surface is otherwise DOMINATED (all_node_cuts now 1.52x after the
dead-attr win; bridges 199x, line_graph 4.5x, condensation 4.7x, harmonic_centrality 17.5x).
